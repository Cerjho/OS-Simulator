# tests/unit/test_clock.py
"""
Unit tests for clock.
Reference: OS101_AgentPlan_v2.md Section 15
"""
import asyncio
import pytest
from core.clock import SimulationClock
from modules.process.pcb import reset_pid_counter


@pytest.fixture(autouse=True)
def reset_pids():
    """Ensure PIDs are deterministic across tests."""
    reset_pid_counter()
    yield
    reset_pid_counter()


class TestSimulationClock:

    @pytest.mark.asyncio
    async def test_tick_advances_monotonically(self):
        # Arrange
        clock = SimulationClock()
        # Act
        await clock.step()
        t1 = clock.tick_count
        await clock.step()
        t2 = clock.tick_count
        # Assert
        assert t2 > t1, f"Expected {t2} > {t1}"

    @pytest.mark.asyncio
    async def test_tick_sequence_is_1_2_3(self):
        # Arrange
        clock = SimulationClock()
        seq = []
        async def cb(t):
            seq.append(t)
        clock.on_tick(cb)
        # Act
        await clock.step()
        await clock.step()
        await clock.step()
        # Assert
        assert seq == [1, 2, 3], f"Expected [1, 2, 3], got {seq}"

    @pytest.mark.asyncio
    async def test_pause_stops_tick_advance(self):
        # Arrange
        clock = SimulationClock(tick_rate_ms=1, max_ticks=5)
        clock.pause()
        # Act
        # Start background task; clock loop will not increment tick while paused
        task = asyncio.create_task(clock.start())
        await asyncio.sleep(0.02)
        assert clock.tick_count == 0, f"Expected 0, got {clock.tick_count}"
        clock.stop()
        await task

    @pytest.mark.asyncio
    async def test_resume_after_pause_continues(self):
        # Arrange
        clock = SimulationClock(tick_rate_ms=1, max_ticks=5)
        clock.pause()
        task = asyncio.create_task(clock.start())
        await asyncio.sleep(0.01)
        assert clock.tick_count == 0
        # Act
        clock.resume()
        await task
        # Assert
        assert clock.tick_count == 5, f"Expected 5, got {clock.tick_count}"

    @pytest.mark.asyncio
    async def test_reset_requires_stopped_simulation(self):
        # Arrange
        clock = SimulationClock(tick_rate_ms=1, max_ticks=10)
        task = asyncio.create_task(clock.start())
        await asyncio.sleep(0.002)
        # Act & Assert
        with pytest.raises(RuntimeError):
            clock.reset()
        clock.stop()
        await task
        clock.reset()
        assert clock.tick_count == 0

    def test_set_speed_zero_raises_error(self):
        # Arrange
        clock = SimulationClock()
        # Act & Assert
        with pytest.raises(ValueError):
            clock.set_speed(0.0)

    @pytest.mark.asyncio
    async def test_max_ticks_stops_loop(self):
        # Arrange
        clock = SimulationClock(tick_rate_ms=1, max_ticks=4)
        # Act
        await clock.start()
        # Assert
        assert clock.tick_count == 4, f"Expected 4, got {clock.tick_count}"

    @pytest.mark.asyncio
    async def test_step_advances_exactly_one_tick(self):
        # Arrange
        clock = SimulationClock()
        # Act
        await clock.step()
        # Assert
        assert clock.tick_count == 1, f"Expected 1, got {clock.tick_count}"
