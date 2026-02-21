"""
Iteration 2 Unit Tests — FastAPI + SSE Layer

Gate: Frontend terminal shows streaming log lines; final result renders as stub data.

Tests cover:
  - Health endpoint
  - POST /audit/run (multipart upload, validation, report parser integration)
  - GET /audit/{id}/stream (SSE event format, agent coverage, ordering)
  - GET /audit/{id} (cached result, 404 for unknown)
  - CORS headers
"""

import json
import time
import uuid

import pytest
from fastapi.testclient import TestClient

# Ensure backend imports resolve
import sys
import os

_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from main import app, _jobs

client = TestClient(app)


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

_SAMPLE_REPORT_JSON = {
    "report_info": {"source": "test-report.xhtml"},
    "facts": [
        {
            "ix_type": "ix:nonNumeric",
            "concept": "esrs_E1-1_01_TransitionPlan",
            "context_ref": "FY2024",
            "value": "Net-zero by 2040",
        },
        {
            "ix_type": "ix:nonFraction",
            "concept": "esrs_E1-5_04_TotalEnergyConsumption",
            "context_ref": "FY2024",
            "value": "45000",
            "unit_ref": "utr:MWh",
            "decimals": "0",
            "scale": None,
        },
        {
            "ix_type": "ix:nonFraction",
            "concept": "esrs_E1-6_01_GrossScope1GHGEmissions",
            "context_ref": "FY2024",
            "value": "1200",
            "unit_ref": "utr:tCO2eq",
            "decimals": "0",
            "scale": None,
        },
        {
            "ix_type": "ix:nonNumeric",
            "concept": "ifrs-full:NameOfReportingEntity",
            "context_ref": "FY2024",
            "value": "TestCorp SA",
        },
        {
            "ix_type": "ix:nonFraction",
            "concept": "eutaxonomy:CapExTotal",
            "context_ref": "FY2024",
            "value": "50000000",
            "unit_ref": "iso4217:EUR",
            "decimals": "0",
            "scale": None,
        },
        {
            "ix_type": "ix:nonFraction",
            "concept": "eutaxonomy:CapExAligned",
            "context_ref": "FY2024",
            "value": "17500000",
            "unit_ref": "iso4217:EUR",
            "decimals": "0",
            "scale": None,
        },
        {
            "ix_type": "ix:nonFraction",
            "concept": "ifrs-full:Revenue",
            "context_ref": "FY2024",
            "value": "250000000",
            "unit_ref": "iso4217:EUR",
            "decimals": "0",
            "scale": None,
        },
    ],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _upload_report(entity_id: str = "TestCorp SA") -> dict:
    """POST /audit/run with sample report JSON. Returns response object."""
    file_content = json.dumps(_SAMPLE_REPORT_JSON).encode()
    return client.post(
        "/audit/run",
        files={"report_json": ("report.json", file_content, "application/json")},
        data={"entity_id": entity_id},
    )


def _run_and_wait(entity_id: str = "TestCorp SA", wait: float = 2.0) -> str:
    """Upload report, wait for graph completion, return run_id."""
    r = _upload_report(entity_id)
    run_id = r.json()["run_id"]
    time.sleep(wait)
    return run_id


def _collect_sse_events(run_id: str) -> list[dict]:
    """Stream SSE events and return them as a list of parsed dicts."""
    events = []
    with client.stream("GET", f"/audit/{run_id}/stream") as response:
        for line in response.iter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
    return events


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_jobs():
    """Clean up the in-memory job store between tests."""
    yield
    _jobs.clear()


# ===========================================================================
# Health Endpoint
# ===========================================================================


class TestHealthEndpoint:
    def test_returns_status_ok(self):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}

    def test_health_content_type(self):
        r = client.get("/health")
        assert "application/json" in r.headers["content-type"]


# ===========================================================================
# POST /audit/run
# ===========================================================================


class TestAuditRunEndpoint:
    def test_returns_run_id(self):
        r = _upload_report()
        assert r.status_code == 200
        body = r.json()
        assert "run_id" in body
        assert isinstance(body["run_id"], str)
        assert len(body["run_id"]) > 0

    def test_run_id_is_valid_uuid(self):
        r = _upload_report()
        run_id = r.json()["run_id"]
        uuid.UUID(run_id)  # Raises ValueError if invalid

    def test_unique_run_ids_per_request(self):
        r1 = _upload_report()
        r2 = _upload_report()
        assert r1.json()["run_id"] != r2.json()["run_id"]

    def test_rejects_missing_report_file(self):
        r = client.post("/audit/run", data={"entity_id": "Test", "mode": "full_audit"})
        assert r.status_code == 400

    def test_rejects_missing_entity_id(self):
        file_content = json.dumps(_SAMPLE_REPORT_JSON).encode()
        r = client.post(
            "/audit/run",
            files={"report_json": ("report.json", file_content, "application/json")},
        )
        assert r.status_code == 422

    def test_rejects_invalid_json_file(self):
        r = client.post(
            "/audit/run",
            files={"report_json": ("report.json", b"not valid json", "application/json")},
            data={"entity_id": "Test"},
        )
        assert r.status_code == 400

    def test_accepts_empty_report(self):
        """An empty (but valid) JSON report should be accepted — stubs fill defaults."""
        empty_report = {"report_info": {}, "facts": []}
        file_content = json.dumps(empty_report).encode()
        r = client.post(
            "/audit/run",
            files={"report_json": ("report.json", file_content, "application/json")},
            data={"entity_id": "EmptyCorp"},
        )
        assert r.status_code == 200
        assert "run_id" in r.json()


# ===========================================================================
# GET /audit/{audit_id} — Cached result
# ===========================================================================


class TestAuditResultEndpoint:
    def test_404_for_unknown_audit_id(self):
        r = client.get("/audit/nonexistent-id-12345")
        assert r.status_code == 404

    def test_202_while_still_running(self):
        """If the graph hasn't finished, return 202."""
        r = _upload_report()
        run_id = r.json()["run_id"]
        # Immediately check — might be 202 or 200 depending on timing
        r = client.get(f"/audit/{run_id}")
        assert r.status_code in (200, 202)

    def test_returns_complete_result_after_graph_finishes(self):
        run_id = _run_and_wait()
        r = client.get(f"/audit/{run_id}")
        assert r.status_code == 200
        body = r.json()
        assert body["audit_id"] == run_id
        assert body["schema_version"] == "2.0"

    def test_result_contains_all_top_level_fields(self):
        run_id = _run_and_wait()
        r = client.get(f"/audit/{run_id}")
        body = r.json()
        required_fields = [
            "audit_id",
            "generated_at",
            "schema_version",
            "company",
            "taxonomy_alignment",
            "compliance_cost",
            "esrs_ledger",
            "roadmap",
            "registry_source",
            "sources",
            "pipeline",
        ]
        for field in required_fields:
            assert field in body, f"Missing top-level field: {field}"

    def test_result_company_reflects_entity_id(self):
        run_id = _run_and_wait(entity_id="Lumiere SA")
        r = client.get(f"/audit/{run_id}")
        assert r.json()["company"]["name"] == "Lumiere SA"

    def test_result_has_three_esrs_ledger_items(self):
        run_id = _run_and_wait()
        r = client.get(f"/audit/{run_id}")
        assert len(r.json()["esrs_ledger"]) == 3

    def test_result_pipeline_has_four_agents(self):
        run_id = _run_and_wait()
        r = client.get(f"/audit/{run_id}")
        pipeline = r.json()["pipeline"]
        assert len(pipeline["agents"]) == 4
        agent_names = [a["agent"] for a in pipeline["agents"]]
        assert agent_names == ["extractor", "fetcher", "auditor", "consultant"]

    def test_result_taxonomy_alignment_pct_valid(self):
        run_id = _run_and_wait()
        r = client.get(f"/audit/{run_id}")
        pct = r.json()["taxonomy_alignment"]["capex_aligned_pct"]
        assert 0.0 <= pct <= 100.0

    def test_result_is_json_serialisable(self):
        """The cached result must be fully JSON-serialisable (no Pydantic objects)."""
        run_id = _run_and_wait()
        r = client.get(f"/audit/{run_id}")
        body = r.json()
        # Round-trip through JSON to verify
        json_str = json.dumps(body)
        parsed = json.loads(json_str)
        assert parsed["audit_id"] == run_id


# ===========================================================================
# GET /audit/{audit_id}/stream — SSE Streaming
# ===========================================================================


class TestSSEStream:
    def test_404_for_unknown_audit_id(self):
        r = client.get("/audit/nonexistent-id-12345/stream")
        assert r.status_code == 404

    def test_sse_content_type(self):
        run_id = _run_and_wait()
        with client.stream("GET", f"/audit/{run_id}/stream") as response:
            assert "text/event-stream" in response.headers["content-type"]
            # Consume stream so it closes cleanly
            for _ in response.iter_lines():
                pass

    def test_streams_all_three_event_types(self):
        run_id = _run_and_wait()
        events = _collect_sse_events(run_id)
        event_types = {e["type"] for e in events}
        assert "log" in event_types, "No log events emitted"
        assert "node_complete" in event_types, "No node_complete events emitted"
        assert "complete" in event_types, "No complete event emitted"

    def test_log_events_from_all_four_agents(self):
        run_id = _run_and_wait()
        events = _collect_sse_events(run_id)
        log_agents = {e["agent"] for e in events if e["type"] == "log"}
        assert "extractor" in log_agents
        assert "fetcher" in log_agents
        assert "auditor" in log_agents
        assert "consultant" in log_agents

    def test_four_node_complete_events_in_order(self):
        run_id = _run_and_wait()
        events = _collect_sse_events(run_id)
        node_completes = [e for e in events if e["type"] == "node_complete"]
        assert len(node_completes) == 4
        agents = [e["agent"] for e in node_completes]
        assert agents == ["extractor", "fetcher", "auditor", "consultant"]

    def test_exactly_one_complete_event(self):
        run_id = _run_and_wait()
        events = _collect_sse_events(run_id)
        complete_events = [e for e in events if e["type"] == "complete"]
        assert len(complete_events) == 1

    def test_complete_event_contains_valid_audit(self):
        run_id = _run_and_wait()
        events = _collect_sse_events(run_id)
        complete = next(e for e in events if e["type"] == "complete")
        audit = complete["audit"]
        assert audit["audit_id"] == run_id
        assert audit["schema_version"] == "2.0"
        assert "company" in audit
        assert "esrs_ledger" in audit
        assert "roadmap" in audit
        assert "pipeline" in audit

    def test_log_event_has_required_fields(self):
        """Each log event must have: type, agent, message, timestamp."""
        run_id = _run_and_wait()
        events = _collect_sse_events(run_id)
        log_event = next(e for e in events if e["type"] == "log")
        assert "agent" in log_event
        assert "message" in log_event
        assert "timestamp" in log_event
        assert log_event["agent"] in {"extractor", "fetcher", "auditor", "consultant"}

    def test_node_complete_event_has_duration(self):
        run_id = _run_and_wait()
        events = _collect_sse_events(run_id)
        nc = next(e for e in events if e["type"] == "node_complete")
        assert "agent" in nc
        assert "duration_ms" in nc
        assert isinstance(nc["duration_ms"], int)

    def test_logs_come_before_their_node_complete(self):
        """All log events for an agent must appear before that agent's node_complete."""
        run_id = _run_and_wait()
        events = _collect_sse_events(run_id)
        for agent_name in ("extractor", "fetcher", "auditor", "consultant"):
            agent_log_indices = [
                i for i, e in enumerate(events)
                if e["type"] == "log" and e["agent"] == agent_name
            ]
            nc_indices = [
                i for i, e in enumerate(events)
                if e["type"] == "node_complete" and e["agent"] == agent_name
            ]
            if agent_log_indices and nc_indices:
                assert max(agent_log_indices) < nc_indices[0], (
                    f"{agent_name}: logs must come before node_complete"
                )

    def test_complete_event_is_last(self):
        """The complete event must be the last event in the stream."""
        run_id = _run_and_wait()
        events = _collect_sse_events(run_id)
        assert events[-1]["type"] == "complete"

    def test_sse_data_format(self):
        """Each event line must be prefixed with 'data: ' per the SSE spec."""
        run_id = _run_and_wait()
        with client.stream("GET", f"/audit/{run_id}/stream") as response:
            lines = list(response.iter_lines())
        # Filter non-empty lines (SSE separates events with blank lines)
        data_lines = [l for l in lines if l.strip()]
        assert len(data_lines) > 0
        for line in data_lines:
            assert line.startswith("data: "), f"Line missing 'data: ' prefix: {line[:50]}"

    def test_multiple_log_events_per_agent(self):
        """Each stub agent emits at least 3 log lines."""
        run_id = _run_and_wait()
        events = _collect_sse_events(run_id)
        for agent_name in ("extractor", "fetcher", "auditor", "consultant"):
            agent_logs = [e for e in events if e["type"] == "log" and e["agent"] == agent_name]
            assert len(agent_logs) >= 3, (
                f"{agent_name} should emit at least 3 log lines, got {len(agent_logs)}"
            )


# ===========================================================================
# Report Parser Integration
# ===========================================================================


class TestReportParserIntegration:
    def test_junk_data_is_cleaned_during_upload(self):
        """Upload with junk data should succeed — report_parser strips it."""
        report_with_junk = {
            "report_info": {"source": "test.xhtml"},
            "facts": [
                {"concept": "esrs_E1-1_01_TransitionPlan", "value": "Net-zero by 2040"},
                {"concept": None, "value": "junk"},
                {"concept": "some_tag", "value": "<script>alert('xss')</script>"},
                {"concept": "eutaxonomy:CapExTotal", "value": "50000000"},
            ],
        }
        file_content = json.dumps(report_with_junk).encode()
        r = client.post(
            "/audit/run",
            files={"report_json": ("report.json", file_content, "application/json")},
            data={"entity_id": "JunkCorp"},
        )
        assert r.status_code == 200

    def test_empty_report_produces_valid_audit(self):
        """Empty report (no facts) should still produce a valid CSRDAudit via stubs."""
        empty_report = {"report_info": {}, "facts": []}
        file_content = json.dumps(empty_report).encode()
        r = client.post(
            "/audit/run",
            files={"report_json": ("report.json", file_content, "application/json")},
            data={"entity_id": "EmptyCorp"},
        )
        run_id = r.json()["run_id"]
        time.sleep(2)

        r = client.get(f"/audit/{run_id}")
        assert r.status_code == 200
        body = r.json()
        assert body["schema_version"] == "2.0"
        assert body["company"]["name"] == "EmptyCorp"

    def test_report_without_report_info_key(self):
        """Report missing 'report_info' key should still be processed."""
        report = {"facts": [{"concept": "esrs_E1-1_01", "value": "test"}]}
        file_content = json.dumps(report).encode()
        r = client.post(
            "/audit/run",
            files={"report_json": ("report.json", file_content, "application/json")},
            data={"entity_id": "NoBannerCorp"},
        )
        assert r.status_code == 200


# ===========================================================================
# CORS
# ===========================================================================


class TestCORS:
    def test_cors_allows_localhost_3000(self):
        r = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"

    def test_cors_allows_post_method(self):
        r = client.options(
            "/audit/run",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )
        allowed = r.headers.get("access-control-allow-methods", "")
        assert "POST" in allowed or "*" in allowed

    def test_cors_allows_credentials(self):
        r = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert r.headers.get("access-control-allow-credentials") == "true"


# ===========================================================================
# End-to-End: Upload → Stream → Result
# ===========================================================================


class TestEndToEnd:
    def test_full_flow_upload_stream_result(self):
        """POST → wait → stream all events → GET cached result. Everything matches."""
        # 1. Upload
        r = _upload_report(entity_id="E2E Corp")
        assert r.status_code == 200
        run_id = r.json()["run_id"]
        time.sleep(2)

        # 2. Stream
        events = _collect_sse_events(run_id)
        assert len(events) > 0

        # 3. Verify stream audit matches cached result
        stream_audit = next(e for e in events if e["type"] == "complete")["audit"]
        r = client.get(f"/audit/{run_id}")
        cached_audit = r.json()

        assert stream_audit["audit_id"] == cached_audit["audit_id"]
        assert stream_audit["schema_version"] == cached_audit["schema_version"]
        assert stream_audit["company"]["name"] == "E2E Corp"
        assert cached_audit["company"]["name"] == "E2E Corp"

    def test_different_entity_ids_produce_different_results(self):
        """Two audits with different entity_ids should produce different company names."""
        run_id_a = _run_and_wait(entity_id="Alpha Corp")
        run_id_b = _run_and_wait(entity_id="Beta Corp")

        r_a = client.get(f"/audit/{run_id_a}")
        r_b = client.get(f"/audit/{run_id_b}")

        assert r_a.json()["company"]["name"] == "Alpha Corp"
        assert r_b.json()["company"]["name"] == "Beta Corp"
