"""
Real-time event emitter registry for SSE streaming.

Allows agent nodes (running inside LangGraph) to push log events
directly to the in-memory job store so the SSE stream delivers
them to the frontend immediately — not after the entire pipeline completes.
"""

import time
from typing import Any, Callable

# audit_id → callback that appends an event dict to the job's event list
_emitters: dict[str, Callable[[dict[str, Any]], None]] = {}


def register(audit_id: str, callback: Callable[[dict[str, Any]], None]) -> None:
    """Register an event callback for an audit run."""
    _emitters[audit_id] = callback


def unregister(audit_id: str) -> None:
    """Remove the callback after the pipeline finishes."""
    _emitters.pop(audit_id, None)


def emit_log(audit_id: str, agent: str, message: str) -> None:
    """Push a log event to the SSE stream in real-time."""
    cb = _emitters.get(audit_id)
    if cb:
        cb({
            "type": "log",
            "agent": agent,
            "message": message,
            "timestamp": str(int(time.time() * 1000)),
        })


def emit_node_complete(audit_id: str, agent: str, duration_ms: int) -> None:
    """Push a node_complete event to the SSE stream."""
    cb = _emitters.get(audit_id)
    if cb:
        cb({
            "type": "node_complete",
            "agent": agent,
            "duration_ms": duration_ms,
        })
