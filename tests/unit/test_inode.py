# tests/unit/test_inode.py
"""
Unit tests for inode.
Reference: OS101_AgentPlan_v2.md Section 15
"""
import pytest
from core.config import FilesystemConfig
from modules.filesystem.inode import InodeFileSystem
from modules.process.pcb import reset_pid_counter


@pytest.fixture(autouse=True)
def reset_pids():
    """Ensure PIDs are deterministic across tests."""
    reset_pid_counter()
    yield
    reset_pid_counter()


class TestInodeFileSystem:

    def test_root_dir_is_inode_1(self):
        # Arrange & Act
        fs = InodeFileSystem(FilesystemConfig())
        # Assert
        assert 1 in fs._inodes
        assert fs._inodes[1].file_type == "directory"

    def test_create_file_allocates_inode(self):
        # Arrange
        fs = InodeFileSystem(FilesystemConfig())
        # Act
        result = fs.create("/test.txt")
        # Assert
        assert result is True
        ino = fs._resolve_path("/test.txt")
        assert ino is not None
        assert fs._inodes[ino].file_type == "file"

    def test_mkdir_creates_directory(self):
        # Arrange
        fs = InodeFileSystem(FilesystemConfig())
        # Act
        result = fs.mkdir("/subdir")
        # Assert
        assert result is True
        ino = fs._resolve_path("/subdir")
        assert ino is not None
        assert fs._inodes[ino].file_type == "directory"

    def test_listdir_returns_names(self):
        # Arrange
        fs = InodeFileSystem(FilesystemConfig())
        fs.create("/a.txt")
        fs.create("/b.txt")
        # Act
        listing = fs.listdir("/")
        # Assert
        assert set(listing) == {"a.txt", "b.txt"}

    def test_write_and_read_roundtrip(self):
        # Arrange
        fs = InodeFileSystem(FilesystemConfig())
        fs.create("/test.txt")
        fd_w = fs.open("/test.txt", "w")
        data = b"inode file data"
        # Act
        fs.write(fd_w, data)
        fs.close(fd_w)
        fd_r = fs.open("/test.txt", "r")
        read_data = fs.read(fd_r, len(data))
        fs.close(fd_r)
        # Assert
        assert read_data == data

    def test_delete_removes_inode(self):
        # Arrange
        fs = InodeFileSystem(FilesystemConfig())
        fs.create("/test.txt")
        # Act
        result = fs.delete("/test.txt")
        # Assert
        assert result is True
        assert fs._resolve_path("/test.txt") is None

    def test_hard_link_increments_link_count(self):
        # Arrange
        fs = InodeFileSystem(FilesystemConfig())
        fs.create("/original.txt")
        ino = fs._resolve_path("/original.txt")
        orig_links = fs._inodes[ino].link_count
        # Act
        result = fs.hard_link("/original.txt", "/link.txt")
        # Assert
        assert result is True
        assert fs._inodes[ino].link_count == orig_links + 1

    def test_rmdir_empty_directory(self):
        # Arrange
        fs = InodeFileSystem(FilesystemConfig())
        fs.mkdir("/empty_dir")
        # Act
        result = fs.rmdir("/empty_dir")
        # Assert
        assert result is True
        assert fs._resolve_path("/empty_dir") is None

    def test_rmdir_non_empty_fails(self):
        # Arrange
        fs = InodeFileSystem(FilesystemConfig())
        fs.mkdir("/full_dir")
        fs.create("/full_dir/file.txt")
        # Act
        result = fs.rmdir("/full_dir")
        # Assert
        assert result is False

    def test_rename_file(self):
        # Arrange
        fs = InodeFileSystem(FilesystemConfig())
        fs.create("/old_name.txt")
        # Act
        result = fs.rename("/old_name.txt", "/new_name.txt")
        # Assert
        assert result is True
        assert fs._resolve_path("/old_name.txt") is None
        assert fs._resolve_path("/new_name.txt") is not None
