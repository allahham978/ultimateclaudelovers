"""
Iteration 4 Unit Tests — Compliance Check Scaffold (Backend)

Gate: graph.invoke({"mode":"compliance_check","free_text_input":"...","entity_id":"test",...})
      runs 3-node pipeline (skips fetcher) and returns final_compliance_check.
      Full audit path unchanged (zero regression).

Tests cover:
  - New Pydantic models (ExtractedGoal, ESRSCoverageItem, ComplianceTodo, etc.)
  - AuditState dual-mode keys
  - Conditional graph routing (fetcher skipped in compliance_check)
  - Agent stubs in compliance_check mode
  - FastAPI endpoint dual-mode support
  - Full audit regression (unchanged behavior)
  - System prompt constants
"""

import json
import time
import uuid

import pytest
from fastapi.testclient import TestClient

import sys
import os

_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from main import app, _jobs
from schemas import (
    ComplianceCheckResult,
    ComplianceCostEstimate,
    ComplianceTodo,
    CSRDAudit,
    ESRSCoverageItem,
    ExtractedGoal,
)

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAMPLE_REPORT_JSON = {
    "report_info": {"source": "test-report.xhtml"},
    "facts": [
        {"ix_type": "ix:nonNumeric", "concept": "esrs_E1-1_01_TransitionPlan", "context_ref": "FY2024", "value": "Net-zero by 2040"},
        {"ix_type": "ix:nonFraction", "concept": "eutaxonomy:CapExTotal", "context_ref": "FY2024", "value": "50000000", "unit_ref": "iso4217:EUR", "decimals": "0", "scale": None},
    ],
}

_SAMPLE_FREE_TEXT = (
    "We are an AI infrastructure company based in France. "
    "We have set a net-zero target for 2040. "
    "Our data centers consume approximately 120 GWh annually with 29% renewable energy."
)


def _upload_full_audit(entity_id: str = "TestCorp SA") -> dict:
    """POST /audit/run in full_audit mode."""
    file_content = json.dumps(_SAMPLE_REPORT_JSON).encode()
    return client.post(
        "/audit/run",
        files={"report_json": ("report.json", file_content, "application/json")},
        data={"entity_id": entity_id, "mode": "full_audit"},
    )


def _upload_compliance_check(entity_id: str = "Lumiere SA", free_text: str = _SAMPLE_FREE_TEXT) -> dict:
    """POST /audit/run in compliance_check mode."""
    return client.post(
        "/audit/run",
        data={"entity_id": entity_id, "mode": "compliance_check", "free_text": free_text},
    )


def _run_and_wait_full_audit(entity_id: str = "TestCorp SA", wait: float = 2.0) -> str:
    r = _upload_full_audit(entity_id)
    run_id = r.json()["run_id"]
    time.sleep(wait)
    return run_id


def _run_and_wait_compliance(entity_id: str = "Lumiere SA", wait: float = 2.0) -> str:
    r = _upload_compliance_check(entity_id)
    run_id = r.json()["run_id"]
    time.sleep(wait)
    return run_id


def _collect_sse_events(run_id: str) -> list[dict]:
    events = []
    with client.stream("GET", f"/audit/{run_id}/stream") as response:
        for line in response.iter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
    return events


@pytest.fixture(autouse=True)
def _clear_jobs():
    yield
    _jobs.clear()


# ===========================================================================
# New Pydantic Models
# ===========================================================================


class TestNewSchemas:
    def test_extracted_goal_import(self):
        from schemas import ExtractedGoal  # noqa: F401

    def test_esrs_coverage_item_import(self):
        from schemas import ESRSCoverageItem  # noqa: F401

    def test_compliance_todo_import(self):
        from schemas import ComplianceTodo  # noqa: F401

    def test_compliance_cost_estimate_import(self):
        from schemas import ComplianceCostEstimate  # noqa: F401

    def test_compliance_check_result_import(self):
        from schemas import ComplianceCheckResult  # noqa: F401

    def test_coverage_level_literal(self):
        from schemas import CoverageLevel  # noqa: F401

    def test_effort_level_literal(self):
        from schemas import EffortLevel  # noqa: F401

    def test_extracted_goal_creates(self):
        g = ExtractedGoal(id="g-1", description="Net-zero by 2040", esrs_relevance="E1-1", confidence=0.7)
        assert g.confidence == 0.7

    def test_esrs_coverage_item_creates(self):
        c = ESRSCoverageItem(esrs_id="E1-1", standard_name="Transition Plan", coverage="partial", details="Some info found")
        assert c.coverage == "partial"

    def test_compliance_todo_creates(self):
        t = ComplianceTodo(
            id="todo-1", priority="critical", esrs_id="E1-6",
            title="Conduct GHG inventory", description="Measure Scope 1/2/3.",
            regulatory_reference="ESRS E1-6", estimated_effort="high",
        )
        assert t.priority == "critical"

    def test_compliance_cost_estimate_creates(self):
        c = ComplianceCostEstimate(
            estimated_range_low_eur=500_000, estimated_range_high_eur=2_000_000,
            basis="Art. 51", caveat="Rough estimate.",
        )
        assert c.estimated_range_low_eur < c.estimated_range_high_eur

    def test_compliance_todo_rejects_invalid_priority(self):
        with pytest.raises(Exception):
            ComplianceTodo(
                id="t-1", priority="invalid_priority", esrs_id="E1-1",
                title="X", description="Y", regulatory_reference="Z", estimated_effort="low",
            )

    def test_compliance_todo_rejects_invalid_effort(self):
        with pytest.raises(Exception):
            ComplianceTodo(
                id="t-1", priority="high", esrs_id="E1-1",
                title="X", description="Y", regulatory_reference="Z", estimated_effort="invalid",
            )

    def test_esrs_coverage_item_rejects_invalid_coverage(self):
        with pytest.raises(Exception):
            ESRSCoverageItem(esrs_id="E1-1", standard_name="Test", coverage="invalid", details="X")


# ===========================================================================
# AuditState — Dual-Mode Keys
# ===========================================================================


class TestAuditStateDualMode:
    def test_auditstate_has_mode_key(self):
        from state import AuditState
        from typing import get_type_hints

        hints = get_type_hints(AuditState)
        assert "mode" in hints

    def test_auditstate_has_free_text_input_key(self):
        from state import AuditState
        from typing import get_type_hints

        hints = get_type_hints(AuditState)
        assert "free_text_input" in hints

    def test_auditstate_has_extracted_goals_key(self):
        from state import AuditState
        from typing import get_type_hints

        hints = get_type_hints(AuditState)
        assert "extracted_goals" in hints

    def test_auditstate_has_esrs_coverage_key(self):
        from state import AuditState
        from typing import get_type_hints

        hints = get_type_hints(AuditState)
        assert "esrs_coverage" in hints

    def test_auditstate_has_compliance_cost_estimate_key(self):
        from state import AuditState
        from typing import get_type_hints

        hints = get_type_hints(AuditState)
        assert "compliance_cost_estimate" in hints

    def test_auditstate_has_todo_list_key(self):
        from state import AuditState
        from typing import get_type_hints

        hints = get_type_hints(AuditState)
        assert "todo_list" in hints

    def test_auditstate_has_final_compliance_check_key(self):
        from state import AuditState
        from typing import get_type_hints

        hints = get_type_hints(AuditState)
        assert "final_compliance_check" in hints


# ===========================================================================
# System Prompts
# ===========================================================================


class TestSystemPrompts:
    def test_extractor_lite_prompt_exists(self):
        from tools.prompts import SYSTEM_PROMPT_EXTRACTOR_LITE
        assert len(SYSTEM_PROMPT_EXTRACTOR_LITE) > 100

    def test_auditor_lite_prompt_exists(self):
        from tools.prompts import SYSTEM_PROMPT_AUDITOR_LITE
        assert len(SYSTEM_PROMPT_AUDITOR_LITE) > 100

    def test_consultant_lite_prompt_exists(self):
        from tools.prompts import SYSTEM_PROMPT_CONSULTANT_LITE
        assert len(SYSTEM_PROMPT_CONSULTANT_LITE) > 100

    def test_extractor_lite_mentions_free_text(self):
        from tools.prompts import SYSTEM_PROMPT_EXTRACTOR_LITE
        assert "unstructured" in SYSTEM_PROMPT_EXTRACTOR_LITE.lower()

    def test_auditor_lite_mentions_coverage(self):
        from tools.prompts import SYSTEM_PROMPT_AUDITOR_LITE
        assert "coverage" in SYSTEM_PROMPT_AUDITOR_LITE.lower()

    def test_consultant_lite_mentions_todo(self):
        from tools.prompts import SYSTEM_PROMPT_CONSULTANT_LITE
        assert "to-do" in SYSTEM_PROMPT_CONSULTANT_LITE.lower() or "todo" in SYSTEM_PROMPT_CONSULTANT_LITE.lower()

    def test_original_prompts_unchanged(self):
        from tools.prompts import (
            SYSTEM_PROMPT_EXTRACTOR,
            SYSTEM_PROMPT_FETCHER,
            SYSTEM_PROMPT_AUDITOR,
            SYSTEM_PROMPT_CONSULTANT,
        )
        assert "iXBRL" in SYSTEM_PROMPT_EXTRACTOR
        assert "Taxonomy" in SYSTEM_PROMPT_FETCHER
        assert "double materiality" in SYSTEM_PROMPT_AUDITOR.lower()
        assert "roadmap" in SYSTEM_PROMPT_CONSULTANT.lower()


# ===========================================================================
# Graph Conditional Routing
# ===========================================================================


class TestGraphRouting:
    def test_graph_imports(self):
        from graph import graph, route_after_extractor  # noqa: F401

    def test_route_after_extractor_full_audit(self):
        from graph import route_after_extractor
        state = {"mode": "full_audit"}
        assert route_after_extractor(state) == "fetcher"

    def test_route_after_extractor_compliance_check(self):
        from graph import route_after_extractor
        state = {"mode": "compliance_check"}
        assert route_after_extractor(state) == "auditor"

    def test_route_after_extractor_default_is_full_audit(self):
        from graph import route_after_extractor
        state = {}  # no mode set — should default to full_audit path
        assert route_after_extractor(state) == "fetcher"

    def test_compliance_check_graph_runs_end_to_end(self, compliance_check_state):
        from graph import graph
        result = graph.invoke(compliance_check_state)
        assert result is not None

    def test_compliance_check_produces_final_compliance_check(self, compliance_check_state):
        from graph import graph
        result = graph.invoke(compliance_check_state)
        assert "final_compliance_check" in result
        assert isinstance(result["final_compliance_check"], ComplianceCheckResult)

    def test_compliance_check_skips_fetcher(self, compliance_check_state):
        from graph import graph
        result = graph.invoke(compliance_check_state)
        agents = [t["agent"] for t in result["pipeline_trace"]]
        assert "fetcher" not in agents

    def test_compliance_check_runs_three_agents(self, compliance_check_state):
        from graph import graph
        result = graph.invoke(compliance_check_state)
        agents = [t["agent"] for t in result["pipeline_trace"]]
        assert agents == ["extractor", "auditor", "consultant"]

    def test_full_audit_graph_still_runs_four_agents(self, minimal_state):
        from graph import graph
        result = graph.invoke(minimal_state)
        agents = [t["agent"] for t in result["pipeline_trace"]]
        assert agents == ["extractor", "fetcher", "auditor", "consultant"]

    def test_full_audit_still_produces_final_audit(self, minimal_state):
        from graph import graph
        result = graph.invoke(minimal_state)
        assert "final_audit" in result
        assert isinstance(result["final_audit"], CSRDAudit)


# ===========================================================================
# Extractor — Compliance Check Mode
# ===========================================================================


class TestExtractorComplianceCheck:
    def test_returns_extracted_goals(self, compliance_check_state):
        from agents.extractor import extractor_node
        result = extractor_node(compliance_check_state)
        assert "extracted_goals" in result
        assert isinstance(result["extracted_goals"], list)
        assert len(result["extracted_goals"]) > 0

    def test_extracted_goals_have_required_fields(self, compliance_check_state):
        from agents.extractor import extractor_node
        result = extractor_node(compliance_check_state)
        for goal in result["extracted_goals"]:
            assert "id" in goal
            assert "description" in goal
            assert "confidence" in goal

    def test_returns_esrs_claims(self, compliance_check_state):
        from agents.extractor import extractor_node
        result = extractor_node(compliance_check_state)
        assert "esrs_claims" in result
        assert len(result["esrs_claims"]) == 3

    def test_xbrl_concept_is_none_in_compliance_mode(self, compliance_check_state):
        from agents.extractor import extractor_node
        result = extractor_node(compliance_check_state)
        for claim in result["esrs_claims"].values():
            assert claim.xbrl_concept is None

    def test_returns_company_meta(self, compliance_check_state):
        from agents.extractor import extractor_node
        result = extractor_node(compliance_check_state)
        assert "company_meta" in result
        assert result["company_meta"].name == "Lumiere Systemes SA"

    def test_report_title_is_user_provided(self, compliance_check_state):
        from agents.extractor import extractor_node
        result = extractor_node(compliance_check_state)
        assert "User-Provided" in result["company_meta"].report_title

    def test_logs_emitted_in_compliance_mode(self, compliance_check_state):
        from agents.extractor import extractor_node
        result = extractor_node(compliance_check_state)
        assert len(result["logs"]) >= 3
        assert all(l["agent"] == "extractor" for l in result["logs"])


# ===========================================================================
# Auditor — Compliance Check Mode
# ===========================================================================


class TestAuditorComplianceCheck:
    def test_returns_esrs_coverage(self, compliance_state_after_extractor):
        from agents.auditor import auditor_node
        result = auditor_node(compliance_state_after_extractor)
        assert "esrs_coverage" in result
        assert isinstance(result["esrs_coverage"], list)
        assert len(result["esrs_coverage"]) == 3

    def test_esrs_coverage_has_required_fields(self, compliance_state_after_extractor):
        from agents.auditor import auditor_node
        result = auditor_node(compliance_state_after_extractor)
        for item in result["esrs_coverage"]:
            assert "esrs_id" in item
            assert "standard_name" in item
            assert "coverage" in item
            assert "details" in item

    def test_esrs_coverage_values_are_valid(self, compliance_state_after_extractor):
        from agents.auditor import auditor_node
        result = auditor_node(compliance_state_after_extractor)
        valid_coverage = {"covered", "partial", "not_covered"}
        for item in result["esrs_coverage"]:
            assert item["coverage"] in valid_coverage

    def test_returns_compliance_cost_estimate(self, compliance_state_after_extractor):
        from agents.auditor import auditor_node
        result = auditor_node(compliance_state_after_extractor)
        assert "compliance_cost_estimate" in result
        est = result["compliance_cost_estimate"]
        assert "estimated_range_low_eur" in est
        assert "estimated_range_high_eur" in est
        assert "basis" in est
        assert "caveat" in est

    def test_cost_estimate_low_less_than_high(self, compliance_state_after_extractor):
        from agents.auditor import auditor_node
        result = auditor_node(compliance_state_after_extractor)
        est = result["compliance_cost_estimate"]
        assert est["estimated_range_low_eur"] <= est["estimated_range_high_eur"]

    def test_cost_estimate_has_caveat(self, compliance_state_after_extractor):
        from agents.auditor import auditor_node
        result = auditor_node(compliance_state_after_extractor)
        assert "incomplete" in result["compliance_cost_estimate"]["caveat"].lower() or \
               "unstructured" in result["compliance_cost_estimate"]["caveat"].lower()

    def test_does_not_return_full_audit_keys(self, compliance_state_after_extractor):
        from agents.auditor import auditor_node
        result = auditor_node(compliance_state_after_extractor)
        assert "esrs_ledger" not in result
        assert "taxonomy_alignment" not in result
        assert "taxonomy_alignment_score" not in result

    def test_logs_emitted(self, compliance_state_after_extractor):
        from agents.auditor import auditor_node
        result = auditor_node(compliance_state_after_extractor)
        auditor_logs = [l for l in result["logs"] if l["agent"] == "auditor"]
        assert len(auditor_logs) >= 3


# ===========================================================================
# Consultant — Compliance Check Mode
# ===========================================================================


class TestConsultantComplianceCheck:
    def test_returns_todo_list(self, compliance_state_after_auditor):
        from agents.consultant import consultant_node
        result = consultant_node(compliance_state_after_auditor)
        assert "todo_list" in result
        assert isinstance(result["todo_list"], list)
        assert len(result["todo_list"]) > 0

    def test_todo_items_have_required_fields(self, compliance_state_after_auditor):
        from agents.consultant import consultant_node
        result = consultant_node(compliance_state_after_auditor)
        for item in result["todo_list"]:
            assert "id" in item
            assert "priority" in item
            assert "esrs_id" in item
            assert "title" in item
            assert "description" in item
            assert "regulatory_reference" in item
            assert "estimated_effort" in item

    def test_includes_foundational_items(self, compliance_state_after_auditor):
        from agents.consultant import consultant_node
        result = consultant_node(compliance_state_after_auditor)
        titles = [t["title"] for t in result["todo_list"]]
        titles_lower = [t.lower() for t in titles]
        assert any("xhtml" in t or "ixbrl" in t for t in titles_lower), \
            "Must include XHTML/iXBRL report preparation item"
        assert any("auditor" in t or "assurance" in t for t in titles_lower), \
            "Must include auditor engagement item"

    def test_returns_final_compliance_check(self, compliance_state_after_auditor):
        from agents.consultant import consultant_node
        result = consultant_node(compliance_state_after_auditor)
        assert "final_compliance_check" in result
        assert isinstance(result["final_compliance_check"], ComplianceCheckResult)

    def test_final_compliance_check_has_correct_mode(self, compliance_state_after_auditor):
        from agents.consultant import consultant_node
        result = consultant_node(compliance_state_after_auditor)
        assert result["final_compliance_check"].mode == "compliance_check"

    def test_final_compliance_check_has_audit_id(self, compliance_state_after_auditor):
        from agents.consultant import consultant_node
        result = consultant_node(compliance_state_after_auditor)
        assert result["final_compliance_check"].audit_id == compliance_state_after_auditor["audit_id"]

    def test_pipeline_has_three_agents(self, compliance_state_after_auditor):
        from agents.consultant import consultant_node
        result = consultant_node(compliance_state_after_auditor)
        pipeline = result["final_compliance_check"].pipeline
        assert len(pipeline.agents) == 3
        agent_names = [a.agent for a in pipeline.agents]
        assert "fetcher" not in agent_names

    def test_does_not_return_full_audit_keys(self, compliance_state_after_auditor):
        from agents.consultant import consultant_node
        result = consultant_node(compliance_state_after_auditor)
        assert "roadmap" not in result
        assert "final_audit" not in result

    def test_final_compliance_check_json_serialisable(self, compliance_state_after_auditor):
        from agents.consultant import consultant_node
        result = consultant_node(compliance_state_after_auditor)
        json_str = result["final_compliance_check"].model_dump_json()
        parsed = json.loads(json_str)
        assert parsed["mode"] == "compliance_check"


# ===========================================================================
# FastAPI — Compliance Check Endpoint
# ===========================================================================


class TestComplianceCheckEndpoint:
    def test_compliance_check_returns_run_id(self):
        r = _upload_compliance_check()
        assert r.status_code == 200
        assert "run_id" in r.json()

    def test_compliance_check_run_id_is_valid_uuid(self):
        r = _upload_compliance_check()
        uuid.UUID(r.json()["run_id"])

    def test_rejects_compliance_check_without_free_text(self):
        r = client.post(
            "/audit/run",
            data={"entity_id": "Test", "mode": "compliance_check"},
        )
        assert r.status_code == 400

    def test_rejects_compliance_check_with_empty_free_text(self):
        r = client.post(
            "/audit/run",
            data={"entity_id": "Test", "mode": "compliance_check", "free_text": "   "},
        )
        assert r.status_code == 400

    def test_rejects_invalid_mode(self):
        r = client.post(
            "/audit/run",
            data={"entity_id": "Test", "mode": "invalid_mode"},
        )
        assert r.status_code == 400

    def test_full_audit_still_requires_report_json(self):
        r = client.post(
            "/audit/run",
            data={"entity_id": "Test", "mode": "full_audit"},
        )
        assert r.status_code == 400

    def test_compliance_check_result_cached(self):
        run_id = _run_and_wait_compliance()
        r = client.get(f"/audit/{run_id}")
        assert r.status_code == 200
        body = r.json()
        assert body["mode"] == "compliance_check"

    def test_compliance_check_result_has_todo_list(self):
        run_id = _run_and_wait_compliance()
        r = client.get(f"/audit/{run_id}")
        body = r.json()
        assert "todo_list" in body
        assert len(body["todo_list"]) > 0

    def test_compliance_check_result_has_esrs_coverage(self):
        run_id = _run_and_wait_compliance()
        r = client.get(f"/audit/{run_id}")
        body = r.json()
        assert "esrs_coverage" in body
        assert len(body["esrs_coverage"]) == 3

    def test_compliance_check_result_has_cost_estimate(self):
        run_id = _run_and_wait_compliance()
        r = client.get(f"/audit/{run_id}")
        body = r.json()
        assert "estimated_compliance_cost" in body


# ===========================================================================
# SSE — Compliance Check Mode
# ===========================================================================


class TestComplianceCheckSSE:
    def test_compliance_check_sse_has_three_node_completes(self):
        run_id = _run_and_wait_compliance()
        events = _collect_sse_events(run_id)
        node_completes = [e for e in events if e["type"] == "node_complete"]
        assert len(node_completes) == 3

    def test_compliance_check_sse_no_fetcher_events(self):
        run_id = _run_and_wait_compliance()
        events = _collect_sse_events(run_id)
        fetcher_events = [e for e in events if e.get("agent") == "fetcher"]
        assert len(fetcher_events) == 0, "Fetcher events should not appear in compliance check mode"

    def test_compliance_check_sse_agents_in_order(self):
        run_id = _run_and_wait_compliance()
        events = _collect_sse_events(run_id)
        node_completes = [e for e in events if e["type"] == "node_complete"]
        agents = [e["agent"] for e in node_completes]
        assert agents == ["extractor", "auditor", "consultant"]

    def test_compliance_check_complete_event_has_compliance_check_key(self):
        run_id = _run_and_wait_compliance()
        events = _collect_sse_events(run_id)
        complete = next(e for e in events if e["type"] == "complete")
        assert "compliance_check" in complete
        assert "audit" not in complete

    def test_compliance_check_complete_event_valid(self):
        run_id = _run_and_wait_compliance()
        events = _collect_sse_events(run_id)
        complete = next(e for e in events if e["type"] == "complete")
        cc = complete["compliance_check"]
        assert cc["mode"] == "compliance_check"
        assert cc["audit_id"] == run_id


# ===========================================================================
# Full Audit Regression — Verify Zero Breakage
# ===========================================================================


class TestFullAuditRegression:
    def test_full_audit_endpoint_still_works(self):
        r = _upload_full_audit()
        assert r.status_code == 200

    def test_full_audit_cached_result_still_valid(self):
        run_id = _run_and_wait_full_audit()
        r = client.get(f"/audit/{run_id}")
        assert r.status_code == 200
        body = r.json()
        assert body["schema_version"] == "2.0"
        assert "company" in body
        assert "esrs_ledger" in body
        assert "roadmap" in body

    def test_full_audit_sse_still_has_four_agents(self):
        run_id = _run_and_wait_full_audit()
        events = _collect_sse_events(run_id)
        node_completes = [e for e in events if e["type"] == "node_complete"]
        assert len(node_completes) == 4
        agents = [e["agent"] for e in node_completes]
        assert agents == ["extractor", "fetcher", "auditor", "consultant"]

    def test_full_audit_complete_event_has_audit_key(self):
        run_id = _run_and_wait_full_audit()
        events = _collect_sse_events(run_id)
        complete = next(e for e in events if e["type"] == "complete")
        assert "audit" in complete
        assert "compliance_check" not in complete

    def test_full_audit_default_mode(self):
        """POST without explicit mode should default to full_audit."""
        file_content = json.dumps(_SAMPLE_REPORT_JSON).encode()
        r = client.post(
            "/audit/run",
            files={"report_json": ("report.json", file_content, "application/json")},
            data={"entity_id": "DefaultMode Corp"},
        )
        assert r.status_code == 200
        run_id = r.json()["run_id"]
        time.sleep(2)
        r = client.get(f"/audit/{run_id}")
        body = r.json()
        assert "schema_version" in body  # CSRDAudit has this, ComplianceCheckResult doesn't have it at top level same way
        assert body.get("schema_version") == "2.0"

    def test_full_audit_pipeline_still_has_four_agents(self):
        run_id = _run_and_wait_full_audit()
        r = client.get(f"/audit/{run_id}")
        pipeline = r.json()["pipeline"]
        assert len(pipeline["agents"]) == 4


# ===========================================================================
# Gate Checks
# ===========================================================================


class TestGateChecks:
    def test_gate_schemas_ok(self):
        from schemas import CSRDAudit, ComplianceCheckResult  # noqa: F401
        assert True

    def test_gate_graph_ok(self):
        from graph import graph  # noqa: F401
        assert graph is not None

    def test_gate_compliance_check_end_to_end(self):
        """Gate: compliance_check graph produces final_compliance_check."""
        from graph import graph
        state = {
            "audit_id": "gate-test",
            "mode": "compliance_check",
            "free_text_input": "We aim for net-zero by 2045.",
            "entity_id": "GateCorp",
            "report_json": {},
            "esrs_data": {},
            "taxonomy_data": {},
            "logs": [],
            "pipeline_trace": [],
        }
        result = graph.invoke(state)
        assert "final_compliance_check" in result
        assert isinstance(result["final_compliance_check"], ComplianceCheckResult)
        assert result["final_compliance_check"].audit_id == "gate-test"

    def test_gate_full_audit_unchanged(self):
        """Gate: full_audit graph still produces final_audit."""
        from graph import graph
        state = {
            "audit_id": "gate-test-full",
            "mode": "full_audit",
            "report_json": {"report_info": {}, "facts": []},
            "esrs_data": {"facts": []},
            "taxonomy_data": {"facts": []},
            "entity_id": "GateCorp Full",
            "logs": [],
            "pipeline_trace": [],
        }
        result = graph.invoke(state)
        assert "final_audit" in result
        assert isinstance(result["final_audit"], CSRDAudit)
