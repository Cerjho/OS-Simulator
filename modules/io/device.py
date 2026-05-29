# modules/io/device.py
# Phase: 5 — I/O & Device Management
# Owner: IO Agent
"""
Device representation and I/O submission interface.
Full implementation spec: OS101_AgentPlan_v2.md Section 10
"""
from __future__ import annotations
from enum import Enum
from typing import TYPE_CHECKING

from core.interrupt import InterruptController, InterruptType
from modules.process.pcb import IORequest

if TYPE_CHECKING:
    from core.event_bus import EventBus


class DeviceType(Enum):
    """Supported device types."""
    HDD      = "hdd"
    SSD      = "ssd"
    KEYBOARD = "keyboard"
    TERMINAL = "terminal"


class Device:
    """
    Base class representing an I/O device.

    Attributes:
      device_id: Unique identifier string.
      device_type: DeviceType enum value.
      status: String indicating 'idle' or 'busy'.
      request_queue: List of pending IORequests.
    """

    def __init__(
        self,
        device_id: str,
        device_type: DeviceType,
        interrupt_controller: InterruptController,
        event_bus: EventBus,
    ) -> None:
        self.device_id: str = device_id
        self.device_type: DeviceType = device_type
        self._interrupt_controller: InterruptController = interrupt_controller
        self._event_bus: EventBus = event_bus

        self.request_queue: list[IORequest] = []
        self._current_request: IORequest | None = None
        self._remaining_ticks: int = 0
        self._current_tick: int = 0

    @property
    def status(self) -> str:
        """Returns 'busy' if servicing a request, otherwise 'idle'."""
        return "busy" if self._current_request is not None else "idle"

    def submit_request(self, req: IORequest) -> None:
        """Enqueue an I/O request for this device."""
        self.request_queue.append(req)
        # Publish event if available
        if hasattr(self._event_bus, "publish"):
            self._event_bus.publish(
                "IO_REQUEST",
                {"device_id": self.device_id, "operation": req.operation},
                tick=self._current_tick,
                source=f"device:{self.device_id}",
            )

    def tick(self, current_tick: int) -> None:
        """Advance device state by one simulation tick."""
        self._current_tick = current_tick

        # If idle and requests are pending, start servicing the next request
        if self._current_request is None and self.request_queue:
            self._current_request = self.request_queue.pop(0)
            # Use size_blocks as service duration (default to 1 if <= 0)
            self._remaining_ticks = max(1, self._current_request.size_blocks)

        # If currently servicing a request, decrement its remaining ticks
        if self._current_request is not None:
            self._remaining_ticks -= 1
            if self._remaining_ticks <= 0:
                self.complete_request()

    def complete_request(self) -> None:
        """
        Finish servicing the current request and raise IO_COMPLETE interrupt.
        Safe to call manually or automatically via tick().
        """
        req = self._current_request
        if req is None:
            # If called manually without an active request but queue has items, pop one
            if self.request_queue:
                req = self.request_queue.pop(0)
            else:
                return

        req.completed_at_tick = self._current_tick
        pid = req.pid  # BUG-39 fix: use proper field instead of defensive getattr

        # Raise IO_COMPLETE interrupt
        self._interrupt_controller.raise_interrupt(
            InterruptType.IO_COMPLETE,
            pid=pid,
            data={"device_id": self.device_id, "operation": req.operation, "size_blocks": req.size_blocks},
            current_tick=self._current_tick,
        )

        # Publish event
        if hasattr(self._event_bus, "publish"):
            self._event_bus.publish(
                "IO_COMPLETE",
                {"device_id": self.device_id, "pid": pid},
                tick=self._current_tick,
                source=f"device:{self.device_id}",
            )

        self._current_request = None
