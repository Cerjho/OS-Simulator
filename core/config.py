# core/config.py
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import yaml


@dataclass
class ClockConfig:
    tick_rate_ms: int = 100
    max_ticks: int = 10_000
    auto_start: bool = False


@dataclass
class CPUConfig:
    cores: int = 1
    context_switch_cost: int = 2


@dataclass
class SchedulerConfig:
    algorithm: str = "round_robin"
    time_quantum: int = 4
    preemptive: bool = True
    aging_interval: int = 50


@dataclass
class MemoryConfig:
    total_frames: int = 64
    page_size_kb: int = 4
    algorithm: str = "lru"
    swap_enabled: bool = True
    tlb_size: int = 16


@dataclass
class FilesystemConfig:
    type: str = "fat"
    total_blocks: int = 512
    block_size_kb: int = 4


@dataclass
class DiskConfig:
    scheduling: str = "sstf"
    cylinders: int = 200
    initial_head: int = 53
    seek_time_per_track: int = 1


@dataclass
class ProcessConfig:
    initial_load: int = 5
    auto_spawn: bool = True
    spawn_interval_ticks: int = 20


@dataclass
class DeadlockConfig:
    detection_interval: int = 10
    recovery_strategy: str = "terminate_youngest"


@dataclass
class LoggingConfig:
    level: str = "INFO"
    log_to_file: bool = True
    log_path: str = "logs/simulation.log"


@dataclass
class SimConfig:
    clock: ClockConfig = field(default_factory=ClockConfig)
    cpu: CPUConfig = field(default_factory=CPUConfig)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    filesystem: FilesystemConfig = field(default_factory=FilesystemConfig)
    disk: DiskConfig = field(default_factory=DiskConfig)
    processes: ProcessConfig = field(default_factory=ProcessConfig)
    deadlock: DeadlockConfig = field(default_factory=DeadlockConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    # Validation constants — do not change
    VALID_SCHEDULER_ALGORITHMS = {"fcfs", "sjf", "srtf", "priority", "round_robin", "mlfq"}
    VALID_PAGE_ALGORITHMS = {"fifo", "lru", "optimal", "clock"}
    VALID_FS_TYPES = {"fat", "inode"}
    VALID_DISK_ALGORITHMS = {"fcfs", "sstf", "scan", "c-scan", "look", "c-look"}
    VALID_RECOVERY_STRATEGIES = {"terminate_youngest", "terminate_lowest", "resource_preempt"}

    def validate(self) -> list[str]:
        """Returns list of error strings. Empty list = valid."""
        errors: list[str] = []
        if self.scheduler.algorithm not in self.VALID_SCHEDULER_ALGORITHMS:
            errors.append(f"Invalid scheduler algorithm: {self.scheduler.algorithm!r}")
        if self.memory.algorithm not in self.VALID_PAGE_ALGORITHMS:
            errors.append(f"Invalid page replacement algorithm: {self.memory.algorithm!r}")
        if self.filesystem.type not in self.VALID_FS_TYPES:
            errors.append(f"Invalid filesystem type: {self.filesystem.type!r}")
        if self.disk.scheduling not in self.VALID_DISK_ALGORITHMS:
            errors.append(f"Invalid disk scheduling algorithm: {self.disk.scheduling!r}")
        if self.memory.total_frames <= 0:
            errors.append("total_frames must be > 0")
        if self.scheduler.time_quantum <= 0:
            errors.append("time_quantum must be > 0")
        if self.disk.cylinders <= 0:
            errors.append("disk.cylinders must be > 0")
        if not (0 <= self.disk.initial_head < self.disk.cylinders):
            errors.append(f"initial_head must be in [0, {self.disk.cylinders - 1}]")
        return errors


def load_config(path: str | Path = "simulation.yaml") -> SimConfig:
    """
    Load simulation.yaml and return a validated SimConfig.
    Raises ValueError if validation fails.
    """
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {path!r}. "
            f"Create a simulation.yaml or provide a valid path."
        )
    raw = yaml.safe_load(config_path.read_text())
    cfg = SimConfig(
        clock=ClockConfig(**raw.get("clock", {})),
        cpu=CPUConfig(**raw.get("cpu", {})),
        scheduler=SchedulerConfig(**raw.get("scheduler", {})),
        memory=MemoryConfig(**raw.get("memory", {})),
        filesystem=FilesystemConfig(**raw.get("filesystem", {})),
        disk=DiskConfig(**raw.get("disk", {})),
        processes=ProcessConfig(**raw.get("processes", {})),
        deadlock=DeadlockConfig(**raw.get("deadlock", {})),
        logging=LoggingConfig(**raw.get("logging", {})),
    )
    errors = cfg.validate()
    if errors:
        raise ValueError("Config validation failed:\n" + "\n".join(f"  - {e}" for e in errors))
    return cfg
