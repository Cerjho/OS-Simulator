# tests/unit/test_fat.py
"""
Unit tests for fat.
Reference: OS101_AgentPlan_v2.md Section 15
"""
import pytest
from core.config import FilesystemConfig
from modules.filesystem.fat import FATFileSystem, FAT_FREE, FAT_BAD
from modules.process.pcb import reset_pid_counter


@pytest.fixture(autouse=True)
def reset_pids():
    """Ensure PIDs are deterministic across tests."""
    reset_pid_counter()
    yield
    reset_pid_counter()


class TestFATFileSystem:

    def test_block_0_is_reserved(self):
        # Arrange & Act
        fs = FATFileSystem(FilesystemConfig())
        # Assert
        assert fs._fat[0] == FAT_BAD

    def test_create_file_adds_dir_entry(self):
        # Arrange
        fs = FATFileSystem(FilesystemConfig())
        # Act
        result = fs.create("/test.txt")
        # Assert
        assert result is True
        assert "/test.txt" in fs._dir_entries

    def test_create_duplicate_returns_false(self):
        # Arrange
        fs = FATFileSystem(FilesystemConfig())
        fs.create("/test.txt")
        # Act
        result = fs.create("/test.txt")
        # Assert
        assert result is False

    def test_open_returns_valid_fd(self):
        # Arrange
        fs = FATFileSystem(FilesystemConfig())
        fs.create("/test.txt")
        # Act
        fd = fs.open("/test.txt", "r")
        # Assert
        assert fd is not None
        assert fd >= 3

    def test_write_and_read_roundtrip(self):
        # Arrange
        fs = FATFileSystem(FilesystemConfig())
        fs.create("/test.txt")
        fd_w = fs.open("/test.txt", "w")
        data = b"hello world"
        # Act
        fs.write(fd_w, data)
        fs.close(fd_w)
        fd_r = fs.open("/test.txt", "r")
        read_data = fs.read(fd_r, len(data))
        fs.close(fd_r)
        # Assert
        assert read_data == data

    def test_delete_removes_file(self):
        # Arrange
        fs = FATFileSystem(FilesystemConfig())
        fs.create("/test.txt")
        # Act
        result = fs.delete("/test.txt")
        # Assert
        assert result is True
        assert "/test.txt" not in fs._dir_entries

    def test_stat_returns_file_info(self):
        # Arrange
        fs = FATFileSystem(FilesystemConfig())
        fs.create("/test.txt")
        # Act
        info = fs.stat("/test.txt")
        # Assert
        assert info is not None
        assert info["name"] == "test.txt"
        assert info["size_bytes"] == 0

    def test_metrics_tracks_operations(self):
        # Arrange
        fs = FATFileSystem(FilesystemConfig())
        fs.create("/a.txt")
        fs.create("/b.txt")
        fd = fs.open("/a.txt", "w")
        fs.write(fd, b"data")
        fs.close(fd)
        fd2 = fs.open("/a.txt", "r")
        fs.read(fd2, 100)
        fs.close(fd2)
        # Act
        metrics = fs.get_metrics()
        # Assert
        assert metrics["ops_count"]["creates"] == 2
        assert metrics["ops_count"]["writes"] >= 1
        assert metrics["ops_count"]["reads"] >= 1

    def test_fat_entries_all_free_initially(self):
        # Arrange & Act
        fs = FATFileSystem(FilesystemConfig(total_blocks=32))
        # Assert — block 0 reserved, rest free
        for i in range(1, 32):
            assert fs._fat[i] == FAT_FREE
