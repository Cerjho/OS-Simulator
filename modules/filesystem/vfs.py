# modules/filesystem/vfs.py
# Phase: 4 — File System
# Owner: FS Agent
"""
Virtual File System (VFS) layer.
Delegates all operations to the configured backend (FAT or Inode).
Full implementation spec: OS101_AgentPlan_v2.md Section 9.1
"""
from __future__ import annotations
from typing import Any

from core.config import FilesystemConfig
from modules.filesystem.fat import FATFileSystem
from modules.filesystem.inode import InodeFileSystem


class VirtualFileSystem:
    """
    Virtual File System layer providing a unified interface to the underlying
    storage backend (FAT or Inode).

    Rules:
      - Delegates ALL calls to active backend.
      - Backend selected by config.type ('fat' or 'inode').
      - Global fd namespace starting at 3.
      - Path resolution traverses full absolute paths.
    """

    def __init__(self, config: FilesystemConfig) -> None:
        self._config: FilesystemConfig = config
        self._backend: FATFileSystem | InodeFileSystem

        if config.type == "fat":
            self._backend = FATFileSystem(config)
        elif config.type == "inode":
            self._backend = InodeFileSystem(config)
        else:
            raise ValueError(f"Unknown filesystem backend type: {config.type!r}")

    # ── File Operations ───────────────────────────────────────────────────────

    def create(self, path: str) -> bool:
        """Create empty file at path. Returns False if path already exists or disk full."""
        return self._backend.create(path)

    def open(self, path: str, mode: str) -> int | None:
        """
        Open file for I/O. mode: "r" | "w" | "a" | "rw"
        Returns integer file descriptor (fd >= 3), or None if file not found.
        Global fd namespace across the VFS instance.
        """
        return self._backend.open(path, mode)

    def close(self, fd: int) -> bool:
        """Close fd. Returns False if fd invalid."""
        return self._backend.close(fd)

    def read(self, fd: int, size: int) -> bytes | None:
        """Read up to size bytes from current position. Returns None if fd invalid."""
        return self._backend.read(fd, size)

    def write(self, fd: int, data: bytes) -> int:
        """Write data. Returns bytes written (may be less than len(data) if disk full)."""
        return self._backend.write(fd, data)

    def seek(self, fd: int, offset: int, whence: str) -> int:
        """
        Move file position. whence: "start" | "current" | "end"
        Returns new absolute position.
        """
        return self._backend.seek(fd, offset, whence)

    def delete(self, path: str) -> bool:
        """Delete file at path. Returns False if not found or path is a directory."""
        return self._backend.delete(path)

    def stat(self, path: str) -> dict[str, Any] | None:
        """
        Returns file info dict, or None if path not found.
        """
        return self._backend.stat(path)

    # ── Directory Operations ──────────────────────────────────────────────────

    def mkdir(self, path: str) -> bool:
        """Create directory. Returns False if already exists."""
        return self._backend.mkdir(path)

    def rmdir(self, path: str) -> bool:
        """Remove empty directory. Returns False if not empty or not found."""
        return self._backend.rmdir(path)

    def listdir(self, path: str) -> list[str] | None:
        """List directory contents. Returns None if path not a directory."""
        return self._backend.listdir(path)

    def rename(self, old_path: str, new_path: str) -> bool:
        """Rename/move file or directory."""
        return self._backend.rename(old_path, new_path)

    # ── Hard/Symbolic Links ───────────────────────────────────────────────────

    def hard_link(self, existing_path: str, link_path: str) -> bool:
        """Create a hard link."""
        return self._backend.hard_link(existing_path, link_path)

    def symlink(self, target_path: str, link_path: str) -> bool:
        """Create a symbolic link."""
        return self._backend.symlink(target_path, link_path)

    # ── Metrics & Lifecycle ───────────────────────────────────────────────────

    def get_metrics(self) -> dict[str, Any]:
        """Returns aggregate filesystem metrics."""
        return self._backend.get_metrics()

    def tick(self, tick: int) -> None:
        """Lifecycle hook called every kernel tick."""
        self._backend.tick(tick)
