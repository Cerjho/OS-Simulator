# modules/io/io_manager.py
# Phase: 5 — I/O & Device Management
# Owner: IO Agent
"""
I/O Subsystem Manager.
Orchestrates device controllers and disk scheduling engine.
Full implementation spec: OS101_AgentPlan_v2.md Section 10
"""
from __future__ import annotations
from typing import Any, TYPE_CHECKING

from modules.io.disk import DiskScheduler
from modules.process.pcb import IORequest

if TYPE_CHECKING:
    from core.config import DiskConfig
    from modules.io.device import Device


class IOManager:
    """
    Central I/O subsystem manager owning registered devices and the disk scheduler.

    Responsibilities:
      - Accepts I/O requests and routes them to appropriate target devices.
      - Enqueues cylinder seek requests to the DiskScheduler.
      - Advances all devices and disk scheduler on clock ticks.
      - Provides subsystem state snapshots for logging/UI.
    """

    def __init__(self, disk_config: DiskConfig, devices: dict[str, Device] | None = None) -> None:
        self.disk_scheduler: DiskScheduler = DiskScheduler(disk_config)
        self.devices: dict[str, Device] = devices if devices is not None else {}

        self._current_tick: int = 0
        self._req_counter: int = 0

    def submit_io(self, pid: int, device_id: str, cylinder: int, operation: str) -> None:
        """
        Submit an I/O request from a process.
        Routes to the target device queue and enqueues to DiskScheduler if cylinder >= 0.
        """
        self._req_counter += 1
        req_id = f"io-{self._req_counter}"

        # Route to registered device controller if available
        if device_id in self.devices:
            req = IORequest(
                device_id=device_id,
                operation=operation,
                size_blocks=1,
                requested_at_tick=self._current_tick,
                pid=pid,
                cylinder=cylinder,
            )
            self.devices[device_id].submit_request(req)

        # Enqueue to disk scheduler to simulate cylinder positioning
        if cylinder >= 0:
            self.disk_scheduler.add_request(cylinder=cylinder, pid=pid, request_id=req_id)

    def tick(self, current_tick: int) -> None:
        """Advance I/O subsystem state by one clock tick."""
        self._current_tick = current_tick

        # Advance disk scheduler state
        self.disk_scheduler.tick(current_tick)
        # Service next disk request to maintain head/distance tracking progress
        if self.disk_scheduler.pending:
            self.disk_scheduler.service_next()

        # Advance all registered device controllers
        for device in self.devices.values():
            device.tick(current_tick)

    def get_state_snapshot(self) -> dict[str, Any]:
        """Returns a snapshot dictionary representing complete I/O subsystem state."""
        return {
            "disk_scheduler": {
                "current_head": self.disk_scheduler.current_head,
                "direction": self.disk_scheduler.direction,
                "pending_count": len(self.disk_scheduler.pending),
                "total_seek_distance": self.disk_scheduler.total_seek_distance,
                "algorithm": self.disk_scheduler.algorithm,
                "seek_trace": self.disk_scheduler.get_seek_trace(),
            },
            "devices": {
                dev_id: {
                    "type": dev.device_type.value,
                    "status": dev.status,
                    "queue_length": len(dev.request_queue),
                }
                for dev_id, dev in self.devices.items()
            },
            "current_tick": self._current_tick,
            "total_requests": self._req_counter,
        }
