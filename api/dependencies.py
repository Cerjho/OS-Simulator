# api/dependencies.py
# Phase: 8 — Visualization & Dashboard
# Owner: Dashboard Agent
"""
Centralized FastAPI dependency management providing clean, global access
to the single shared Simulation Kernel instance across routers.
"""
from __future__ import annotations
from typing import TYPE_CHECKING
from fastapi import HTTPException

if TYPE_CHECKING:
    from core.kernel import Kernel

# Single global kernel instance shared across all API routes and WebSockets
kernel_instance: Kernel | None = None


def get_kernel() -> Kernel:
    """
    Retrieve the initialized global Simulation Kernel instance.
    Raises HTTP 400 Bad Request if the simulation has not completed startup lifecycle.
    """
    if kernel_instance is None:
        raise HTTPException(status_code=400, detail="Simulation kernel not initialized")
    return kernel_instance
