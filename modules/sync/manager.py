# modules/sync/manager.py
from __future__ import annotations
from typing import TYPE_CHECKING

from modules.sync.mutex import Mutex
from modules.process.pcb import ProcessState

if TYPE_CHECKING:
    from modules.process.queue_manager import QueueManager
    from modules.sync.deadlock import DeadlockDetector

class SyncManager:
    """
    Manages synchronization primitives and coordinates with the QueueManager 
    and DeadlockDetector to handle resource acquisition, blocking, and releasing.
    """

    def __init__(self, queue_manager: QueueManager, deadlock_detector: DeadlockDetector) -> None:
        self.queue_manager = queue_manager
        self.deadlock_detector = deadlock_detector
        self.mutexes: dict[str, Mutex] = {}

    def tick(self, tick: int) -> None:
        """Called every tick by the kernel."""
        pass

    def process_request(self, pid: int, action: str, resource_id: str, tick: int) -> None:
        """Process a sync request (acquire/release) from a process."""
        if resource_id not in self.mutexes:
            self.mutexes[resource_id] = Mutex(resource_id)
        
        mutex = self.mutexes[resource_id]

        if action == "acquire":
            # Record intention
            self.deadlock_detector.update("request", pid, resource_id)
            
            acquired = mutex.acquire(pid, tick)
            if acquired:
                # Successfully locked
                self.deadlock_detector.update("allocate", pid, resource_id)
            else:
                # Blocked — find the PCB and block it (BUG-10 fix: use enum, not string)
                pcb = next((p for p in self.queue_manager.get_all_processes() if p.pid == pid), None)
                if pcb and pcb.state == ProcessState.RUNNING:
                    self.queue_manager.block(pcb, f"mutex_wait_{resource_id}", tick)
        
        elif action == "release":
            # Release intention
            self.deadlock_detector.update("release", pid, resource_id)
            
            try:
                woken_pid = mutex.release(pid, tick)
            except PermissionError:
                return  # Ignoring if trying to release something not owned
            
            if woken_pid is not None:
                # Mutex was handed to waiting process
                self.deadlock_detector.update("allocate", woken_pid, resource_id)
                woken_pcb = next((p for p in self.queue_manager.get_all_processes() if p.pid == woken_pid), None)
                if woken_pcb and woken_pcb.state == ProcessState.BLOCKED:
                    self.queue_manager.unblock(woken_pcb, tick)
