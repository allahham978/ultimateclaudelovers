"""
FastAPI app — EU CSRD Compliance Engine (v3.0 unified pipeline).

Endpoints:
  POST  /audit/run               Accept report JSON + company inputs (structured_document)
                                  OR free text + company inputs (free_text)
  GET   /audit/{audit_id}/stream  SSE stream of log lines + final result
  GET   /audit/{audit_id}         Return cached result (for reconnects)
  GET   /health                   Liveness probe
"""

import asyncio
import json
import os
import tempfile
import threading
import uuid
from typing import Any

from dotenv import load_dotenv

load_dotenv()  # Load ANTHROPIC_API_KEY (and other vars) from .env

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from graph import graph
from schemas import CompanyInputs
from state import AuditState
from tools.report_parser import (
    extract_narrative_sustainability,
    extract_xhtml_to_json,
    parse_report,
    summarize_narrative_sections,
)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="EU CSRD Compliance Engine", version="3.0")

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

        # Complete event — unified final_result for both modes
        final_result = result.get("final_result")

        if final_result:
            result_dict = final_result.model_dump() if hasattr(final_result, "model_dump") else final_result
            job.result = result_dict
            job.events.append({"type": "complete", "result": result_dict})

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
    entity_id: str = Form(...),
    mode: str = Form("structured_document"),
    report_json: UploadFile | None = File(None),
    free_text: str | None = Form(None),
    number_of_employees: int | None = Form(None),
    revenue_eur: float | None = Form(None),
    total_assets_eur: float | None = Form(None),
    reporting_year: int | None = Form(None),
):
    """Accept a report JSON (structured_document) or free text (free_text), start audit."""
    # Validate mode
    if mode not in ("structured_document", "free_text"):
        raise HTTPException(400, f"Invalid mode: {mode}. Must be 'structured_document' or 'free_text'.")

    audit_id = str(uuid.uuid4())

    # Build CompanyInputs from form fields
    company_inputs = CompanyInputs(
        number_of_employees=number_of_employees or 0,
        revenue_eur=revenue_eur or 0.0,
        total_assets_eur=total_assets_eur or 0.0,
        reporting_year=reporting_year or 2025,
    )

    if mode == "structured_document":
        # structured_document requires report_json file
        if report_json is None:
            raise HTTPException(400, "mode=structured_document requires a report_json file upload.")

        raw_bytes = await report_json.read()
        is_xhtml = raw_bytes.lstrip()[:10].startswith((b"<?xml", b"<html", b"<!DOC"))

        if is_xhtml:
            # XHTML upload: parse iXBRL facts + extract narrative sustainability text
            tmp_fd, tmp_path = tempfile.mkstemp(suffix=".xhtml")
            try:
                os.write(tmp_fd, raw_bytes)
                os.close(tmp_fd)
                raw_json = extract_xhtml_to_json(tmp_path)
                cleaned, esrs_data, taxonomy_data, narrative_sections = parse_report(
                    raw_json, file_path=tmp_path
                )
            finally:
                os.unlink(tmp_path)
        else:
            # JSON upload (existing path)
            try:
                raw_json = json.loads(raw_bytes)
            except json.JSONDecodeError as exc:
                raise HTTPException(400, f"Invalid JSON in uploaded file: {exc}")
            cleaned, esrs_data, taxonomy_data, narrative_sections = parse_report(raw_json)

        initial_state: AuditState = {
            "audit_id": audit_id,
            "mode": "structured_document",
            "report_json": cleaned,
            "esrs_data": esrs_data,
            "taxonomy_data": taxonomy_data,
            "narrative_sections": narrative_sections,
            "entity_id": entity_id,
            "company_inputs": company_inputs,
            "logs": [],
            "pipeline_trace": [],
        }

    else:
        # free_text requires free_text
        if not free_text or not free_text.strip():
            raise HTTPException(400, "mode=free_text requires a non-empty free_text field.")

        initial_state = {
            "audit_id": audit_id,
            "mode": "free_text",
            "free_text_input": free_text,
            "entity_id": entity_id,
            "company_inputs": company_inputs,
            "report_json": {},
            "esrs_data": {},
            "taxonomy_data": {},
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

    return {"audit_id": audit_id}


@app.get("/audit/{audit_id}/stream")
async def audit_stream(audit_id: str):
    """SSE stream — emits log lines, node completions, and the final result JSON."""
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
    """Return cached result (for reconnects after stream ends)."""
    if audit_id not in _jobs:
        raise HTTPException(404, f"Audit {audit_id} not found")

    job = _jobs[audit_id]
    if job.result is None:
        return JSONResponse({"status": "running", "audit_id": audit_id}, status_code=202)

    return job.result
