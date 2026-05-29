# core/kernel.py
from __future__ import annotations
import random
from typing import Any
from core.config import SimConfig, load_config
from core.clock import SimulationClock
from core.interrupt import InterruptController, InterruptType
from core.event_bus import EventBus
from core.metrics import MetricsCollector
from modules.process.pcb import ProcessState


class Kernel:
    """
    Central orchestrator. Owns ALL subsystem references.

    Lifecycle:
      kernel = Kernel()             # creates config + subsystems
      await kernel.start()          # starts tick loop (blocks until done)
      kernel.stop()                 # signals tick loop to stop
      kernel.pause() / resume()
      kernel.inject_process(spec)   # add process mid-simulation
      kernel.get_state() -> dict    # full serializable snapshot

    Tick dispatch order (MUST be maintained exactly):
      1. interrupt_controller.handle_all()
      2. io_manager.tick(tick)
      3. scheduler.tick(tick)
      4. process_executor.tick(tick)
      5. memory_manager.tick(tick)
      6. filesystem.tick(tick)
      7. sync_manager.tick(tick)
      8. deadlock_detector.tick(tick)
      9. metrics_collector.tick(tick)
      10. event_bus.publish("TICK", {...}, tick)
    """

    def __init__(self, config_path: str = "simulation.yaml") -> None:
        self.config: SimConfig = load_config(config_path)
        self.clock: SimulationClock = SimulationClock(
            tick_rate_ms=self.config.clock.tick_rate_ms,
            max_ticks=self.config.clock.max_ticks,
        )
        self.interrupt_controller: InterruptController = InterruptController()
        self.event_bus: EventBus = EventBus()

        # Subsystem references — assigned during _init_subsystems()
        self.process_manager = None
        self.memory_manager = None
        self.filesystem = None
        self.io_manager = None
        self.scheduler = None
        self.sync_manager = None
        self.deadlock_detector = None
        self.metrics_collector: MetricsCollector | None = None
        self._initialized: bool = False
        self._spawn_counter: int = 0  # Auto-spawn naming counter
        self._rng: random.Random = random.Random(42)  # Deterministic RNG for reproducibility
        self._freed_pids: set[int] = set()  # BUG-46 fix: init in __init__ not via hasattr

        # Register the kernel's own tick callback
        self.clock.on_tick(self._on_tick)

    async def _init_subsystems(self) -> None:
        """
        Instantiate all subsystem managers in dependency order.
        Called once before start().
        Import here (not at module top) to avoid circular imports.
        """
        # BUG-24 fix: Reset PID counter for fresh simulation runs
        from modules.process.pcb import reset_pid_counter
        reset_pid_counter()

        from modules.process.queue_manager import QueueManager
        from modules.process.scheduler import create_scheduler
        from modules.memory.paging import VirtualMemoryManager
        from modules.filesystem.vfs import VirtualFileSystem
        from modules.io.io_manager import IOManager
        from modules.sync.deadlock import DeadlockDetector
        from modules.sync.manager import SyncManager

        self.process_manager = QueueManager(self.interrupt_controller, self.event_bus)
        self.scheduler = create_scheduler(self.config.scheduler)
        self.memory_manager = VirtualMemoryManager(self.config.memory, self.interrupt_controller)
        self.filesystem = VirtualFileSystem(self.config.filesystem)
        self.io_manager = IOManager(self.config.disk)
        self.deadlock_detector = DeadlockDetector(self.config.deadlock, self.event_bus)
        self.sync_manager = SyncManager(self.process_manager, self.deadlock_detector)

        # Metrics collector — bind subsystem references for live telemetry
        self.metrics_collector = MetricsCollector()
        self.metrics_collector.bind(
            process_manager=self.process_manager,
            memory_manager=self.memory_manager,
        )

        # Seed initial processes from config.processes.initial_load
        self._seed_initial_processes()

        # Register interrupt handlers
        self.interrupt_controller.register_handler(
            InterruptType.TIMER, self.process_manager.handle_timer_interrupt
        )
        self.interrupt_controller.register_handler(
            InterruptType.IO_COMPLETE, self.process_manager.handle_io_complete
        )
        self.interrupt_controller.register_handler(
            InterruptType.PAGE_FAULT, self.memory_manager.handle_page_fault
        )
        self.interrupt_controller.register_handler(
            InterruptType.SYSCALL, self.process_manager.handle_syscall
        )

    async def start(self) -> None:
        """Initialize subsystems and start the tick loop."""
        if self.clock.is_running:
            return  # Prevent duplicate tick loops
        if not self._initialized:
            await self._init_subsystems()
            self._initialized = True
        self.event_bus.publish("SIMULATION_STARTED", {"tick": 0}, tick=0, source="kernel")
        await self.clock.start()

    def stop(self) -> None:
        self.clock.stop()
        self.event_bus.publish("SIMULATION_STOPPED", {"tick": self.clock.tick_count},
                               tick=self.clock.tick_count, source="kernel")

    def pause(self) -> None:
        self.clock.pause()
        self.event_bus.publish("SIMULATION_PAUSED", {"tick": self.clock.tick_count},
                               tick=self.clock.tick_count, source="kernel")

    def resume(self) -> None:
        self.clock.resume()
        self.event_bus.publish("SIMULATION_RESUMED", {"tick": self.clock.tick_count},
                               tick=self.clock.tick_count, source="kernel")

    async def step(self) -> None:
        """Advance exactly one tick. For debugging/testing."""
        # RT-BUG-01 fix: Ensure subsystems are initialized before stepping
        if not self._initialized:
            await self._init_subsystems()
            self._initialized = True
        await self.clock.step()

    def inject_process(self, spec: dict[str, Any]) -> int:
        """
        Create a new process mid-simulation from a spec dict.
        spec keys: name (str), burst (int), priority (int), memory_pages (int)
        Returns the new process's PID.
        """
        # RT-BUG-02 fix: Guard against inject before subsystem init
        if self.process_manager is None:
            raise RuntimeError("Cannot inject process before simulation is started. Call start() or step() first.")
        return self.process_manager.create_process(
            name=spec["name"],
            burst_time=spec["burst"],
            priority=spec.get("priority", 5),
            memory_pages=spec.get("memory_pages", 4),
            arrival_time=self.clock.tick_count,
            sync_requests=spec.get("sync_requests", []),
        )

    def _seed_initial_processes(self) -> None:
        """Create initial_load processes at tick 0 to seed the simulation."""
        if self.process_manager is None:
            return
        count = self.config.processes.initial_load
        for i in range(count):
            self._spawn_counter += 1
            burst = self._rng.randint(5, 20)
            priority = self._rng.randint(1, 10)
            pages = self._rng.randint(2, 8)
            self.process_manager.create_process(
                name=f"Auto-P{self._spawn_counter}",
                burst_time=burst,
                priority=priority,
                memory_pages=pages,
                arrival_time=0,
            )

    def _auto_spawn_process(self, tick: int) -> None:
        """Spawn a new random process periodically per config.processes.spawn_interval_ticks."""
        if not self.config.processes.auto_spawn:
            return
        if self.process_manager is None:
            return
        if tick <= 0 or tick % self.config.processes.spawn_interval_ticks != 0:
            return

        self._spawn_counter += 1
        burst = self._rng.randint(4, 18)
        priority = self._rng.randint(1, 10)
        pages = self._rng.randint(2, 6)
        pid = self.process_manager.create_process(
            name=f"Auto-P{self._spawn_counter}",
            burst_time=burst,
            priority=priority,
            memory_pages=pages,
            arrival_time=tick,
        )

        # Submit random disk I/O to keep DiskSeekTrace alive
        if self.io_manager:
            cylinders = max(self.config.disk.cylinders, 1)
            for _ in range(self._rng.randint(1, 3)):
                cyl = self._rng.randint(0, cylinders - 1)
                self.io_manager.submit_io(
                    pid=pid, device_id="disk0", cylinder=cyl, operation="read"
                )

    def _allocate_process_memory(self, pcb: Any, tick: int) -> None:
        """Trigger page faults for a newly admitted process's pages to allocate physical frames."""
        if self.memory_manager is None:
            return
        for page_num in range(pcb.memory_pages):
            # Check if page is already resident
            frame = self.memory_manager.translate(pcb.pid, page_num, tick)
            if frame is None:
                # Page not in memory — handle page fault to allocate a frame
                self.memory_manager.handle_page_fault_direct(pcb.pid, page_num, tick)

    def _admit_arrived_processes(self, tick: int) -> None:
        """Move arrived processes from NEW to READY and allocate their memory."""
        if self.process_manager is None:
            return

        ready_for_admission = [
            pcb for pcb in list(self.process_manager.new_queue)
            if pcb.arrival_time <= tick
        ]
        for pcb in ready_for_admission:
            self.process_manager.admit(pcb)
            # Allocate physical memory frames for the process's virtual pages
            self._allocate_process_memory(pcb, tick)

    def _free_process_memory(self, pid: int) -> None:
        """Release all physical frames held by a terminated process."""
        if self.memory_manager is None:
            return
        # Free mutexes (BUG-11 fix: only unblock processes that are actually BLOCKED)
        if self.sync_manager:
            for res_id, mutex in list(self.sync_manager.mutexes.items()):
                if mutex.owner_pid == pid:
                    try:
                        woken_pid = mutex.release(pid, self.clock.tick_count)
                        self.deadlock_detector.update("release", pid, res_id)
                        if woken_pid is not None:
                            self.deadlock_detector.update("allocate", woken_pid, res_id)
                            woken_pcb = next((p for p in self.process_manager.get_all_processes() if p.pid == woken_pid), None)
                            if woken_pcb and woken_pcb.state == ProcessState.BLOCKED:
                                self.process_manager.unblock(woken_pcb, self.clock.tick_count)
                    except PermissionError:
                        pass

        # Free memory frames via public API (BUG-03 fix: don't access VMM private members)
        self.memory_manager.free_process(pid)

    def _cleanup_terminated_processes(self, tick: int) -> None:
        """Free memory for newly terminated processes and cap the terminated list."""
        if self.process_manager is None:
            return

        for pcb in self.process_manager.terminated:
            if pcb.pid not in self._freed_pids:
                self._free_process_memory(pcb.pid)
                self._freed_pids.add(pcb.pid)

        # Cap terminated list to last 50 entries to prevent unbounded growth
        # BUG-23 fix: also remove trimmed PIDs from _freed_pids to prevent unbounded set growth
        if len(self.process_manager.terminated) > 50:
            trimmed = self.process_manager.terminated[:-50]
            for pcb in trimmed:
                self._freed_pids.discard(pcb.pid)
            self.process_manager.terminated = self.process_manager.terminated[-50:]

    def get_state(self) -> dict[str, Any]:
        """
        Return a fully serializable snapshot of the entire simulation.
        This is the canonical output format for the API and WebSocket.
        Schema: Section 17.1
        """
        return {
            "tick": self.clock.tick_count,
            "clock": {
                "tick_rate_ms": self.config.clock.tick_rate_ms,
                "paused": self.clock.is_paused,
                "max_ticks": self.config.clock.max_ticks,
            },
            "config": {
                "scheduler": {
                    "algorithm": self.config.scheduler.algorithm,
                    "time_quantum": self.config.scheduler.time_quantum,
                    "preemptive": self.config.scheduler.preemptive,
                },
                "memory": {
                    "algorithm": self.config.memory.algorithm,
                    "total_frames": self.config.memory.total_frames,
                },
                "disk": {
                    "scheduling": self.config.disk.scheduling,
                    "cylinders": self.config.disk.cylinders,
                },
            },
            "cpu": self._get_cpu_state(),
            "processes": self._get_process_state(),
            "memory": self._get_memory_state(),
            "filesystem": self._get_fs_state(),
            "disk": self._get_disk_state(),
            "deadlock": self._get_deadlock_state(),
            "gantt": self._get_gantt_state(),
        }

    def _get_cpu_state(self) -> dict:
        if self.process_manager is None:
            return {}
        running = self.process_manager.running
        return {
            "utilization": self.metrics_collector.cpu_utilization() if self.metrics_collector else 0.0,
            "running_pid": running.pid if running else None,
            "context_switches": self.process_manager.context_switch_count,
        }

    def _get_process_state(self) -> list[dict]:
        if self.process_manager is None:
            return []
        return [
            {
                "pid": p.pid, "name": p.name, "state": p.state.value,
                "priority": p.priority, "remaining_burst": p.remaining_burst,
                "waiting_time": p.waiting_time, "turnaround_time": p.turnaround_time,
            }
            for p in self.process_manager.get_all_processes()
        ]

    def _get_memory_state(self) -> dict:
        if self.memory_manager is None:
            return {}
        snap = self.memory_manager.get_state_snapshot()
        # BUG-40 fix: Use public API instead of accessing _frame_table directly
        blocks = self.memory_manager.get_allocated_blocks()
        snap["allocated_blocks"] = blocks
        snap["blocks"] = blocks  # alias for dashboard compatibility
        return snap

    def _get_fs_state(self) -> dict:
        if self.filesystem is None:
            return {}
        return self.filesystem.get_metrics()

    def _get_disk_state(self) -> dict:
        if self.io_manager is None:
            return {}
        raw = self.io_manager.get_state_snapshot()
        # Flatten disk_scheduler sub-dict to top level for dashboard consumption
        ds = raw.get("disk_scheduler", {})
        return {
            "current_head": ds.get("current_head", 53),
            "direction": ds.get("direction", 1),
            "pending_count": ds.get("pending_count", 0),
            "total_seek_distance": ds.get("total_seek_distance", 0),
            "algorithm": ds.get("algorithm", "sstf"),
            "seek_trace": ds.get("seek_trace", []),
            "trace": ds.get("seek_trace", []),
            "total_cylinders": self.io_manager.disk_scheduler.total_cylinders,
            "devices": raw.get("devices", {}),
            "current_tick": raw.get("current_tick", 0),
            "total_requests": raw.get("total_requests", 0),
        }

    def _get_deadlock_state(self) -> dict:
        if self.deadlock_detector is None:
            return {"detected": False, "cycles": []}
        return self.deadlock_detector.get_state_snapshot()

    def _get_gantt_state(self) -> list[dict]:
        if self.process_manager is None:
            return []
        # BUG-42 fix: Include color field for dashboard visualization
        return [
            {"pid": g.pid, "start_tick": g.start_tick, "end_tick": g.end_tick, "color": g.color}
            for g in self.process_manager.gantt_log
        ]

    async def _on_tick(self, tick: int) -> None:
        """
        Master tick handler — called every tick in this EXACT order.
        Do NOT reorder these calls.
        """
        # Step 1: Handle all pending interrupts
        self.interrupt_controller.handle_all()
        # Step 2: Advance I/O operations
        if self.io_manager:
            self.io_manager.tick(tick)
        # Step 2.5: Auto-spawn new processes periodically
        self._auto_spawn_process(tick)
        # Step 2.6: Admit arrived processes into READY queue
        self._admit_arrived_processes(tick)
        # Step 3: Scheduler decides who runs next (updates running process)
        if self.scheduler and self.process_manager:
            self.scheduler.tick(tick, self.process_manager)
        # Step 4: Execute one burst unit for running process
        if self.process_manager:
            running_pid = self.process_manager.running.pid if self.process_manager.running else None

            # BUG-02 fix: Process sync release requests BEFORE execute_tick so that
            # releases scheduled at the final burst tick are not lost when the process terminates.
            if self.sync_manager and self.process_manager.running and running_pid is not None:
                pre_pc = self.process_manager.running.program_counter
                pcb = self.process_manager.running
                for req in pcb.sync_requests:
                    if req.get("tick") == pre_pc and req.get("action") == "release":
                        self.sync_manager.process_request(pcb.pid, "release", req.get("resource"), tick)

            # Feature: Simulate realistic memory access during execution with locality
            if self.memory_manager and self.process_manager.running and running_pid is not None:
                pcb = self.process_manager.running
                if pcb.memory_pages > 0:
                    if pcb.last_accessed_page is None:
                        pcb.last_accessed_page = 0
                    
                    # 20% chance to jump to next page (simulating sequential scan), 80% spatial locality
                    pseudo_rand = (tick * 17 + pcb.pid * 31) % 100
                    if pseudo_rand < 20:
                        pcb.last_accessed_page = (pcb.last_accessed_page + 1) % pcb.memory_pages
                    
                    frame = self.memory_manager.translate(pcb.pid, pcb.last_accessed_page, tick)
                    if frame is None:
                        self.memory_manager.handle_page_fault_direct(pcb.pid, pcb.last_accessed_page, tick)

            # Feature: Simulate realistic disk I/O requests for active processes to keep Disk Arm Trace alive.
            # Uses the kernel's seeded PRNG instead of deterministic modular arithmetic to avoid
            # degenerate residue cycles where certain PIDs would never generate I/O.
            if self.io_manager and self.process_manager.running and running_pid is not None:
                if self._rng.randint(1, 100) <= 15:  # ~15% chance per tick
                    cylinders = max(self.config.disk.cylinders, 1)
                    target_cyl = self._rng.randint(0, cylinders - 1)
                    self.io_manager.submit_io(
                        pid=running_pid, device_id="disk0", cylinder=target_cyl, operation="read"
                    )

            self.process_manager.execute_tick(tick)

            # BUG-01 fix: Use post-execute program_counter for acquire requests.
            # After execute_tick, program_counter has been incremented, so the current
            # tick's PC is (program_counter - 1) for the process that just executed.
            if self.sync_manager and self.process_manager.running and self.process_manager.running.pid == running_pid:
                pcb = self.process_manager.running
                current_pc = pcb.program_counter  # post-increment value
                for req in pcb.sync_requests:
                    if req.get("tick") == current_pc and req.get("action") != "release":
                        self.sync_manager.process_request(pcb.pid, req.get("action"), req.get("resource"), tick)
        # Step 4.5: Free memory for terminated processes and cap terminated list
        self._cleanup_terminated_processes(tick)
        # Step 5: Memory manager handles any deferred work
        if self.memory_manager:
            self.memory_manager.tick(tick)
        # Step 6: File system processes queued operations
        if self.filesystem:
            self.filesystem.tick(tick)
        # Step 7: Sync manager resolves mutex/semaphore waits
        if self.sync_manager:
            self.sync_manager.tick(tick)
        # Step 8: Deadlock detection (runs every detection_interval ticks)
        if self.deadlock_detector and tick > 0:
            # Process delayed deadlock recovery if a cycle was previously detected
            if getattr(self, "_deadlock_recovery_countdown", 0) > 0:
                self._deadlock_recovery_countdown -= 1
                if self._deadlock_recovery_countdown == 0 and getattr(self, "_pending_deadlock_cycles", None):
                    affected_pids = self.deadlock_detector.recover(self._pending_deadlock_cycles, self.config.deadlock.recovery_strategy)
                    if affected_pids and self.process_manager:
                        for victim_pid in affected_pids:
                            victim_pcb = next(
                                (p for p in self.process_manager.get_all_processes()
                                 if p.pid == victim_pid and p.state == ProcessState.BLOCKED),
                                None
                            )
                            if victim_pcb:
                                try:
                                    self.process_manager.unblock(victim_pcb, tick)
                                    self.process_manager.terminate(victim_pcb, tick)
                                except Exception:
                                    pass
                    self._pending_deadlock_cycles = []

            # Standard detection runs on intervals
            if tick % self.config.deadlock.detection_interval == 0:
                self.deadlock_detector.tick(tick)
                cycles = self.deadlock_detector.detect()
                if cycles:
                    # Delay recovery by 3 ticks (typically ~1.5 - 3 seconds) 
                    # so the deadlock state is broadcasted to the dashboard UI and visibly renders.
                    if self.config.deadlock.recovery_strategy != "none" and getattr(self, "_deadlock_recovery_countdown", 0) == 0:
                        self._deadlock_recovery_countdown = 3
                        self._pending_deadlock_cycles = cycles
        # Step 9: Collect metrics snapshot
        if self.metrics_collector:
            self.metrics_collector.tick(tick)
        # Step 10: Publish tick event (dashboard reads this)
        self.event_bus.publish("TICK", self.get_state(), tick=tick, source="kernel")
