"""
FastAPI app — EU CSRD Compliance Engine (v3.0 unified pipeline).

Endpoints:
  POST  /audit/run               Accept report JSON + company inputs (structured_document)
                                  OR free text + company inputs (free_text)
  GET   /audit/{audit_id}/stream  SSE stream of log lines + final result
  GET   /audit/{audit_id}         Return cached result (for reconnects)
  GET   /health                   Liveness probe
  POST  /kb/update                Manual knowledge-base update trigger
  GET   /kb/status                Knowledge-base update status
"""

import asyncio
import json
import logging
import os
import tempfile
import threading
import traceback
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Optional

from dotenv import load_dotenv

load_dotenv()  # Load ANTHROPIC_API_KEY (and other vars) from .env

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from events import emit_log, emit_node_complete, register, unregister
from graph import graph
from schemas import CompanyInputs
from state import AuditState
from tools.kb_updater import KBUpdater, get_tracked_celex_ids, read_meta
from tools.report_parser import (
    extract_narrative_sustainability,
    extract_xhtml_to_json,
    parse_report,
    summarize_narrative_sections,
)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

logger = logging.getLogger("audit")
logging.basicConfig(level=logging.INFO)

_KB_CHECK_INTERVAL_SECONDS = 24 * 60 * 60  # 24 hours
_KB_STALE_DAYS = 7


async def _periodic_kb_check() -> None:
    """Background task: check daily if the KB needs updating (>7 days stale)."""
    while True:
        try:
            await asyncio.sleep(_KB_CHECK_INTERVAL_SECONDS)
            meta = read_meta()
            last_update = meta.get("last_update_utc")
            if last_update:
                last_dt = datetime.fromisoformat(last_update)
                age_days = (datetime.now(timezone.utc) - last_dt).days
                if age_days <= _KB_STALE_DAYS:
                    logger.info("KB update check: last update %d days ago, still fresh.", age_days)
                    continue
                logger.info("KB update check: last update %d days ago, triggering update.", age_days)
            else:
                logger.info("KB update check: no previous update recorded, triggering update.")

            loop = asyncio.get_running_loop()
            updater = KBUpdater()
            for celex_id in get_tracked_celex_ids():
                await loop.run_in_executor(None, updater.run_update, celex_id)
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Periodic KB check failed.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: check staleness and start periodic task
    meta = read_meta()
    last_update = meta.get("last_update_utc")
    if last_update:
        last_dt = datetime.fromisoformat(last_update)
        age_days = (datetime.now(timezone.utc) - last_dt).days
        if age_days > _KB_STALE_DAYS:
            logger.info("KB is stale (%d days old), queuing background update.", age_days)
            loop = asyncio.get_running_loop()
            updater = KBUpdater()
            for celex_id in get_tracked_celex_ids():
                loop.run_in_executor(None, updater.run_update, celex_id)
    else:
        logger.info("No KB update metadata found — will update on next periodic check.")

    task = asyncio.create_task(_periodic_kb_check())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="EU CSRD Compliance Engine", version="3.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",
    ],
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
    """Run the LangGraph pipeline in a background thread, pushing SSE events.

    Log events are emitted in real-time by each agent node via the events
    module.  Node-complete and final-complete events are emitted here once
    the graph finishes.
    """
    # Register the job so agents can push log events in real-time
    register(audit_id, lambda evt: job.events.append(evt))

    try:
        # Emit knowledge-base freshness confirmation before the pipeline starts
        meta = read_meta()
        last_update = meta.get("last_update_utc", "never")
        emit_log(
            audit_id,
            "system",
            f"Regulatory rules verified up to date (last synced: {last_update})",
        )

        logger.info("[%s] Graph execution starting...", audit_id[:8])
        result = graph.invoke(state)
        logger.info("[%s] Graph execution completed successfully", audit_id[:8])

        # Emit node_complete events from pipeline_trace
        pipeline_trace = result.get("pipeline_trace", [])
        for trace_entry in pipeline_trace:
            emit_node_complete(
                audit_id, trace_entry["agent"], trace_entry["ms"]
            )

        # Complete event — unified final_result for both modes
        final_result = result.get("final_result")
        if final_result:
            result_dict = (
                final_result.model_dump()
                if hasattr(final_result, "model_dump")
                else final_result
            )
            job.result = result_dict
            job.events.append({"type": "complete", "result": result_dict})

    except Exception as exc:
        logger.error("[%s] Graph execution FAILED: %s", audit_id[:8], exc)
        logger.error("[%s] Traceback:\n%s", audit_id[:8], traceback.format_exc())
        job.events.append({"type": "error", "message": str(exc)})
    finally:
        unregister(audit_id)
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
    logger.info("POST /audit/run — mode=%s, entity=%s", mode, entity_id)

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
        logger.info("[%s] Uploaded file: %s (%d bytes)", audit_id[:8], report_json.filename, len(raw_bytes))
        is_xhtml = raw_bytes.lstrip()[:10].startswith((b"<?xml", b"<html", b"<!DOC"))
        logger.info("[%s] Detected format: %s", audit_id[:8], "XHTML" if is_xhtml else "JSON")

        if is_xhtml:
            # XHTML upload: parse iXBRL facts + extract narrative sustainability text
            tmp_fd, tmp_path = tempfile.mkstemp(suffix=".xhtml")
            try:
                os.write(tmp_fd, raw_bytes)
                os.close(tmp_fd)
                logger.info("[%s] Parsing XHTML → iXBRL facts...", audit_id[:8])
                raw_json = extract_xhtml_to_json(tmp_path)
                logger.info("[%s] Extracted %d facts, running parse_report...", audit_id[:8], len(raw_json.get("facts", [])))
                cleaned, esrs_data, taxonomy_data, narrative_sections = parse_report(
                    raw_json, file_path=tmp_path
                )
                logger.info("[%s] Parse complete: %d clean facts, %d ESRS, %d taxonomy, %d narrative sections",
                           audit_id[:8], len(cleaned.get("facts", [])), len(esrs_data.get("facts", [])),
                           len(taxonomy_data.get("facts", [])), len(narrative_sections))
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
        heartbeat_interval = 5.0  # seconds between keepalive comments
        last_heartbeat = asyncio.get_event_loop().time()

        while True:
            # Emit any new events
            while sent < len(job.events):
                event = job.events[sent]
                sent += 1
                yield f"data: {json.dumps(event)}\n\n"
                last_heartbeat = asyncio.get_event_loop().time()

            # If the graph has finished, drain remaining events and exit
            if job.complete.is_set():
                while sent < len(job.events):
                    event = job.events[sent]
                    sent += 1
                    yield f"data: {json.dumps(event)}\n\n"
                break

            # Send SSE comment as keepalive to prevent connection timeout
            now = asyncio.get_event_loop().time()
            if now - last_heartbeat >= heartbeat_interval:
                yield ": keepalive\n\n"
                last_heartbeat = now

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


# ---------------------------------------------------------------------------
# Knowledge-base update endpoints
# ---------------------------------------------------------------------------


@app.post("/kb/update")
async def kb_update(celex_id: Optional[str] = Query(default=None)):
    """Trigger a knowledge-base update. Runs in a thread to avoid blocking."""
    ids_to_check = [celex_id] if celex_id else get_tracked_celex_ids()
    loop = asyncio.get_running_loop()
    updater = KBUpdater()

    results = []
    for cid in ids_to_check:
        result = await loop.run_in_executor(None, updater.run_update, cid)
        results.append(result)

    return {"results": results}


@app.get("/kb/status")
async def kb_status():
    """Return the current knowledge-base update metadata."""
    return read_meta()
