# tests/unit/test_pcb.py
"""
Unit tests for pcb.
Reference: OS101_AgentPlan_v2.md Section 15
"""
import pytest
from modules.process.pcb import PCB, ProcessState, StateTransitionError, reset_pid_counter


@pytest.fixture(autouse=True)
def reset_pids():
    """Ensure PIDs are deterministic across tests."""
    reset_pid_counter()
    yield
    reset_pid_counter()


class TestPCB:

    def test_pid_auto_assigned(self):
        # Arrange & Act
        pcb1 = PCB(name="P1", burst_time=5)
        pcb2 = PCB(name="P2", burst_time=5)
        # Assert
        assert pcb1.pid == 1, f"Expected 1, got {pcb1.pid}"
        assert pcb2.pid == 2, f"Expected 2, got {pcb2.pid}"

    def test_remaining_burst_equals_burst_time_at_creation(self):
        # Arrange & Act
        pcb = PCB(name="P1", burst_time=12)
        # Assert
        assert pcb.remaining_burst == 12, f"Expected 12, got {pcb.remaining_burst}"

    def test_page_table_initialized_with_correct_length(self):
        # Arrange & Act
        pcb = PCB(name="P1", burst_time=5, memory_pages=6)
        # Assert
        assert len(pcb.page_table) == 6, f"Expected 6, got {len(pcb.page_table)}"

    def test_new_to_ready_valid(self):
        # Arrange
        pcb = PCB(name="P1", burst_time=5)
        # Act
        pcb.transition_to(ProcessState.READY, tick=1)
        # Assert
        assert pcb.state == ProcessState.READY

    def test_ready_to_running_valid(self):
        # Arrange
        pcb = PCB(name="P1", burst_time=5)
        pcb.transition_to(ProcessState.READY, tick=1)
        # Act
        pcb.transition_to(ProcessState.RUNNING, tick=2)
        # Assert
        assert pcb.state == ProcessState.RUNNING

    def test_running_to_blocked_valid(self):
        # Arrange
        pcb = PCB(name="P1", burst_time=5)
        pcb.transition_to(ProcessState.READY, tick=1)
        pcb.transition_to(ProcessState.RUNNING, tick=2)
        # Act
        pcb.transition_to(ProcessState.BLOCKED, tick=3)
        # Assert
        assert pcb.state == ProcessState.BLOCKED

    def test_new_to_terminated_invalid_raises(self):
        # Arrange
        pcb = PCB(name="P1", burst_time=5)
        # Act & Assert
        with pytest.raises(StateTransitionError):
            pcb.transition_to(ProcessState.TERMINATED, tick=1)

    def test_ready_to_terminated_invalid_raises(self):
        # Arrange
        pcb = PCB(name="P1", burst_time=5)
        pcb.transition_to(ProcessState.READY, tick=1)
        # Act & Assert
        with pytest.raises(StateTransitionError):
            pcb.transition_to(ProcessState.TERMINATED, tick=2)

    def test_response_time_set_on_first_dispatch(self):
        # Arrange
        pcb = PCB(name="P1", burst_time=5, arrival_time=2)
        pcb.transition_to(ProcessState.READY, tick=3)
        # Act
        pcb.transition_to(ProcessState.RUNNING, tick=6)
        # Assert
        assert pcb.response_time == 4, f"Expected 4, got {pcb.response_time}"

    def test_turnaround_set_on_termination(self):
        # Arrange
        pcb = PCB(name="P1", burst_time=5, arrival_time=1)
        pcb.transition_to(ProcessState.READY, tick=2)
        pcb.transition_to(ProcessState.RUNNING, tick=3)
        # Act
        pcb.transition_to(ProcessState.TERMINATED, tick=10)
        # Assert
        assert pcb.turnaround_time == 9, f"Expected 9, got {pcb.turnaround_time}"

    def test_to_dict_contains_required_keys(self):
        # Arrange
        pcb = PCB(name="P1", burst_time=5)
        # Act
        d = pcb.to_dict()
        # Assert
        required = ["pid", "name", "state", "priority", "burst_time", "remaining_burst", "waiting_time", "turnaround_time", "response_time", "arrival_time", "mlfq_queue_level"]
        for k in required:
            assert k in d, f"Missing key {k}"

    def test_reset_pid_counter_gives_deterministic_pids(self):
        # Arrange & Act
        pcb1 = PCB(name="P1", burst_time=5)
        reset_pid_counter()
        pcb2 = PCB(name="P2", burst_time=5)
        # Assert
        assert pcb1.pid == 1
        assert pcb2.pid == 1
