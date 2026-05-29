# api/routes/control.py
# Phase: 8 — Visualization & Dashboard
# Owner: Dashboard Agent
"""
Simulation Lifecycle and Process Injection API controllers.
Directly interfaces with core Kernel operational methods.
Full implementation spec: OS101_AgentPlan_v2.md Section 13
"""
from __future__ import annotations
import asyncio
from typing import Any
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from core.kernel import Kernel
from api.dependencies import get_kernel

router = APIRouter()


class InjectProcessRequest(BaseModel):
    """Pydantic payload schema validation for runtime process injection requests."""
    name: str = Field(..., description="Unique process naming string")
    burst: int = Field(..., gt=0, description="Required execution CPU burst units")
    priority: int = Field(5, ge=0, description="Scheduling tier priority level")
    memory_pages: int = Field(4, gt=0, description="Virtual memory page footprint allocation")


@router.post("/control/start")
async def start_simulation(kernel: Kernel = Depends(get_kernel)) -> dict[str, Any]:
    """Launch simulation subsystems and start clock execution loop."""
    # BUG-15 fix: Guard against duplicate start calls creating multiple tick loops
    if kernel.clock.is_running:
        return {"status": "already_running", "tick": kernel.clock.tick_count}
    # Run the start loop asynchronously in the background so API does not block HTTP callers
    asyncio.create_task(kernel.start())
    # Briefly yield context to allow initial tick initialization to publish basic state
    await asyncio.sleep(0.05)
    return {"status": "started", "tick": kernel.clock.tick_count}


@router.post("/control/stop")
async def stop_simulation(kernel: Kernel = Depends(get_kernel)) -> dict[str, Any]:
    """Terminate simulation tick execution lifecycle."""
    kernel.stop()
    return {"status": "stopped", "tick": kernel.clock.tick_count}


@router.post("/control/pause")
async def pause_simulation(kernel: Kernel = Depends(get_kernel)) -> dict[str, Any]:
    """Temporarily suspend automated tick advancement."""
    kernel.pause()
    return {"status": "paused", "tick": kernel.clock.tick_count}


@router.post("/control/resume")
async def resume_simulation(kernel: Kernel = Depends(get_kernel)) -> dict[str, Any]:
    """Resume automated simulation tick progression."""
    kernel.resume()
    return {"status": "resumed", "tick": kernel.clock.tick_count}


@router.post("/control/step")
async def step_simulation(kernel: Kernel = Depends(get_kernel)) -> dict[str, Any]:
    """Manually advance the simulation execution clock by precisely one tick unit."""
    await kernel.step()
    return {"status": "stepped", "tick": kernel.clock.tick_count}


@router.post("/processes/inject")
async def inject_process(
    payload: InjectProcessRequest,
    kernel: Kernel = Depends(get_kernel)
) -> dict[str, Any]:
    """Inject a freshly spawned process specification mid-simulation execution dynamically."""
    assigned_pid = kernel.inject_process(payload.model_dump())
    return {"pid": assigned_pid, "tick": kernel.clock.tick_count}
