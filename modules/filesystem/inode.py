# modules/filesystem/inode.py
# Phase: 4 — File System
# Owner: FS Agent
"""
Inode-based filesystem implementation.
Full implementation spec: OS101_AgentPlan_v2.md Sections 9.1, 9.3
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

from core.config import FilesystemConfig

# ── Constants ─────────────────────────────────────────────────────────────────
DIRECT_POINTERS:      int = 12  # inode.direct_blocks has exactly 12 slots
SINGLE_INDIRECT_SIZE: int = 1   # one block of pointers
DOUBLE_INDIRECT_SIZE: int = 1   # one block pointing to blocks of pointers

# Inode 0 = reserved, Inode 1 = root directory, user files start at inode 2


@dataclass
class Inode:
    """Inode data structure."""
    inode_num:      int
    file_type:      str = "file"        # "file" | "directory" | "symlink"
    link_count:     int = 1
    size_bytes:     int = 0
    direct_blocks:  list[int] = field(default_factory=lambda: [-1] * DIRECT_POINTERS)
    indirect_block: int = -1            # single indirect pointer
    double_indirect_block: int = -1     # double indirect pointer
    created_tick:   int = 0
    modified_tick:  int = 0
    owner_pid:      int = 0
    permissions:    str = "rw"


@dataclass
class InodeDirEntry:
    """Directory entry within an inode-based filesystem."""
    name:      str
    inode_num: int


@dataclass
class _OpenFile:
    """Internal state for an open file descriptor."""
    path:     str
    inode_num: int
    mode:     str
    position: int = 0


class InodeFileSystem:
    """
    Inode-based filesystem with all VFS interface methods.
    Inode 0 = reserved, Inode 1 = root directory, user files start at inode 2.
    """

    def __init__(self, config: FilesystemConfig) -> None:
        self._config: FilesystemConfig = config
        self._total_blocks: int = config.total_blocks
        self._block_size: int = config.block_size_kb * 1024

        # Inode table: inode_num → Inode
        self._inodes: dict[int, Inode] = {}
        self._next_inode: int = 2  # Start at 2 (0=reserved, 1=root)

        # Reserved inode 0
        self._inodes[0] = Inode(inode_num=0, file_type="reserved")

        # Root directory (inode 1)
        self._inodes[1] = Inode(inode_num=1, file_type="directory", created_tick=0)

        # Directory contents: inode_num → list[InodeDirEntry]
        self._dir_contents: dict[int, list[InodeDirEntry]] = {1: []}

        # Block allocation bitmap: block_index → True if allocated
        self._block_bitmap: list[bool] = [False] * self._total_blocks
        self._block_bitmap[0] = True  # Block 0 reserved

        # Block data storage
        self._block_data: dict[int, bytes] = {}

        # Open file descriptors
        self._open_files: dict[int, _OpenFile] = {}
        self._next_fd: int = 3

        # Operation counters
        self._ops: dict[str, int] = {"reads": 0, "writes": 0, "creates": 0, "deletes": 0}
        self._current_tick: int = 0

    # ── File Operations ───────────────────────────────────────────────────────

    def create(self, path: str) -> bool:
        """Create empty file at path. Returns False if already exists or disk full."""
        path = self._normalize(path)
        if self._resolve_path(path) is not None:
            return False

        parent_path = self._parent_path(path)
        parent_ino = self._resolve_path(parent_path)
        if parent_ino is None or self._inodes[parent_ino].file_type != "directory":
            return False

        # Allocate inode
        ino = self._alloc_inode("file")
        if ino is None:
            return False

        # Add dir entry to parent
        name = self._basename(path)
        self._dir_contents[parent_ino].append(InodeDirEntry(name=name, inode_num=ino))
        self._ops["creates"] += 1
        return True

    def open(self, path: str, mode: str) -> int | None:
        """Open file for I/O. Returns fd >= 3, or None if file not found."""
        path = self._normalize(path)
        ino = self._resolve_path(path)
        if ino is None:
            return None
        inode = self._inodes[ino]
        if inode.file_type not in ("file", "symlink"):
            return None

        fd = self._next_fd
        self._next_fd += 1
        position = 0
        if mode == "a":
            position = inode.size_bytes
        self._open_files[fd] = _OpenFile(path=path, inode_num=ino, mode=mode, position=position)
        return fd

    def close(self, fd: int) -> bool:
        """Close fd. Returns False if fd invalid."""
        if fd not in self._open_files:
            return False
        del self._open_files[fd]
        return True

    def read(self, fd: int, size: int) -> bytes | None:
        """Read up to size bytes from current position."""
        if fd not in self._open_files:
            return None
        of = self._open_files[fd]
        inode = self._inodes.get(of.inode_num)
        if inode is None:
            return None

        all_data = self._read_inode_data(inode)
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
        inode = self._inodes.get(of.inode_num)
        if inode is None:
            return 0

        existing = self._read_inode_data(inode)

        if of.mode == "a":
            new_data = existing + data
        else:
            new_data = existing[:of.position] + data
            if of.position + len(data) < len(existing):
                new_data += existing[of.position + len(data):]

        # Free existing blocks
        self._free_inode_blocks(inode)

        if not new_data:
            inode.size_bytes = 0
            of.position += len(data)
            self._ops["writes"] += 1
            return len(data)

        # Calculate blocks needed
        blocks_needed = (len(new_data) + self._block_size - 1) // self._block_size
        free_blocks = self._get_free_blocks()

        if not free_blocks:
            inode.size_bytes = 0
            self._ops["writes"] += 1
            return 0

        actual_blocks = min(blocks_needed, len(free_blocks))
        # BUG-44 fix: Cap at DIRECT_POINTERS to prevent orphaned blocks
        # (indirect block support not implemented)
        actual_blocks = min(actual_blocks, DIRECT_POINTERS)
        actual_bytes = min(len(new_data), actual_blocks * self._block_size)
        new_data = new_data[:actual_bytes]
        allocated = free_blocks[:actual_blocks]

        # Allocate blocks and write data
        for i, blk in enumerate(allocated):
            self._block_bitmap[blk] = True
            start = i * self._block_size
            end = min(start + self._block_size, len(new_data))
            self._block_data[blk] = new_data[start:end]

            if i < DIRECT_POINTERS:
                inode.direct_blocks[i] = blk

        inode.size_bytes = len(new_data)
        inode.modified_tick = self._current_tick
        of.position += len(data)
        self._ops["writes"] += 1
        return len(data) if actual_bytes >= len(new_data) else 0

    def seek(self, fd: int, offset: int, whence: str) -> int:
        """Move file position."""
        if fd not in self._open_files:
            return -1
        of = self._open_files[fd]
        inode = self._inodes.get(of.inode_num)
        file_size = inode.size_bytes if inode else 0

        if whence == "start":
            of.position = offset
        elif whence == "current":
            of.position += offset
        elif whence == "end":
            of.position = file_size + offset

        of.position = max(0, of.position)
        return of.position

    def delete(self, path: str) -> bool:
        """Delete file at path. Returns False if not found or is directory."""
        path = self._normalize(path)
        ino = self._resolve_path(path)
        if ino is None:
            return False
        inode = self._inodes[ino]
        if inode.file_type == "directory":
            return False

        # Decrement link count
        inode.link_count -= 1

        # Remove dir entry from parent
        parent_path = self._parent_path(path)
        parent_ino = self._resolve_path(parent_path)
        name = self._basename(path)
        if parent_ino is not None and parent_ino in self._dir_contents:
            self._dir_contents[parent_ino] = [
                e for e in self._dir_contents[parent_ino] if not (e.name == name and e.inode_num == ino)
            ]

        # If link_count reaches 0, actually free the inode
        if inode.link_count <= 0:
            self._free_inode_blocks(inode)
            del self._inodes[ino]

        # Close open fds
        fds_to_close = [fd for fd, of in self._open_files.items() if of.path == path]
        for fd in fds_to_close:
            del self._open_files[fd]

        self._ops["deletes"] += 1
        return True

    def stat(self, path: str) -> dict | None:
        """Returns file info dict, or None if not found."""
        path = self._normalize(path)
        ino = self._resolve_path(path)
        if ino is None:
            return None
        inode = self._inodes[ino]
        block_count = sum(1 for b in inode.direct_blocks if b >= 0)
        return {
            "name": self._basename(path),
            "size_bytes": inode.size_bytes,
            "created_tick": inode.created_tick,
            "modified_tick": inode.modified_tick,
            "is_directory": inode.file_type == "directory",
            "block_count": block_count,
            "fragmentation_ratio": 0.0,
            "inode_num": ino,
            "link_count": inode.link_count,
        }

    # ── Directory Operations ──────────────────────────────────────────────────

    def mkdir(self, path: str) -> bool:
        """Create directory. Returns False if already exists."""
        path = self._normalize(path)
        if self._resolve_path(path) is not None:
            return False
        parent_path = self._parent_path(path)
        parent_ino = self._resolve_path(parent_path)
        if parent_ino is None or self._inodes[parent_ino].file_type != "directory":
            return False

        ino = self._alloc_inode("directory")
        if ino is None:
            return False
        self._dir_contents[ino] = []
        name = self._basename(path)
        self._dir_contents[parent_ino].append(InodeDirEntry(name=name, inode_num=ino))
        return True

    def rmdir(self, path: str) -> bool:
        """Remove empty directory. Returns False if not empty or not found."""
        path = self._normalize(path)
        ino = self._resolve_path(path)
        if ino is None or ino == 1:
            return False
        inode = self._inodes[ino]
        if inode.file_type != "directory":
            return False
        if ino in self._dir_contents and self._dir_contents[ino]:
            return False

        parent_path = self._parent_path(path)
        parent_ino = self._resolve_path(parent_path)
        name = self._basename(path)
        if parent_ino is not None and parent_ino in self._dir_contents:
            self._dir_contents[parent_ino] = [
                e for e in self._dir_contents[parent_ino] if not (e.name == name and e.inode_num == ino)
            ]
        if ino in self._dir_contents:
            del self._dir_contents[ino]
        del self._inodes[ino]
        return True

    def listdir(self, path: str) -> list[str] | None:
        """List directory contents."""
        path = self._normalize(path)
        ino = self._resolve_path(path)
        if ino is None:
            return None
        inode = self._inodes.get(ino)
        if inode is None or inode.file_type != "directory":
            return None
        entries = self._dir_contents.get(ino, [])
        return [e.name for e in entries]

    def rename(self, old_path: str, new_path: str) -> bool:
        """Rename/move file or directory."""
        old_path = self._normalize(old_path)
        new_path = self._normalize(new_path)
        ino = self._resolve_path(old_path)
        if ino is None:
            return False
        if self._resolve_path(new_path) is not None:
            return False

        # Remove from old parent
        old_parent_ino = self._resolve_path(self._parent_path(old_path))
        old_name = self._basename(old_path)
        if old_parent_ino is not None and old_parent_ino in self._dir_contents:
            self._dir_contents[old_parent_ino] = [
                e for e in self._dir_contents[old_parent_ino]
                if not (e.name == old_name and e.inode_num == ino)
            ]

        # Add to new parent
        new_parent_ino = self._resolve_path(self._parent_path(new_path))
        if new_parent_ino is None:
            return False
        new_name = self._basename(new_path)
        self._dir_contents[new_parent_ino].append(InodeDirEntry(name=new_name, inode_num=ino))
        self._inodes[ino].modified_tick = self._current_tick
        return True

    # ── Hard/Symbolic Links ───────────────────────────────────────────────────

    def hard_link(self, existing_path: str, link_path: str) -> bool:
        """Create a hard link: link_path points to same inode as existing_path."""
        existing_path = self._normalize(existing_path)
        link_path = self._normalize(link_path)

        ino = self._resolve_path(existing_path)
        if ino is None:
            return False
        inode = self._inodes[ino]
        if inode.file_type == "directory":
            return False  # Hard links to directories not allowed

        if self._resolve_path(link_path) is not None:
            return False  # Link path already exists

        parent_path = self._parent_path(link_path)
        parent_ino = self._resolve_path(parent_path)
        if parent_ino is None:
            return False

        # Add dir entry pointing to same inode
        name = self._basename(link_path)
        self._dir_contents[parent_ino].append(InodeDirEntry(name=name, inode_num=ino))
        inode.link_count += 1
        return True

    def symlink(self, target_path: str, link_path: str) -> bool:
        """Create a symbolic link: link_path is a symlink pointing to target_path."""
        link_path = self._normalize(link_path)
        if self._resolve_path(link_path) is not None:
            return False

        parent_path = self._parent_path(link_path)
        parent_ino = self._resolve_path(parent_path)
        if parent_ino is None:
            return False

        ino = self._alloc_inode("symlink")
        if ino is None:
            return False

        # Store target path as data
        inode = self._inodes[ino]
        target_bytes = target_path.encode("utf-8")
        free_blocks = self._get_free_blocks()
        if free_blocks:
            blk = free_blocks[0]
            self._block_bitmap[blk] = True
            self._block_data[blk] = target_bytes
            inode.direct_blocks[0] = blk
            inode.size_bytes = len(target_bytes)

        name = self._basename(link_path)
        self._dir_contents[parent_ino].append(InodeDirEntry(name=name, inode_num=ino))
        return True

    # ── Metrics ───────────────────────────────────────────────────────────────

    def get_metrics(self) -> dict[str, Any]:
        """Returns filesystem metrics."""
        used = sum(1 for b in self._block_bitmap if b)
        free = self._total_blocks - used
        files = sum(1 for i in self._inodes.values() if i.file_type == "file")
        dirs = sum(1 for i in self._inodes.values() if i.file_type == "directory") - 1  # Exclude root

        return {
            "used_blocks": used,
            "free_blocks": free,
            "total_blocks": self._total_blocks,
            "file_count": files,
            "dir_count": max(0, dirs),
            "fragmentation_ratio": 0.0,
            "ops_count": dict(self._ops),
        }

    def tick(self, tick: int) -> None:
        """Called every tick by the kernel."""
        self._current_tick = tick

    # ── Internal Helpers ──────────────────────────────────────────────────────

    def _normalize(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        if path != "/" and path.endswith("/"):
            path = path.rstrip("/")
        return path

    def _parent_path(self, path: str) -> str:
        if path == "/":
            return "/"
        parts = path.rsplit("/", 1)
        return parts[0] if parts[0] else "/"

    def _basename(self, path: str) -> str:
        return path.rsplit("/", 1)[-1]

    def _resolve_path(self, path: str) -> int | None:
        """Resolve a path to an inode number. Returns None if not found."""
        path = self._normalize(path)
        if path == "/":
            return 1

        parts = path.strip("/").split("/")
        current_ino = 1  # Start at root

        for part in parts:
            entries = self._dir_contents.get(current_ino, [])
            found = False
            for e in entries:
                if e.name == part:
                    current_ino = e.inode_num
                    found = True
                    break
            if not found:
                return None

        return current_ino

    def _alloc_inode(self, file_type: str) -> int | None:
        """Allocate a new inode. Returns inode number or None."""
        ino = self._next_inode
        self._next_inode += 1
        self._inodes[ino] = Inode(
            inode_num=ino,
            file_type=file_type,
            created_tick=self._current_tick,
            modified_tick=self._current_tick,
        )
        return ino

    def _get_free_blocks(self) -> list[int]:
        """Get list of free block indices (excluding block 0)."""
        return [i for i in range(1, self._total_blocks) if not self._block_bitmap[i]]

    def _free_inode_blocks(self, inode: Inode) -> None:
        """Free all data blocks associated with an inode."""
        for i in range(DIRECT_POINTERS):
            blk = inode.direct_blocks[i]
            if blk >= 0:
                self._block_bitmap[blk] = False
                if blk in self._block_data:
                    del self._block_data[blk]
                inode.direct_blocks[i] = -1

    def _read_inode_data(self, inode: Inode) -> bytes:
        """Read all data from an inode's direct blocks."""
        data = bytearray()
        for i in range(DIRECT_POINTERS):
            blk = inode.direct_blocks[i]
            if blk < 0:
                break
            block = self._block_data.get(blk, b"\x00" * self._block_size)
            data.extend(block)
        return bytes(data[:inode.size_bytes])
