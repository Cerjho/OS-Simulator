# modules/filesystem/fat.py
# Phase: 4 — File System
# Owner: FS Agent
"""
FAT (File Allocation Table) filesystem implementation.
Full implementation spec: OS101_AgentPlan_v2.md Sections 9.1, 9.2
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

from core.config import FilesystemConfig

# ── FAT Sentinel Constants ────────────────────────────────────────────────────
FAT_FREE: int = 0x00000000   # Block is free
FAT_EOF:  int = 0xFFFFFFFF   # End of file chain
FAT_BAD:  int = 0xFFFFFFF7   # Bad block (skip)


@dataclass
class DirEntry:
    """FAT directory entry."""
    name:          str
    extension:     str = ""
    attributes:    str = "file"     # "file" | "directory"
    size_bytes:    int = 0
    first_cluster: int = -1         # -1 = no data blocks allocated
    created_tick:  int = 0
    modified_tick: int = 0


@dataclass
class _OpenFile:
    """Internal state for an open file descriptor."""
    path: str
    mode: str
    position: int = 0


class FATFileSystem:
    """
    FAT filesystem with all VFS interface methods.
    Block 0 is RESERVED (boot sector). Never allocate block 0 to a file.
    """

    def __init__(self, config: FilesystemConfig) -> None:
        self._config: FilesystemConfig = config
        self._total_blocks: int = config.total_blocks
        self._block_size: int = config.block_size_kb * 1024  # bytes

        # FAT table: block_index → next_block (FAT_FREE, FAT_EOF, or next index)
        self._fat: list[int] = [FAT_FREE] * self._total_blocks
        self._fat[0] = FAT_BAD  # Block 0 reserved

        # Directory tree: path → DirEntry
        self._dir_entries: dict[str, DirEntry] = {}
        # Root directory always exists
        self._dir_entries["/"] = DirEntry(
            name="/", attributes="directory", created_tick=0, modified_tick=0
        )

        # Block data storage: block_index → bytes
        self._block_data: dict[int, bytes] = {}

        # Open file descriptors: fd → _OpenFile
        self._open_files: dict[int, _OpenFile] = {}
        self._next_fd: int = 3  # 0/1/2 reserved for stdin/stdout/stderr

        # Operation counters
        self._ops: dict[str, int] = {"reads": 0, "writes": 0, "creates": 0, "deletes": 0}

        # Tick counter for timestamps
        self._current_tick: int = 0

    # ── File Operations ───────────────────────────────────────────────────────

    def create(self, path: str) -> bool:
        """Create empty file at path. Returns False if path already exists or disk full."""
        path = self._normalize(path)
        if path in self._dir_entries:
            return False

        # Verify parent directory exists
        parent = self._parent_path(path)
        if parent not in self._dir_entries or self._dir_entries[parent].attributes != "directory":
            return False

        name = self._basename(path)
        self._dir_entries[path] = DirEntry(
            name=name,
            attributes="file",
            size_bytes=0,
            first_cluster=-1,
            created_tick=self._current_tick,
            modified_tick=self._current_tick,
        )
        self._ops["creates"] += 1
        return True

    def open(self, path: str, mode: str) -> int | None:
        """Open file for I/O. Returns fd >= 3, or None if file not found."""
        path = self._normalize(path)
        if path not in self._dir_entries:
            return None
        entry = self._dir_entries[path]
        if entry.attributes != "file":
            return None

        fd = self._next_fd
        self._next_fd += 1
        position = 0
        if mode == "a":
            position = entry.size_bytes
        self._open_files[fd] = _OpenFile(path=path, mode=mode, position=position)
        return fd

    def close(self, fd: int) -> bool:
        """Close fd. Returns False if fd invalid."""
        if fd not in self._open_files:
            return False
        del self._open_files[fd]
        return True

    def read(self, fd: int, size: int) -> bytes | None:
        """Read up to size bytes from current position. Returns None if fd invalid."""
        if fd not in self._open_files:
            return None
        of = self._open_files[fd]
        path = of.path
        if path not in self._dir_entries:
            return None

        entry = self._dir_entries[path]
        all_data = self._read_file_data(entry)
        start = of.position
        end = min(start + size, len(all_data))
        result = all_data[start:end]
        of.position = end
        self._ops["reads"] += 1
        return result

    def write(self, fd: int, data: bytes) -> int:
        """Write data. Returns bytes written (may be less if disk full)."""
        if fd not in self._open_files:
            return 0
        of = self._open_files[fd]
        path = of.path
        if path not in self._dir_entries:
            return 0

        entry = self._dir_entries[path]

        # Read existing data
        existing = self._read_file_data(entry)

        # Insert new data at current position
        if of.mode == "a":
            new_data = existing + data
        else:
            new_data = existing[:of.position] + data
            if of.position + len(data) < len(existing):
                new_data += existing[of.position + len(data):]

        # Calculate blocks needed
        blocks_needed = max(1, (len(new_data) + self._block_size - 1) // self._block_size) if new_data else 0

        # Free existing blocks
        self._free_chain(entry.first_cluster)
        entry.first_cluster = -1

        if blocks_needed == 0:
            entry.size_bytes = 0
            of.position += len(data)
            self._ops["writes"] += 1
            return len(data)

        # Allocate new blocks
        free_blocks = self._get_free_blocks()
        available = len(free_blocks)
        if available == 0:
            # Disk full — cannot write anything
            entry.size_bytes = 0
            self._ops["writes"] += 1
            return 0

        actual_blocks = min(blocks_needed, available)
        actual_bytes = min(len(new_data), actual_blocks * self._block_size)

        # Truncate data to fit
        new_data = new_data[:actual_bytes]
        allocated = free_blocks[:actual_blocks]

        # Build FAT chain
        for i, blk in enumerate(allocated):
            if i < len(allocated) - 1:
                self._fat[blk] = allocated[i + 1]
            else:
                self._fat[blk] = FAT_EOF

        # Write data to blocks
        for i, blk in enumerate(allocated):
            start = i * self._block_size
            end = min(start + self._block_size, len(new_data))
            self._block_data[blk] = new_data[start:end]

        entry.first_cluster = allocated[0]
        entry.size_bytes = len(new_data)
        entry.modified_tick = self._current_tick

        # BUG-45 fix: Return actual bytes written, not the requested amount
        actual_written = len(new_data) - of.position if of.mode != "a" else len(new_data) - len(existing)
        actual_written = max(0, min(actual_written, len(data)))
        of.position += actual_written
        self._ops["writes"] += 1
        return actual_written

    def seek(self, fd: int, offset: int, whence: str) -> int:
        """Move file position. whence: 'start' | 'current' | 'end'. Returns new position."""
        if fd not in self._open_files:
            return -1
        of = self._open_files[fd]
        path = of.path
        entry = self._dir_entries.get(path)
        file_size = entry.size_bytes if entry else 0

        if whence == "start":
            of.position = offset
        elif whence == "current":
            of.position += offset
        elif whence == "end":
            of.position = file_size + offset

        of.position = max(0, of.position)
        return of.position

    def delete(self, path: str) -> bool:
        """Delete file at path. Returns False if not found or path is a directory."""
        path = self._normalize(path)
        if path not in self._dir_entries:
            return False
        entry = self._dir_entries[path]
        if entry.attributes != "file":
            return False

        # Free the block chain
        self._free_chain(entry.first_cluster)
        del self._dir_entries[path]

        # Close any open fds pointing to this file
        fds_to_close = [fd for fd, of in self._open_files.items() if of.path == path]
        for fd in fds_to_close:
            del self._open_files[fd]

        self._ops["deletes"] += 1
        return True

    def stat(self, path: str) -> dict | None:
        """Returns file info dict, or None if path not found."""
        path = self._normalize(path)
        if path not in self._dir_entries:
            return None
        entry = self._dir_entries[path]
        block_count = self._count_chain(entry.first_cluster) if entry.first_cluster >= 0 else 0
        return {
            "name": entry.name,
            "size_bytes": entry.size_bytes,
            "created_tick": entry.created_tick,
            "modified_tick": entry.modified_tick,
            "is_directory": entry.attributes == "directory",
            "block_count": block_count,
            "fragmentation_ratio": self._file_fragmentation(entry.first_cluster),
        }

    # ── Directory Operations ──────────────────────────────────────────────────

    def mkdir(self, path: str) -> bool:
        """Create directory. Returns False if already exists."""
        path = self._normalize(path)
        if path in self._dir_entries:
            return False
        parent = self._parent_path(path)
        if parent not in self._dir_entries or self._dir_entries[parent].attributes != "directory":
            return False

        name = self._basename(path)
        self._dir_entries[path] = DirEntry(
            name=name, attributes="directory",
            created_tick=self._current_tick, modified_tick=self._current_tick,
        )
        return True

    def rmdir(self, path: str) -> bool:
        """Remove empty directory. Returns False if not empty or not found."""
        path = self._normalize(path)
        if path not in self._dir_entries or path == "/":
            return False
        entry = self._dir_entries[path]
        if entry.attributes != "directory":
            return False
        # Check if directory is empty
        children = [k for k in self._dir_entries if self._parent_path(k) == path and k != path]
        if children:
            return False
        del self._dir_entries[path]
        return True

    def listdir(self, path: str) -> list[str] | None:
        """List directory contents. Returns None if path not a directory."""
        path = self._normalize(path)
        if path not in self._dir_entries or self._dir_entries[path].attributes != "directory":
            return None
        children = []
        for k, v in self._dir_entries.items():
            if k == path:
                continue
            if self._parent_path(k) == path:
                children.append(v.name)
        return children

    def rename(self, old_path: str, new_path: str) -> bool:
        """Rename/move file or directory."""
        old_path = self._normalize(old_path)
        new_path = self._normalize(new_path)
        if old_path not in self._dir_entries:
            return False
        if new_path in self._dir_entries:
            return False
        new_parent = self._parent_path(new_path)
        if new_parent not in self._dir_entries:
            return False

        entry = self._dir_entries.pop(old_path)
        entry.name = self._basename(new_path)
        entry.modified_tick = self._current_tick
        self._dir_entries[new_path] = entry

        # Also move children if it's a directory
        if entry.attributes == "directory":
            children_to_move: list[tuple[str, str]] = []
            for k in list(self._dir_entries.keys()):
                if k.startswith(old_path + "/"):
                    new_child = new_path + k[len(old_path):]
                    children_to_move.append((k, new_child))
            for old_k, new_k in children_to_move:
                child = self._dir_entries.pop(old_k)
                self._dir_entries[new_k] = child

        return True

    # ── Hard/Symbolic Links ───────────────────────────────────────────────────

    def hard_link(self, existing_path: str, link_path: str) -> bool:
        """FAT does not support hard links."""
        return False

    def symlink(self, target_path: str, link_path: str) -> bool:
        """FAT does not support symbolic links."""
        return False

    # ── Metrics ───────────────────────────────────────────────────────────────

    def get_metrics(self) -> dict[str, Any]:
        """Returns filesystem metrics."""
        used = sum(1 for b in self._fat if b not in (FAT_FREE, FAT_BAD))
        free = sum(1 for b in self._fat if b == FAT_FREE)
        files = sum(1 for e in self._dir_entries.values() if e.attributes == "file")
        dirs = sum(1 for e in self._dir_entries.values() if e.attributes == "directory") - 1  # Exclude root

        total_frag = 0.0
        file_count_for_frag = 0
        for e in self._dir_entries.values():
            if e.attributes == "file" and e.first_cluster >= 0:
                total_frag += self._file_fragmentation(e.first_cluster)
                file_count_for_frag += 1

        avg_frag = total_frag / file_count_for_frag if file_count_for_frag > 0 else 0.0

        return {
            "used_blocks": used,
            "free_blocks": free,
            "total_blocks": self._total_blocks,
            "file_count": files,
            "dir_count": max(0, dirs),
            "fragmentation_ratio": avg_frag,
            "ops_count": dict(self._ops),
        }

    def tick(self, tick: int) -> None:
        """Called every tick by the kernel."""
        self._current_tick = tick

    # ── Internal Helpers ──────────────────────────────────────────────────────

    def _normalize(self, path: str) -> str:
        """Normalize path: ensure leading /, remove trailing /."""
        if not path.startswith("/"):
            path = "/" + path
        if path != "/" and path.endswith("/"):
            path = path.rstrip("/")
        return path

    def _parent_path(self, path: str) -> str:
        """Get parent directory path."""
        if path == "/":
            return "/"
        parts = path.rsplit("/", 1)
        parent = parts[0] if parts[0] else "/"
        return parent

    def _basename(self, path: str) -> str:
        """Get filename from path."""
        return path.rsplit("/", 1)[-1]

    def _get_free_blocks(self) -> list[int]:
        """Get list of all free block indices (excluding block 0)."""
        return [i for i in range(1, self._total_blocks) if self._fat[i] == FAT_FREE]

    def _free_chain(self, start_block: int) -> None:
        """Free a FAT chain starting from start_block."""
        if start_block < 0:
            return
        current = start_block
        visited: set[int] = set()  # BUG-43 fix: detect cyclic chains
        while current != FAT_EOF and current != FAT_FREE and 0 < current < self._total_blocks:
            if current in visited:
                break  # Cyclic chain detected — stop to prevent infinite loop
            visited.add(current)
            next_block = self._fat[current]
            self._fat[current] = FAT_FREE
            if current in self._block_data:
                del self._block_data[current]
            current = next_block

    def _read_file_data(self, entry: DirEntry) -> bytes:
        """Read all data from a file's block chain."""
        if entry.first_cluster < 0:
            return b""
        data = bytearray()
        current = entry.first_cluster
        visited: set[int] = set()  # BUG-43 fix: detect cyclic chains
        while current != FAT_EOF and current != FAT_FREE and 0 < current < self._total_blocks:
            if current in visited:
                break
            visited.add(current)
            block = self._block_data.get(current, b"\x00" * self._block_size)
            data.extend(block)
            current = self._fat[current]
        return bytes(data[:entry.size_bytes])

    def _count_chain(self, start_block: int) -> int:
        """Count blocks in a FAT chain."""
        if start_block < 0:
            return 0
        count = 0
        current = start_block
        visited: set[int] = set()  # BUG-43 fix: detect cyclic chains
        while current != FAT_EOF and current != FAT_FREE and 0 < current < self._total_blocks:
            if current in visited:
                break
            visited.add(current)
            count += 1
            current = self._fat[current]
        return count

    def _file_fragmentation(self, start_block: int) -> float:
        """Calculate fragmentation ratio for a file (0.0 = contiguous, 1.0 = max fragmented)."""
        if start_block < 0:
            return 0.0
        blocks: list[int] = []
        current = start_block
        visited: set[int] = set()  # BUG-43 fix: detect cyclic chains
        while current != FAT_EOF and current != FAT_FREE and 0 < current < self._total_blocks:
            if current in visited:
                break
            visited.add(current)
            blocks.append(current)
            current = self._fat[current]
        if len(blocks) <= 1:
            return 0.0
        non_contiguous = sum(1 for i in range(len(blocks) - 1) if blocks[i + 1] != blocks[i] + 1)
        return non_contiguous / (len(blocks) - 1)
