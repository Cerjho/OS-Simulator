# core/event_bus.py
from __future__ import annotations
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Callable, Any
import json


# ── Event Type Catalogue ──────────────────────────────────────────────────────
# These are the ONLY valid event type strings.
# An agent must not publish events with names not in this list
# without updating the list and documenting the reason.

VALID_EVENT_TYPES: frozenset[str] = frozenset({
    "TICK",
    "PROCESS_CREATED",
    "PROCESS_TERMINATED",
    "PROCESS_STATE_CHANGED",
    "PAGE_FAULT",
    "IO_COMPLETE",
    "IO_REQUEST",
    "DEADLOCK_DETECTED",
    "DEADLOCK_RECOVERED",
    "CONTEXT_SWITCH",
    "MEMORY_ALLOCATED",
    "MEMORY_DEALLOCATED",
    "FILE_CREATED",
    "FILE_DELETED",
    "SIMULATION_STARTED",
    "SIMULATION_STOPPED",
    "SIMULATION_PAUSED",
    "SIMULATION_RESUMED",
})


@dataclass
class Event:
    event_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    tick: int = 0
    source: str = "unknown"

    def to_json(self) -> str:
        return json.dumps({
            "event_type": self.event_type,
            "tick": self.tick,
            "source": self.source,
            "payload": self.payload,
        })


class EventBus:
    """
    Synchronous pub/sub event bus.

    Key rules:
      - publish() is SYNCHRONOUS. The caller blocks until all listeners return.
      - A listener that raises an exception does NOT stop other listeners.
        The exception is caught, logged, and the bus continues.
      - Event types must be in VALID_EVENT_TYPES. Publishing unknown types raises ValueError.
    """

    def __init__(self, strict_types: bool = True) -> None:
        self._listeners: dict[str, list[Callable[[Event], None]]] = defaultdict(list)
        self._max_history: int = 5000        # cap to prevent unbounded memory growth
        # BUG-25 fix: Use deque with maxlen for O(1) append and automatic eviction
        self._history: deque[Event] = deque(maxlen=self._max_history)
        self._strict_types = strict_types

    def subscribe(self, event_type: str, callback: Callable[[Event], None]) -> None:
        """Register callback for an event type. Callback receives Event object."""
        if self._strict_types and event_type not in VALID_EVENT_TYPES:
            raise ValueError(f"Unknown event type: {event_type!r}. Add to VALID_EVENT_TYPES first.")
        self._listeners[event_type].append(callback)

    def unsubscribe(self, event_type: str, callback: Callable[[Event], None]) -> None:
        """Remove a previously registered callback."""
        try:
            self._listeners[event_type].remove(callback)
        except ValueError:
            pass  # Not subscribed — silently ignore

    def publish(self, event_type: str, payload: dict[str, Any], tick: int = 0, source: str = "kernel") -> None:
        """
        Fire an event synchronously.
        All registered callbacks are called before this method returns.
        """
        if self._strict_types and event_type not in VALID_EVENT_TYPES:
            raise ValueError(f"Unknown event type: {event_type!r}")
        event = Event(event_type=event_type, payload=payload, tick=tick, source=source)
        self._history.append(event)  # deque auto-evicts oldest when maxlen reached
        for callback in self._listeners[event_type]:
            try:
                callback(event)
            except Exception as exc:
                print(f"[EventBus ERROR] Listener for {event_type!r} raised: {exc}")

    def get_history(self, last_n: int | None = None) -> list[Event]:
        """Return event history. If last_n provided, return last N events only."""
        if last_n is None:
            return list(self._history)
        return self._history[-last_n:]

    def clear_history(self) -> None:
        self._history.clear()
