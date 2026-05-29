# tests/unit/test_disk_scheduling.py
"""
Unit tests for disk_scheduling.
Reference: OS101_AgentPlan_v2.md Section 15
"""
import pytest
from core.config import DiskConfig
from modules.io.disk import DiskScheduler
from modules.process.pcb import reset_pid_counter


@pytest.fixture(autouse=True)
def reset_pids():
    """Ensure PIDs are deterministic across tests."""
    reset_pid_counter()
    yield
    reset_pid_counter()


class TestDiskScheduler:

    def test_fcfs_seek_sequence_matches_textbook(self):
        # Arrange - Textbook initial head: 53, requests: 98, 183, 37, 122, 14, 124, 65, 67
        cfg = DiskConfig(scheduling="fcfs", initial_head=53, cylinders=200)
        scheduler = DiskScheduler(cfg)
        requests = [98, 183, 37, 122, 14, 124, 65, 67]
        for idx, cyl in enumerate(requests):
            scheduler.add_request(cylinder=cyl, pid=1, request_id=f"R{idx}")
        # Act
        while scheduler.pending:
            scheduler.service_next()
        # Assert
        assert scheduler.total_seek_distance == 640

    def test_sstf_seek_sequence_matches_textbook(self):
        # Arrange - Textbook initial head: 53, requests: 98, 183, 37, 122, 14, 124, 65, 67
        cfg = DiskConfig(scheduling="sstf", initial_head=53, cylinders=200)
        scheduler = DiskScheduler(cfg)
        requests = [98, 183, 37, 122, 14, 124, 65, 67]
        for idx, cyl in enumerate(requests):
            scheduler.add_request(cylinder=cyl, pid=1, request_id=f"R{idx}")
        # Act
        while scheduler.pending:
            scheduler.service_next()
        # Assert
        assert scheduler.total_seek_distance == 236

    def test_scan_direction_up_correct(self):
        # Arrange
        cfg = DiskConfig(scheduling="scan", initial_head=50, cylinders=200)
        scheduler = DiskScheduler(cfg)
        scheduler.direction = 1
        scheduler.add_request(cylinder=60, pid=1, request_id="R1")
        scheduler.add_request(cylinder=40, pid=1, request_id="R2")
        # Act
        r1 = scheduler.service_next()
        r2 = scheduler.service_next()
        # Assert
        assert r1 is not None and r1.cylinder == 60
        assert r2 is not None and r2.cylinder == 40
        # Head sweeps to 199 then back to 40
        assert scheduler.total_seek_distance == (199 - 50) + (199 - 40)

    def test_cscan_wrap_around_correct(self):
        # Arrange
        cfg = DiskConfig(scheduling="c-scan", initial_head=50, cylinders=200)
        scheduler = DiskScheduler(cfg)
        scheduler.add_request(cylinder=60, pid=1, request_id="R1")
        scheduler.add_request(cylinder=40, pid=1, request_id="R2")
        # Act
        r1 = scheduler.service_next()
        r2 = scheduler.service_next()
        # Assert
        assert r1 is not None and r1.cylinder == 60
        assert r2 is not None and r2.cylinder == 40
        # 50->60 (10), 60->199 (139), 199->0 (199), 0->40 (40)
        assert scheduler.total_seek_distance == 10 + 139 + 199 + 40

    def test_look_does_not_seek_to_end(self):
        # Arrange
        cfg = DiskConfig(scheduling="look", initial_head=50, cylinders=200)
        scheduler = DiskScheduler(cfg)
        scheduler.direction = 1
        scheduler.add_request(cylinder=60, pid=1, request_id="R1")
        scheduler.add_request(cylinder=40, pid=1, request_id="R2")
        # Act
        r1 = scheduler.service_next()
        r2 = scheduler.service_next()
        # Assert
        assert r1 is not None and r1.cylinder == 60
        assert r2 is not None and r2.cylinder == 40
        # 50->60 (10), reverses directly at 60 -> 40 (20) -> total 30
        assert scheduler.total_seek_distance == 30

    def test_clook_wrap_around_to_lowest_request(self):
        # Arrange
        cfg = DiskConfig(scheduling="c-look", initial_head=50, cylinders=200)
        scheduler = DiskScheduler(cfg)
        scheduler.add_request(cylinder=60, pid=1, request_id="R1")
        scheduler.add_request(cylinder=40, pid=1, request_id="R2")
        # Act
        r1 = scheduler.service_next()
        r2 = scheduler.service_next()
        # Assert
        assert r1 is not None and r1.cylinder == 60
        assert r2 is not None and r2.cylinder == 40
        # 50->60 (10), directly wraps to lowest request 40 (abs(40-60)=20) -> total 30
        assert scheduler.total_seek_distance == 30
