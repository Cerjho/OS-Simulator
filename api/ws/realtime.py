# api/ws/realtime.py
# Phase: 8 — Visualization & Dashboard
# Owner: Dashboard Agent
"""
Real-time full state streaming WebSockets bridging synchronous EventBus metrics.
Full implementation spec: OS101_AgentPlan_v2.md Section 13
"""
from __future__ import annotations
import asyncio
import json
from typing import Any

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from core.kernel import Kernel
from core.event_bus import Event
from api.dependencies import get_kernel

router = APIRouter()


@router.websocket("/ws/realtime")
async def websocket_realtime_endpoint(
    websocket: WebSocket,
    kernel: Kernel = Depends(get_kernel)
) -> None:
    """
    Establish bidirectional WebSockets transmission layer.
    Streams active state snapshot immediately upon connection, subscribes to EventBus TICK
    messages dynamically, enforces 64KB size truncation bounds, and handles Control client commands.
    """
    await websocket.accept()

    # Deliver instantaneous current state baseline snapshot immediately on establish connection
    try:
        initial_state = kernel.get_state()
        await websocket.send_text(json.dumps(initial_state))
    except Exception:
        return

    # Asynchronous memory buffer bridging synchronous EventBus listener callbacks safely
    state_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=10)

    subscribed_events = (
        "TICK",
        "SIMULATION_PAUSED",
        "SIMULATION_RESUMED",
        "SIMULATION_STOPPED",
        "SIMULATION_STARTED",
    )

    def _state_listener_callback(event: Event) -> None:
        """Pushes simulation state frames into async queue for both ticks and lifecycle changes."""
        try:
            if event.event_type == "TICK" and isinstance(event.payload, dict):
                state_frame = event.payload
            else:
                state_frame = kernel.get_state()

            # Drop oldest frame if queue is full to prevent unbounded memory growth
            if state_queue.full():
                try:
                    state_queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            state_queue.put_nowait(state_frame)
        except Exception:
            pass

    # Subscribe active listener to kernel state and lifecycle events
    for event_type in subscribed_events:
        kernel.event_bus.subscribe(event_type, _state_listener_callback)

    async def _transmission_sender_loop() -> None:
        """Consumes buffered tick state structures, evaluates frame capacity constraints, and transmits frames."""
        try:
            while True:
                state_frame = await state_queue.get()
                serialized_text = json.dumps(state_frame)
                
                # Check maximum byte length capacity constraint (64KB = 65536 bytes)
                if len(serialized_text.encode("utf-8")) > 65_536:
                    truncated_frame = dict(state_frame)
                    if "gantt" in truncated_frame and isinstance(truncated_frame["gantt"], list):
                        # Truncate gantt historical entry arrays to trailing 50 items precisely
                        truncated_frame["gantt"] = truncated_frame["gantt"][-50:]
                    serialized_text = json.dumps(truncated_frame)

                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_text(serialized_text)
                else:
                    break
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    async def _reception_listener_loop() -> None:
        """Listens for bidirectional incoming client telemetry command blocks."""
        try:
            while True:
                client_message = await websocket.receive_json()
                command_str = client_message.get("command")

                if command_str in ("pause", "resume", "stop"):
                    if command_str == "pause":
                        kernel.pause()
                    elif command_str == "resume":
                        kernel.resume()
                    elif command_str == "stop":
                        kernel.stop()

                    # Transmit verification acknowledgment structure matching expected dashboard payloads
                    ack_response = {"ack": command_str, "tick": kernel.clock.tick_count}
                    if websocket.client_state == WebSocketState.CONNECTED:
                        await websocket.send_text(json.dumps(ack_response))
        except WebSocketDisconnect:
            pass
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    # Execute async sender and receiver task components in parallel
    sender_task = asyncio.create_task(_transmission_sender_loop())
    receiver_task = asyncio.create_task(_reception_listener_loop())

    try:
        # BUG-16 fix: Await whichever finishes first, then cancel the other
        done, pending = await asyncio.wait(
            [sender_task, receiver_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
    finally:
        # Guarantee cancellation and unregistration cleanup hooks to prevent memory leaks
        sender_task.cancel()
        receiver_task.cancel()
        for event_type in subscribed_events:
            kernel.event_bus.unsubscribe(event_type, _state_listener_callback)
