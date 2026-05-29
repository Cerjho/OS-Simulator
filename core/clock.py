# core/clock.py
from __future__ import annotations
import asyncio
import time
from typing import Callable, Awaitable


class SimulationClock:
    """
    Manages discrete simulation time.

    Rules:
      - tick_count is the ONLY measure of simulated time.
      - wall_clock_ms is for pacing only; never use it for logic.
      - The tick loop fires callbacks in registration order.
    """

    def __init__(self, tick_rate_ms: int = 100, max_ticks: int = 10_000) -> None:
        self.tick_count: int = 0
        self.tick_rate_ms: int = tick_rate_ms
        self.max_ticks: int = max_ticks
        self._paused: bool = False
        self._running: bool = False
        self._speed_multiplier: float = 1.0
        self._tick_callbacks: list[Callable[[int], Awaitable[None]]] = []
        self._wall_start: float = 0.0

    # ── Registration ──────────────────────────────────────────────────────────

    def on_tick(self, callback: Callable[[int], Awaitable[None]]) -> None:
        """Register an async function called every tick with current tick_count."""
        self._tick_callbacks.append(callback)

    # ── Control ───────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Start the tick loop. Returns when max_ticks reached or stop() called."""
        self._running = True
        self._wall_start = time.monotonic()
        while self._running and self.tick_count < self.max_ticks:
            if not self._paused:
                await self._fire_tick()
            sleep_s = (self.tick_rate_ms / 1000.0) / self._speed_multiplier
            await asyncio.sleep(sleep_s)

    def stop(self) -> None:
        """Stop the tick loop after current tick completes."""
        self._running = False

    def pause(self) -> None:
        """Suspend ticking. tick_count does NOT advance while paused."""
        self._paused = True

    def resume(self) -> None:
        """Resume ticking."""
        self._paused = False

    def set_speed(self, multiplier: float) -> None:
        """Set speed multiplier. 2.0 = twice as fast. Must be > 0."""
        if multiplier <= 0:
            raise ValueError(f"Speed multiplier must be > 0, got {multiplier}")
        self._speed_multiplier = multiplier

    def reset(self) -> None:
        """Reset to tick 0. Simulation must be stopped first."""
        if self._running:
            raise RuntimeError("Cannot reset a running simulation. Call stop() first.")
        self.tick_count = 0
        self._paused = False

    async def step(self) -> None:
        """Advance exactly one tick regardless of paused state. For debugging."""
        await self._fire_tick()

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _fire_tick(self) -> None:
        """Increment tick and invoke all registered callbacks in order."""
        self.tick_count += 1
        for callback in self._tick_callbacks:
            await callback(self.tick_count)

    @property
    def wall_clock_ms(self) -> float:
        return (time.monotonic() - self._wall_start) * 1000.0

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def is_running(self) -> bool:
        return self._running
