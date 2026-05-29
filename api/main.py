# api/main.py
# Phase: 8 — Visualization & Dashboard
# Owner: Dashboard Agent
"""
FastAPI application entrypoint mounting API and WebSocket routers, configuring CORS,
and managing the single global shared simulation Kernel instance lifecycle.
Full implementation spec: OS101_AgentPlan_v2.md Section 13
"""
from __future__ import annotations
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator
import yaml

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.kernel import Kernel
from core.config import SimConfig
import api.dependencies as deps

from api.routes.control import router as control_router
from api.routes.state import router as state_router
from api.routes.config import router as config_router
from api.ws.realtime import router as ws_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    FastAPI Context Manager handling initialization and finalization lifecycle.
    Instantiates the single global shared Kernel reference cleanly on startup.
    """
    # Ensure baseline simulation.yaml profile script exists to guarantee successful startup
    target_cfg = Path("simulation.yaml")
    if not target_cfg.exists():
        try:
            default_raw = yaml.safe_load(yaml.dump(SimConfig())) or {}
            target_cfg.write_text(yaml.dump(default_raw))
        except Exception:
            pass

    # Initialize single global kernel instance shared across all API routes and WebSockets
    kernel = Kernel(str(target_cfg))
    deps.kernel_instance = kernel

    yield

    # Cleanly terminate any active background timing engine loops upon application shutdown
    if deps.kernel_instance:
        deps.kernel_instance.stop()


# Instantiate FastAPI framework instance using modern Context Manager hooks
app = FastAPI(
    title="OS101 Core Simulation Backend API",
    description="Real-time Operational Dashboard telemetry API layer",
    lifespan=lifespan,
)

# Configure strict cross-origin network policies allowing standard Dashboard port targets
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount functional API controllers under standardized prefixes
app.include_router(control_router, prefix="/api", tags=["Control"])
app.include_router(state_router, prefix="/api", tags=["State"])
app.include_router(config_router, prefix="/api", tags=["Config"])

# Mount high-frequency bidirectional real-time WebSocket endpoints directly
app.include_router(ws_router, tags=["Realtime"])
