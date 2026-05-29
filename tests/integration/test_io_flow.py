# tests/integration/test_io_flow.py
"""
Integration tests for I/O and disk scheduling flow.
Reference: OS101_AgentPlan_v2.md Section 15
"""
import pytest
from core.config import DiskConfig
from core.interrupt import InterruptController
from core.event_bus import EventBus
from modules.io.disk import DiskScheduler
from modules.process.pcb import ProcessState, reset_pid_counter
from modules.process.queue_manager import QueueManager


@pytest.fixture(autouse=True)
def reset_pids():
    reset_pid_counter()
    yield
    reset_pid_counter()


class TestIOFlow:

    def test_disk_request_lifecycle(self):
        """Disk request is enqueued, selected, serviced, and head moves correctly."""
        cfg = DiskConfig(scheduling="fcfs", initial_head=50, cylinders=200)
        scheduler = DiskScheduler(cfg)

        scheduler.add_request(cylinder=100, pid=1, request_id="R1")
        assert len(scheduler.pending) == 1

        serviced = scheduler.service_next()
        assert serviced is not None
        assert serviced.cylinder == 100
        assert serviced.seek_distance == 50
        assert scheduler.current_head == 100
        assert len(scheduler.pending) == 0

    def test_multiple_requests_processed_in_order(self):
        """FCFS processes requests in arrival order."""
        cfg = DiskConfig(scheduling="fcfs", initial_head=0, cylinders=200)
        scheduler = DiskScheduler(cfg)

        scheduler.add_request(cylinder=50, pid=1, request_id="R1")
        scheduler.add_request(cylinder=100, pid=1, request_id="R2")
        scheduler.add_request(cylinder=30, pid=1, request_id="R3")

        order = []
        while scheduler.pending:
            r = scheduler.service_next()
            order.append(r.cylinder)

        assert order == [50, 100, 30]

    def test_seek_trace_populated(self):
        """Seek trace records every head movement."""
        cfg = DiskConfig(scheduling="fcfs", initial_head=10, cylinders=200)
        scheduler = DiskScheduler(cfg)

        scheduler.add_request(cylinder=50, pid=1, request_id="R1")
        scheduler.add_request(cylinder=20, pid=1, request_id="R2")

        while scheduler.pending:
            scheduler.service_next()

        trace = scheduler.get_seek_trace()
        assert len(trace) == 2
        assert trace[0]["from_cylinder"] == 10
        assert trace[0]["to_cylinder"] == 50
        assert trace[1]["from_cylinder"] == 50
        assert trace[1]["to_cylinder"] == 20

    def test_process_blocks_and_unblocks_on_io(self):
        """Process transitions RUNNING → BLOCKED on I/O, BLOCKED → READY on completion."""
        qm = QueueManager(InterruptController(), EventBus())
        qm.create_process("P1", burst_time=10, priority=5, memory_pages=4, arrival_time=0)
        pcb = list(qm.new_queue)[0]
        qm.admit(pcb)
        qm.dispatch(pcb, tick=1)
        assert pcb.state == ProcessState.RUNNING

        # Block on I/O
        qm.block(pcb, reason="io:disk0", tick=2)
        assert pcb.state == ProcessState.BLOCKED
        assert qm.running is None

        # Unblock
        qm.unblock(pcb, tick=5)
        assert pcb.state == ProcessState.READY
        assert len(qm.ready_queue) == 1

    def test_out_of_range_cylinder_raises(self):
        """Requesting a cylinder outside valid range raises ValueError."""
        cfg = DiskConfig(scheduling="fcfs", initial_head=50, cylinders=200)
        scheduler = DiskScheduler(cfg)

        with pytest.raises(ValueError):
            scheduler.add_request(cylinder=250, pid=1, request_id="R1")
