# tests/unit/test_disk_full.py
"""Comprehensive disk scheduling tests for 100% coverage."""
import pytest
from modules.io.disk import DiskScheduler, DiskRequest
from core.config import DiskConfig


def _cfg(**kw):
    d = {"cylinders": 200, "initial_head": 53, "scheduling": "fcfs",
         "seek_time_per_track": 1}
    d.update(kw)
    return DiskConfig(**d)


def _add_requests(ds, cyls):
    for i, c in enumerate(cyls):
        ds.add_request(c, pid=1, request_id=f"r{i}")


class TestDiskRequestValidation:
    def test_out_of_bounds_raises(self):
        ds = DiskScheduler(_cfg())
        with pytest.raises(ValueError):
            ds.add_request(200, pid=1, request_id="bad")
        with pytest.raises(ValueError):
            ds.add_request(-1, pid=1, request_id="bad2")


class TestSCAN:
    def test_scan_ascending_ahead(self):
        ds = DiskScheduler(_cfg(scheduling="scan"))
        _add_requests(ds, [65, 67, 98, 183])
        r = ds.service_next()
        assert r.cylinder == 65

    def test_scan_ascending_reverses_at_boundary(self):
        ds = DiskScheduler(_cfg(scheduling="scan", initial_head=150))
        _add_requests(ds, [30, 180])
        r1 = ds.service_next()
        assert r1.cylinder == 180
        r2 = ds.service_next()
        assert r2.cylinder == 30
        assert ds.direction == -1

    def test_scan_descending_behind(self):
        ds = DiskScheduler(_cfg(scheduling="scan", initial_head=100))
        ds.direction = -1
        _add_requests(ds, [50, 30, 150])
        r = ds.service_next()
        assert r.cylinder <= 100

    def test_scan_descending_reverses(self):
        ds = DiskScheduler(_cfg(scheduling="scan", initial_head=50))
        ds.direction = -1
        _add_requests(ds, [150])
        r = ds.service_next()
        assert r.cylinder == 150
        assert ds.direction == 1


class TestCSCAN:
    def test_cscan_ahead(self):
        ds = DiskScheduler(_cfg(scheduling="c-scan", initial_head=50))
        _add_requests(ds, [60, 100, 30])
        r = ds.service_next()
        assert r.cylinder == 60

    def test_cscan_wraps_around(self):
        ds = DiskScheduler(_cfg(scheduling="c-scan", initial_head=180))
        _add_requests(ds, [10, 30])
        r = ds.service_next()
        assert r.cylinder == 10
        assert ds.total_seek_distance > 0


class TestLOOK:
    def test_look_ascending(self):
        ds = DiskScheduler(_cfg(scheduling="look", initial_head=50))
        _add_requests(ds, [60, 100, 30])
        r = ds.service_next()
        assert r.cylinder == 60
        assert ds.direction == 1

    def test_look_reverses(self):
        ds = DiskScheduler(_cfg(scheduling="look", initial_head=100))
        _add_requests(ds, [30, 50])
        r = ds.service_next()
        assert r.cylinder in (30, 50)

    def test_look_descending(self):
        ds = DiskScheduler(_cfg(scheduling="look", initial_head=100))
        ds.direction = -1
        _add_requests(ds, [50, 30, 150])
        r = ds.service_next()
        assert r.cylinder <= 100

    def test_look_descending_reverses(self):
        ds = DiskScheduler(_cfg(scheduling="look", initial_head=20))
        ds.direction = -1
        _add_requests(ds, [100])
        r = ds.service_next()
        assert r.cylinder == 100


class TestCLOOK:
    def test_clook_ahead(self):
        ds = DiskScheduler(_cfg(scheduling="c-look", initial_head=50))
        _add_requests(ds, [60, 100, 30])
        r = ds.service_next()
        assert r.cylinder == 60

    def test_clook_wraps(self):
        ds = DiskScheduler(_cfg(scheduling="c-look", initial_head=120))
        _add_requests(ds, [30, 50])
        r = ds.service_next()
        assert r.cylinder == 30


class TestEmptyQueue:
    def test_select_next_empty(self):
        ds = DiskScheduler(_cfg())
        assert ds.select_next() is None

    def test_service_next_empty(self):
        ds = DiskScheduler(_cfg())
        assert ds.service_next() is None


class TestSeekTrace:
    def test_get_seek_trace(self):
        ds = DiskScheduler(_cfg(scheduling="fcfs"))
        _add_requests(ds, [100])
        ds.service_next()
        trace = ds.get_seek_trace()
        assert len(trace) == 1
        assert "from_cylinder" in trace[0]

    def test_tick(self):
        ds = DiskScheduler(_cfg())
        ds.tick(42)
        assert ds._current_tick == 42
