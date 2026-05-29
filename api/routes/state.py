# api/routes/state.py
# Phase: 8 — Visualization & Dashboard
# Owner: Dashboard Agent
"""
Real-time simulation state snapshot and metrics history API endpoints.
Full implementation spec: OS101_AgentPlan_v2.md Section 13
"""
from __future__ import annotations
from typing import Any
from fastapi import APIRouter, Depends, Query

from core.kernel import Kernel
from api.dependencies import get_kernel

router = APIRouter()


@router.get("/state")
async def get_simulation_state(kernel: Kernel = Depends(get_kernel)) -> dict[str, Any]:
    """Retrieve full live serializable simulation subsystem state snapshot."""
    return kernel.get_state()


@router.get("/metrics/history")
async def get_metrics_history(
    last_n: int = Query(100, ge=1, le=1000, description="Retrieve historical window boundary count"),
    kernel: Kernel = Depends(get_kernel)
) -> list[dict[str, Any]]:
    """Retrieve historical Section 17.2 time-series telemetry metrics snapshot."""
    # Use real metrics history if MetricsCollector is initialised
    if kernel.metrics_collector and hasattr(kernel.metrics_collector, "get_history"):
        history = kernel.metrics_collector.get_history(last_n)
        if history:
            return history

    # Fallback: generate baseline placeholder if collector has no data yet
    return [{
        "tick": 0,
        "cpu_utilization": 0.0,
        "page_fault_rate": 0.0,
        "memory_utilization": 0.0,
    }]
