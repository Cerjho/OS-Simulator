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

    # Restart Kernel backend state cleanly to apply hardware parameter modifications
    if deps.kernel_instance:
        deps.kernel_instance.stop()

    fresh_kernel = Kernel(str(target_file))
    deps.kernel_instance = fresh_kernel

    async def _start_kernel_safe() -> None:
        try:
            await fresh_kernel.start()
        except Exception as exc:
            print(f"[Config API] Kernel restart failed: {exc}")

    asyncio.create_task(_start_kernel_safe())
    await asyncio.sleep(0.05)

    return {"status": "config_updated_kernel_restarted", "config": current_raw}


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


@router.post("/experiments/run")
async def run_experiment_preset(payload: RunExperimentRequest) -> dict[str, Any]:
    """Load workload process specifications and initialize clean tracking execution run."""
    import api.dependencies as deps

    workload_file = Path(f"experiments/workloads/{payload.name}.yaml")
    process_specs: list[dict[str, Any]] = []
    # BUG-12 fix: Initialize parsed_workload before conditional block
    parsed_workload: dict[str, Any] = {}

    if workload_file.exists():
        try:
            parsed_workload = yaml.safe_load(workload_file.read_text()) or {}
            process_specs = parsed_workload.get("processes", [])
        except Exception:
            pass

    # Terminate active kernel state context
    if deps.kernel_instance:
        deps.kernel_instance.stop()

    # Launch fresh context engine execution block
    new_kernel = Kernel("simulation.yaml")

    # BUG-13 fix: Apply config overrides BEFORE _init_subsystems so they take effect
    try:
        if "scheduler" in parsed_workload:
            for k, v in parsed_workload["scheduler"].items():
                setattr(new_kernel.config.scheduler, k, v)

        if "processes_config" in parsed_workload:
            for k, v in parsed_workload["processes_config"].items():
                setattr(new_kernel.config.processes, k, v)
    except Exception as exc:
        print(f"[Experiment API] Config override failed: {exc}")

    # BUG-14 fix: Initialize subsystems synchronously BEFORE injecting processes
    await new_kernel._init_subsystems()
    new_kernel._initialized = True
    deps.kernel_instance = new_kernel

    # Inject configured process footprint arrays sequentially
    assigned_pids: list[int] = []
    for spec in process_specs:
        pid = new_kernel.inject_process(spec)
        assigned_pids.append(pid)

    # Seed disk I/O traces for workloads that define I/O targets.
    disk_requests_submitted = 0
    if new_kernel.io_manager is not None and assigned_pids:
        disk_cylinders = max(int(new_kernel.config.disk.cylinders), 1)

        for idx, spec in enumerate(process_specs):
            if idx >= len(assigned_pids):
                break

            pid = assigned_pids[idx]
            io_cylinders: list[int] = []

            raw_io_cylinders = spec.get("io_cylinders", [])
            if isinstance(raw_io_cylinders, list):
                for cylinder in raw_io_cylinders:
                    try:
                        parsed = int(cylinder)
                    except (TypeError, ValueError):
                        continue
                    if 0 <= parsed < disk_cylinders:
                        io_cylinders.append(parsed)

            # Keep io_heavy visibly active even if YAML omits explicit IO cylinders.
            if not io_cylinders and payload.name == "io_heavy":
                mem_pages = int(spec.get("memory_pages", 1))
                base = (pid * 31 + (idx + 1) * 17 + mem_pages * 11) % disk_cylinders
                io_cylinders = [base, (base + 47) % disk_cylinders, (base + 93) % disk_cylinders]

            for cylinder in io_cylinders:
                new_kernel.io_manager.submit_io(
                    pid=pid,
                    device_id="disk0",
                    cylinder=cylinder,
                    operation="read",
                )
                disk_requests_submitted += 1

    # Start the tick loop in background AFTER injection
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
