"""
FastAPI app — EU CSRD Audit Engine.

Endpoints:
  POST  /audit/run               Accept report JSON + entity_id, start audit
  GET   /audit/{audit_id}/stream  SSE stream of log lines + final result
  GET   /audit/{audit_id}         Return cached result (for reconnects)
  GET   /health                   Liveness probe
"""

import asyncio
import json
import threading
import uuid
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from graph import graph
from state import AuditState
from tools.report_parser import parse_report

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="EU CSRD Audit Engine", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# In-memory job store (v1)
# ---------------------------------------------------------------------------


class _AuditJob:
    """Tracks a running or completed audit."""

    __slots__ = ("events", "complete", "result")

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self.complete = threading.Event()
        self.result: dict[str, Any] | None = None


_jobs: dict[str, _AuditJob] = {}


# ---------------------------------------------------------------------------
# Background graph runner
# ---------------------------------------------------------------------------


def _run_graph(audit_id: str, state: AuditState, job: _AuditJob) -> None:
    """Run the LangGraph pipeline in a background thread, pushing SSE events."""
    try:
        result = graph.invoke(state)

        all_logs = result.get("logs", [])
        pipeline_trace = result.get("pipeline_trace", [])
        trace_by_agent: dict[str, dict] = {t["agent"]: t for t in pipeline_trace}

        # Emit log + node_complete events grouped by agent execution order
        current_agent: str | None = None
        for log_entry in all_logs:
            agent = log_entry["agent"]

            # When agent transitions, emit node_complete for the previous agent
            if current_agent is not None and agent != current_agent:
                if current_agent in trace_by_agent:
                    trace = trace_by_agent.pop(current_agent)
                    job.events.append(
                        {
                            "type": "node_complete",
                            "agent": current_agent,
                            "duration_ms": trace["ms"],
                        }
                    )

            current_agent = agent
            job.events.append(
                {
                    "type": "log",
                    "agent": log_entry["agent"],
                    "message": log_entry["msg"],
                    "timestamp": str(log_entry["ts"]),
                }
            )

        # node_complete for the last agent
        if current_agent is not None and current_agent in trace_by_agent:
            trace = trace_by_agent.pop(current_agent)
            job.events.append(
                {
                    "type": "node_complete",
                    "agent": current_agent,
                    "duration_ms": trace["ms"],
                }
            )

        # Complete event with the full CSRDAudit JSON
        final_audit = result.get("final_audit")
        if final_audit:
            audit_dict = final_audit.model_dump()
            job.result = audit_dict
            job.events.append({"type": "complete", "audit": audit_dict})

    except Exception as exc:
        job.events.append({"type": "error", "message": str(exc)})
    finally:
        job.complete.set()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
async def health():
    """Liveness probe."""
    return {"status": "ok"}


@app.post("/audit/run")
async def audit_run(
    report_json: UploadFile = File(...),
    entity_id: str = Form(...),
):
    """Accept a pre-parsed management report JSON + entity identifier, start audit."""
    audit_id = str(uuid.uuid4())

    # Parse uploaded JSON file
    raw_bytes = await report_json.read()
    try:
        raw_json = json.loads(raw_bytes)
    except json.JSONDecodeError as exc:
        raise HTTPException(400, f"Invalid JSON in uploaded file: {exc}")

    # Clean + route sections via report_parser
    cleaned, esrs_data, taxonomy_data = parse_report(raw_json)

    # Initialise AuditState
    initial_state: AuditState = {
        "audit_id": audit_id,
        "report_json": cleaned,
        "esrs_data": esrs_data,
        "taxonomy_data": taxonomy_data,
        "entity_id": entity_id,
        "logs": [],
        "pipeline_trace": [],
    }

    # Create job + launch background thread
    job = _AuditJob()
    _jobs[audit_id] = job

    thread = threading.Thread(
        target=_run_graph,
        args=(audit_id, initial_state, job),
        daemon=True,
    )
    thread.start()

    return {"run_id": audit_id}


@app.get("/audit/{audit_id}/stream")
async def audit_stream(audit_id: str):
    """SSE stream — emits log lines, node completions, and the final CSRDAudit JSON."""
    if audit_id not in _jobs:
        raise HTTPException(404, f"Audit {audit_id} not found")

    job = _jobs[audit_id]

    async def _event_generator():
        sent = 0
        while True:
            # Emit any new events
            while sent < len(job.events):
                event = job.events[sent]
                sent += 1
                yield f"data: {json.dumps(event)}\n\n"

            # If the graph has finished, drain remaining events and exit
            if job.complete.is_set():
                while sent < len(job.events):
                    event = job.events[sent]
                    sent += 1
                    yield f"data: {json.dumps(event)}\n\n"
                break

            await asyncio.sleep(0.05)

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/audit/{audit_id}")
async def get_audit(audit_id: str):
    """Return cached CSRDAudit JSON (for reconnects after stream ends)."""
    if audit_id not in _jobs:
        raise HTTPException(404, f"Audit {audit_id} not found")

    job = _jobs[audit_id]
    if job.result is None:
        return JSONResponse({"status": "running", "audit_id": audit_id}, status_code=202)

    return job.result
