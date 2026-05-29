# api/routes/config.py
# Phase: 8 — Visualization & Dashboard
# Owner: Dashboard Agent
"""
Simulation configuration read/write partial updates and experiment runners.
Full implementation spec: OS101_AgentPlan_v2.md Section 13
"""
from __future__ import annotations
import asyncio
from pathlib import Path
from typing import Any
import yaml

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.kernel import Kernel
from core.config import SimConfig

router = APIRouter()


class RunExperimentRequest(BaseModel):
    """Pydantic payload parameter validation for running preset workload scripts."""
    name: str


@router.get("/config")
async def get_current_configuration() -> dict[str, Any]:
    """Retrieve active serialized simulation configuration file parameters."""
    target_file = Path("simulation.yaml")
    if target_file.exists():
        try:
            return yaml.safe_load(target_file.read_text()) or {}
        except Exception:
            pass
    # Export structural baseline dictionary mapping defaults cleanly
    return yaml.safe_load(yaml.dump(SimConfig())) or {}


@router.put("/config")
async def update_configuration(partial_update: dict[str, Any]) -> dict[str, Any]:
    """
    Accept partial configuration dict updates, validate structural constraints,
    persist back to simulation.yaml, and safely restart underlying kernel instances.
    """
    import api.dependencies as deps

    target_file = Path("simulation.yaml")
    current_raw: dict[str, Any] = {}
    if target_file.exists():
        try:
            current_raw = yaml.safe_load(target_file.read_text()) or {}
        except Exception:
            pass

    # Deep merge partial configuration parameter overrides
    for section_key, override_dict in partial_update.items():
        if isinstance(override_dict, dict):
            if section_key not in current_raw or not isinstance(current_raw[section_key], dict):
                current_raw[section_key] = {}
            current_raw[section_key].update(override_dict)
        else:
            current_raw[section_key] = override_dict

    # Reconstruct fresh simulation dataclass mapping to perform rigorous constraints validation
    try:
        from core.config import (
            ClockConfig, CPUConfig, SchedulerConfig, MemoryConfig,
            FilesystemConfig, DiskConfig, ProcessConfig, DeadlockConfig, LoggingConfig
        )
        new_cfg = SimConfig(
            clock=ClockConfig(**current_raw.get("clock", {})),
            cpu=CPUConfig(**current_raw.get("cpu", {})),
            scheduler=SchedulerConfig(**current_raw.get("scheduler", {})),
            memory=MemoryConfig(**current_raw.get("memory", {})),
            filesystem=FilesystemConfig(**current_raw.get("filesystem", {})),
            disk=DiskConfig(**current_raw.get("disk", {})),
            processes=ProcessConfig(**current_raw.get("processes", {})),
            deadlock=DeadlockConfig(**current_raw.get("deadlock", {})),
            logging=LoggingConfig(**current_raw.get("logging", {})),
        )
        errors = new_cfg.validate()
        if errors:
            raise HTTPException(status_code=422, detail={"errors": errors})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=422, detail={"errors": [str(e)]})

    # Persist serialized update block to underlying configuration file
    target_file.write_text(yaml.dump(current_raw))

    # Sync matching configurations to all preset workload files so the dashboard is the ultimate source of truth
    try:
        workloads_dir = Path("experiments/workloads")
        if workloads_dir.exists():
            for wl_file in workloads_dir.glob("*.yaml"):
                try:
                    wl_data = yaml.safe_load(wl_file.read_text()) or {}
                    wl_modified = False
                    
                    # Map workload section keys to global section keys
                    sections_map = {
                        "scheduler": "scheduler",
                        "deadlock": "deadlock",
                        "processes_config": "processes"
                    }
                    
                    for wl_sec, global_sec in sections_map.items():
                        if wl_sec in wl_data and global_sec in current_raw:
                            # Update only the keys that the workload explicitly defines
                            for k in list(wl_data[wl_sec].keys()):
                                if k in current_raw[global_sec]:
                                    wl_data[wl_sec][k] = current_raw[global_sec][k]
                                    wl_modified = True
                    
                    if wl_modified:
                        wl_file.write_text(yaml.dump(wl_data, sort_keys=False))
                except Exception as e:
                    print(f"[Config API] Failed to sync workload {wl_file.name}: {e}")
    except Exception as e:
        print(f"[Config API] Workload sync failed: {e}")

    # Smart Kernel Restart/Hot-Reload logic
    if deps.kernel_instance:
        old_cfg = deps.kernel_instance.config
        # Check if any structural hardware parameters changed that require a full restart
        structural_changed = (
            old_cfg.memory != new_cfg.memory or
            old_cfg.disk != new_cfg.disk or
            old_cfg.filesystem != new_cfg.filesystem or
            old_cfg.cpu != new_cfg.cpu
        )

        if structural_changed:
            deps.kernel_instance.stop()
            fresh_kernel = Kernel(str(target_file))
            deps.kernel_instance = fresh_kernel
            async def _start_kernel_safe() -> None:
                try:
                    await fresh_kernel.start()
                except Exception as exc:
                    print(f"[Config API] Kernel restart failed: {exc}")
            import asyncio
            asyncio.create_task(_start_kernel_safe())
            
            return {"status": "config_updated_kernel_restarted", "config": current_raw}
        else:
            # Hot-reload the parameters in-place so active workloads are not interrupted
            old_cfg.clock.tick_rate_ms = new_cfg.clock.tick_rate_ms
            old_cfg.clock.max_ticks = new_cfg.clock.max_ticks
            old_cfg.clock.auto_start = new_cfg.clock.auto_start
            
            old_cfg.scheduler.algorithm = new_cfg.scheduler.algorithm
            old_cfg.scheduler.time_quantum = new_cfg.scheduler.time_quantum
            old_cfg.scheduler.preemptive = new_cfg.scheduler.preemptive
            old_cfg.scheduler.aging_interval = new_cfg.scheduler.aging_interval
            
            old_cfg.deadlock.detection_interval = new_cfg.deadlock.detection_interval
            old_cfg.deadlock.recovery_strategy = new_cfg.deadlock.recovery_strategy
            
            old_cfg.processes.initial_load = new_cfg.processes.initial_load
            old_cfg.processes.auto_spawn = new_cfg.processes.auto_spawn
            old_cfg.processes.spawn_interval_ticks = new_cfg.processes.spawn_interval_ticks
            
            old_cfg.logging.level = new_cfg.logging.level
            old_cfg.logging.log_to_file = new_cfg.logging.log_to_file

            return {"status": "config_updated_hot_reloaded", "config": current_raw}


@router.get("/experiments")
async def list_experiment_presets() -> list[dict[str, Any]]:
    """Discover available YAML profile scripts inside target workload directories."""
    discovered_profiles: list[dict[str, Any]] = []
    base_dir = Path("experiments/workloads")

    if base_dir.exists():
        for file_path in base_dir.glob("*.yaml"):
            try:
                parsed_data = yaml.safe_load(file_path.read_text()) or {}
                discovered_profiles.append({
                    "name": file_path.stem,
                    "description": parsed_data.get("workload_name", f"Experiment Profile: {file_path.stem}"),
                    "config_path": str(file_path),
                })
            except Exception:
                pass

    # Ensure interface rendering hooks populate preset selectors cleanly if files are missing
    if not discovered_profiles:
        for profile_stem in ["standard_mix", "io_heavy", "memory_pressure", "deadlock_demo"]:
            discovered_profiles.append({
                "name": profile_stem,
                "description": f"Standard evaluation simulation workload: {profile_stem}",
                "config_path": f"experiments/workloads/{profile_stem}.yaml",
            })

    return discovered_profiles


@router.get("/experiments/{name}")
async def get_experiment_detail(name: str) -> dict[str, Any]:
    """Return full parsed YAML content for a specific workload preset including processes and config overrides."""
    workload_file = Path(f"experiments/workloads/{name}.yaml")
    if not workload_file.exists():
        raise HTTPException(status_code=404, detail=f"Workload '{name}' not found")

    try:
        parsed = yaml.safe_load(workload_file.read_text()) or {}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse workload: {e}")

    return {
        "name": name,
        "workload_name": parsed.get("workload_name", name),
        "seed": parsed.get("seed"),
        "scheduler": parsed.get("scheduler"),
        "processes_config": parsed.get("processes_config"),
        "deadlock": parsed.get("deadlock"),
        "processes": parsed.get("processes", []),
    }


# ── AUDIT FIX-9: Decomposed helpers for run_experiment_preset ─────────────────

def _load_workload_yaml(name: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Load and parse a workload YAML file. Returns (parsed_data, process_specs)."""
    workload_file = Path(f"experiments/workloads/{name}.yaml")
    if workload_file.exists():
        try:
            parsed = yaml.safe_load(workload_file.read_text()) or {}
            return parsed, parsed.get("processes", [])
        except Exception:
            pass
    return {}, []


def _apply_config_overrides(kernel: Kernel, parsed_workload: dict[str, Any]) -> None:
    """Apply workload-specific scheduler/process/deadlock overrides to the kernel config
    and persist them to simulation.yaml so the dashboard stays in sync."""
    try:
        target_file = Path("simulation.yaml")
        current_raw: dict[str, Any] = {}
        if target_file.exists():
            current_raw = yaml.safe_load(target_file.read_text()) or {}

        section_map = {
            "scheduler": ("scheduler", kernel.config.scheduler),
            "processes_config": ("processes", kernel.config.processes),
            "deadlock": ("deadlock", kernel.config.deadlock),
        }

        for wl_key, (cfg_key, cfg_obj) in section_map.items():
            if wl_key in parsed_workload:
                if cfg_key not in current_raw:
                    current_raw[cfg_key] = {}
                for k, v in parsed_workload[wl_key].items():
                    setattr(cfg_obj, k, v)
                    current_raw[cfg_key][k] = v

        target_file.write_text(yaml.dump(current_raw))
    except Exception as exc:
        print(f"[Experiment API] Config override failed: {exc}")


def _inject_workload_processes(
    kernel: Kernel, process_specs: list[dict[str, Any]]
) -> list[int]:
    """Inject process specifications into the kernel. Returns list of assigned PIDs."""
    assigned_pids: list[int] = []
    for spec in process_specs:
        pid = kernel.inject_process(spec)
        assigned_pids.append(pid)
    return assigned_pids


def _seed_disk_io(
    kernel: Kernel,
    workload_name: str,
    process_specs: list[dict[str, Any]],
    assigned_pids: list[int],
) -> int:
    """Seed initial disk I/O requests from workload specs. Returns count of requests submitted."""
    if kernel.io_manager is None or not assigned_pids:
        return 0

    disk_cylinders = max(int(kernel.config.disk.cylinders), 1)
    submitted = 0

    for idx, spec in enumerate(process_specs):
        if idx >= len(assigned_pids):
            break

        pid = assigned_pids[idx]
        io_cylinders: list[int] = []

        raw_io = spec.get("io_cylinders", [])
        if isinstance(raw_io, list):
            for cyl in raw_io:
                try:
                    parsed = int(cyl)
                except (TypeError, ValueError):
                    continue
                if 0 <= parsed < disk_cylinders:
                    io_cylinders.append(parsed)

        # Keep io_heavy visibly active even if YAML omits explicit IO cylinders.
        if not io_cylinders and workload_name == "io_heavy":
            mem_pages = int(spec.get("memory_pages", 1))
            base = (pid * 31 + (idx + 1) * 17 + mem_pages * 11) % disk_cylinders
            io_cylinders = [base, (base + 47) % disk_cylinders, (base + 93) % disk_cylinders]

        for cylinder in io_cylinders:
            kernel.io_manager.submit_io(
                pid=pid, device_id="disk0", cylinder=cylinder, operation="read",
            )
            submitted += 1

    return submitted


@router.post("/experiments/run")
async def run_experiment_preset(payload: RunExperimentRequest) -> dict[str, Any]:
    """Load workload process specifications and initialize clean tracking execution run."""
    import api.dependencies as deps

    # Step 1: Load workload YAML
    parsed_workload, process_specs = _load_workload_yaml(payload.name)

    # Step 2: Stop active kernel
    if deps.kernel_instance:
        deps.kernel_instance.stop()

    # Step 3: Create fresh kernel with config overrides
    new_kernel = Kernel("simulation.yaml")
    _apply_config_overrides(new_kernel, parsed_workload)

    # Step 4: Initialize subsystems synchronously BEFORE injecting processes
    await new_kernel._init_subsystems()
    new_kernel._initialized = True
    deps.kernel_instance = new_kernel

    # Step 5: Inject processes and seed disk I/O
    assigned_pids = _inject_workload_processes(new_kernel, process_specs)
    disk_requests_submitted = _seed_disk_io(new_kernel, payload.name, process_specs, assigned_pids)

    # Step 6: Start tick loop in background
    async def _start_kernel_safe() -> None:
        try:
            await new_kernel.start()
        except Exception as exc:
            print(f"[Experiment API] Kernel start failed: {exc}")

    asyncio.create_task(_start_kernel_safe())
    await asyncio.sleep(0.05)

    return {
        "status": "experiment_workload_started",
        "workload": payload.name,
        "injected_pids": assigned_pids,
        "disk_requests_submitted": disk_requests_submitted,
    }

