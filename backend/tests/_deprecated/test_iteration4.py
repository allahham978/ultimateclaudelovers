"""
Iteration 4 Unit Tests — Dual-Mode Support (v5.0 Unified Pipeline)

Gate: graph.invoke({"mode":"free_text","free_text_input":"...","entity_id":"test",...})
      runs 3-node pipeline (extractor → scorer → advisor) and returns final_result.
      structured_document path unchanged (zero regression).

Tests cover:
  - Legacy Pydantic models (ExtractedGoal, ESRSCoverageItem, ComplianceTodo, etc.)
  - v5.0 Pydantic models (ComplianceResult, ComplianceScore, Recommendation)
  - AuditState dual-mode keys
  - Agent stubs in free_text mode
  - FastAPI endpoint dual-mode support (structured_document / free_text)
  - structured_document regression (unchanged behavior)
  - System prompt constants
"""

import json
import time
import uuid
from unittest.mock import MagicMock, patch

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
    ComplianceResult,
    ComplianceScore,
    ESRSCoverageItem,
    ExtractedGoal,
    Recommendation,
)

client = TestClient(app)


# ---------------------------------------------------------------------------
# Mock Claude API helpers for real extractor
# ---------------------------------------------------------------------------

def _mock_claude_response(text: str) -> MagicMock:
    """Create a mock Anthropic Messages API response."""
    block = MagicMock()
    block.text = text
    resp = MagicMock()
    resp.content = [block]
    return resp


_MOCK_EXTRACTOR_JSON = json.dumps({
    "company_meta": {
        "name": "TestCorp SA", "lei": "529900TESTCORP00001", "sector": "AI Infrastructure",
        "fiscal_year": 2024, "jurisdiction": "EU", "report_title": "Annual Management Report 2024",
    },
    "esrs_claims": {
        "E1-1": {"data_point": "Transition Plan", "disclosed_value": "Net-zero by 2040", "unit": None, "confidence": 0.85, "xbrl_concept": "esrs_E1-1_01"},
        "E1-5": {"data_point": "Energy Consumption", "disclosed_value": "45,000 MWh", "unit": "MWh", "confidence": 0.90, "xbrl_concept": "esrs_E1-5_04"},
        "E1-6": {"data_point": "GHG Emissions", "disclosed_value": "Scope 1: 1,200 tCO2eq", "unit": "tCO2eq", "confidence": 0.80, "xbrl_concept": "esrs_E1-6_01"},
    },
    "financial_context": {"capex_total_eur": 50000000, "capex_green_eur": 17500000, "opex_total_eur": 120000000, "opex_green_eur": 24000000, "revenue_eur": 250000000, "taxonomy_activities": [], "confidence": 0.92},
})

_MOCK_EXTRACTOR_LITE_JSON = json.dumps({
    "company_meta": {
        "name": "Lumiere Systemes SA", "lei": None, "sector": "AI Infrastructure",
        "fiscal_year": None, "jurisdiction": "FR", "report_title": "User-Provided Sustainability Description",
    },
    "esrs_claims": {
        "E1-1": {"data_point": "Transition Plan", "disclosed_value": "Net-zero target mentioned", "unit": None, "confidence": 0.5, "xbrl_concept": None},
        "E1-5": {"data_point": "Energy Consumption", "disclosed_value": None, "unit": None, "confidence": 0.0, "xbrl_concept": None},
        "E1-6": {"data_point": "GHG Emissions", "disclosed_value": None, "unit": None, "confidence": 0.0, "xbrl_concept": None},
    },
    "financial_context": None,
})


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


def _upload_structured(entity_id: str = "TestCorp SA") -> dict:
    """POST /audit/run in structured_document mode."""
    file_content = json.dumps(_SAMPLE_REPORT_JSON).encode()
    return client.post(
        "/audit/run",
        files={"report_json": ("report.json", file_content, "application/json")},
        data={"entity_id": entity_id, "mode": "structured_document"},
    )


def _upload_free_text(entity_id: str = "Lumiere SA", free_text: str = _SAMPLE_FREE_TEXT) -> dict:
    """POST /audit/run in free_text mode."""
    return client.post(
        "/audit/run",
        data={"entity_id": entity_id, "mode": "free_text", "free_text": free_text},
    )


def _run_and_wait_structured(entity_id: str = "TestCorp SA", wait: float = 2.0) -> str:
    r = _upload_structured(entity_id)
    run_id = r.json()["run_id"]
    time.sleep(wait)
    return run_id


def _run_and_wait_free_text(entity_id: str = "Lumiere SA", wait: float = 2.0) -> str:
    r = _upload_free_text(entity_id)
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
# Legacy Pydantic Models (still available for backward compat)
# ===========================================================================


class TestLegacySchemas:
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
# v5.0 Pydantic Models
# ===========================================================================


class TestV5Schemas:
    def test_compliance_result_import(self):
        from schemas import ComplianceResult  # noqa: F401

    def test_compliance_score_import(self):
        from schemas import ComplianceScore  # noqa: F401

    def test_recommendation_import(self):
        from schemas import Recommendation  # noqa: F401

    def test_company_inputs_import(self):
        from schemas import CompanyInputs  # noqa: F401

    def test_financial_context_import(self):
        from schemas import FinancialContext  # noqa: F401


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

    def test_auditstate_has_company_inputs_key(self):
        from state import AuditState
        from typing import get_type_hints

        hints = get_type_hints(AuditState)
        assert "company_inputs" in hints

    def test_auditstate_has_compliance_score_key(self):
        from state import AuditState
        from typing import get_type_hints

        hints = get_type_hints(AuditState)
        assert "compliance_score" in hints

    def test_auditstate_has_recommendations_key(self):
        from state import AuditState
        from typing import get_type_hints

        hints = get_type_hints(AuditState)
        assert "recommendations" in hints

    def test_auditstate_has_final_result_key(self):
        from state import AuditState
        from typing import get_type_hints

        hints = get_type_hints(AuditState)
        assert "final_result" in hints

    def test_auditstate_has_coverage_gaps_key(self):
        from state import AuditState
        from typing import get_type_hints

        hints = get_type_hints(AuditState)
        assert "coverage_gaps" in hints


# ===========================================================================
# System Prompts
# ===========================================================================


class TestSystemPrompts:
    def test_extractor_lite_prompt_exists(self):
        from tools.prompts import SYSTEM_PROMPT_EXTRACTOR_LITE
        assert len(SYSTEM_PROMPT_EXTRACTOR_LITE) > 100

    def test_scorer_prompt_exists(self):
        from tools.prompts import SYSTEM_PROMPT_SCORER
        assert len(SYSTEM_PROMPT_SCORER) > 100

    def test_advisor_prompt_exists(self):
        from tools.prompts import SYSTEM_PROMPT_ADVISOR
        assert len(SYSTEM_PROMPT_ADVISOR) > 100

    def test_extractor_lite_mentions_free_text(self):
        from tools.prompts import SYSTEM_PROMPT_EXTRACTOR_LITE
        assert "unstructured" in SYSTEM_PROMPT_EXTRACTOR_LITE.lower()

    def test_scorer_mentions_scoring(self):
        from tools.prompts import SYSTEM_PROMPT_SCORER
        assert "score" in SYSTEM_PROMPT_SCORER.lower()

    def test_advisor_mentions_recommendations(self):
        from tools.prompts import SYSTEM_PROMPT_ADVISOR
        assert "recommendation" in SYSTEM_PROMPT_ADVISOR.lower()

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
# Graph — v5.0 Linear Pipeline (no conditional routing)
# ===========================================================================


class TestGraphPipeline:
    @pytest.fixture(autouse=True)
    def _mock_extractor_api(self):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _mock_claude_response(_MOCK_EXTRACTOR_JSON)
        with patch("agents.extractor.anthropic.Anthropic", return_value=mock_client):
            yield

    def test_graph_imports(self):
        from graph import graph  # noqa: F401

    def test_free_text_graph_runs_end_to_end(self, compliance_check_state):
        from graph import graph
        result = graph.invoke(compliance_check_state)
        assert result is not None

    def test_free_text_produces_final_result(self, compliance_check_state):
        from graph import graph
        result = graph.invoke(compliance_check_state)
        assert "final_result" in result
        assert isinstance(result["final_result"], ComplianceResult)

    def test_free_text_runs_three_agents(self, compliance_check_state):
        from graph import graph
        result = graph.invoke(compliance_check_state)
        agents = [t["agent"] for t in result["pipeline_trace"]]
        assert agents == ["extractor", "scorer", "advisor"]

    def test_structured_graph_also_runs_three_agents(self, minimal_state):
        from graph import graph
        result = graph.invoke(minimal_state)
        agents = [t["agent"] for t in result["pipeline_trace"]]
        assert agents == ["extractor", "scorer", "advisor"]

    def test_structured_also_produces_final_result(self, minimal_state):
        from graph import graph
        result = graph.invoke(minimal_state)
        assert "final_result" in result
        assert isinstance(result["final_result"], ComplianceResult)


# ===========================================================================
# Extractor — Free Text Mode
# ===========================================================================


class TestExtractorFreeText:
    """Tests for extractor in free_text mode — requires mocking the Claude API."""

    @pytest.fixture(autouse=True)
    def _mock_extractor_api(self):
        """Mock the Claude API for all tests in this class."""
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _mock_claude_response(_MOCK_EXTRACTOR_LITE_JSON)
        with patch("agents.extractor.anthropic.Anthropic", return_value=mock_client):
            yield

    def test_returns_esrs_claims(self, compliance_check_state):
        from agents.extractor import extractor_node
        result = extractor_node(compliance_check_state)
        assert "esrs_claims" in result
        assert len(result["esrs_claims"]) == 3

    def test_xbrl_concept_is_none_in_free_text_mode(self, compliance_check_state):
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

    def test_logs_emitted_in_free_text_mode(self, compliance_check_state):
        from agents.extractor import extractor_node
        result = extractor_node(compliance_check_state)
        assert len(result["logs"]) >= 3
        assert all(l["agent"] == "extractor" for l in result["logs"])

    def test_no_financial_context_in_free_text(self, compliance_check_state):
        from agents.extractor import extractor_node
        result = extractor_node(compliance_check_state)
        assert "financial_context" not in result or result.get("financial_context") is None


# ===========================================================================
# Scorer — Both Modes
# ===========================================================================


class TestScorerNode:
    @pytest.fixture(autouse=True)
    def _mock_extractor_api(self):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _mock_claude_response(_MOCK_EXTRACTOR_LITE_JSON)
        with patch("agents.extractor.anthropic.Anthropic", return_value=mock_client):
            yield

    def test_returns_compliance_score(self, compliance_check_state):
        from agents.extractor import extractor_node
        from agents.scorer import scorer_node
        ext_result = extractor_node(compliance_check_state)
        state = {**compliance_check_state, **ext_result}
        result = scorer_node(state)
        assert "compliance_score" in result
        assert isinstance(result["compliance_score"], ComplianceScore)

    def test_score_in_valid_range(self, compliance_check_state):
        from agents.extractor import extractor_node
        from agents.scorer import scorer_node
        ext_result = extractor_node(compliance_check_state)
        state = {**compliance_check_state, **ext_result}
        result = scorer_node(state)
        assert 0 <= result["compliance_score"].overall <= 100

    def test_returns_coverage_gaps(self, compliance_check_state):
        from agents.extractor import extractor_node
        from agents.scorer import scorer_node
        ext_result = extractor_node(compliance_check_state)
        state = {**compliance_check_state, **ext_result}
        result = scorer_node(state)
        assert "coverage_gaps" in result
        assert isinstance(result["coverage_gaps"], list)


# ===========================================================================
# Advisor — Both Modes
# ===========================================================================


class TestAdvisorNode:
    @pytest.fixture(autouse=True)
    def _mock_extractor_api(self):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _mock_claude_response(_MOCK_EXTRACTOR_LITE_JSON)
        with patch("agents.extractor.anthropic.Anthropic", return_value=mock_client):
            yield

    def test_returns_recommendations(self, compliance_check_state):
        from agents.extractor import extractor_node
        from agents.scorer import scorer_node
        from agents.advisor import advisor_node
        ext_result = extractor_node(compliance_check_state)
        state = {**compliance_check_state, **ext_result}
        scorer_result = scorer_node(state)
        state = {**state, **scorer_result}
        result = advisor_node(state)
        assert "recommendations" in result
        assert isinstance(result["recommendations"], list)

    def test_returns_final_result(self, compliance_check_state):
        from agents.extractor import extractor_node
        from agents.scorer import scorer_node
        from agents.advisor import advisor_node
        ext_result = extractor_node(compliance_check_state)
        state = {**compliance_check_state, **ext_result}
        scorer_result = scorer_node(state)
        state = {**state, **scorer_result}
        result = advisor_node(state)
        assert "final_result" in result
        assert isinstance(result["final_result"], ComplianceResult)

    def test_final_result_has_correct_mode(self, compliance_check_state):
        from agents.extractor import extractor_node
        from agents.scorer import scorer_node
        from agents.advisor import advisor_node
        ext_result = extractor_node(compliance_check_state)
        state = {**compliance_check_state, **ext_result}
        scorer_result = scorer_node(state)
        state = {**state, **scorer_result}
        result = advisor_node(state)
        assert result["final_result"].mode == "free_text"

    def test_final_result_has_audit_id(self, compliance_check_state):
        from agents.extractor import extractor_node
        from agents.scorer import scorer_node
        from agents.advisor import advisor_node
        ext_result = extractor_node(compliance_check_state)
        state = {**compliance_check_state, **ext_result}
        scorer_result = scorer_node(state)
        state = {**state, **scorer_result}
        result = advisor_node(state)
        assert result["final_result"].audit_id == compliance_check_state["audit_id"]

    def test_pipeline_has_three_agents(self, compliance_check_state):
        from agents.extractor import extractor_node
        from agents.scorer import scorer_node
        from agents.advisor import advisor_node
        ext_result = extractor_node(compliance_check_state)
        state = {**compliance_check_state, **ext_result}
        scorer_result = scorer_node(state)
        state = {**state, **scorer_result}
        result = advisor_node(state)
        pipeline = result["final_result"].pipeline
        assert len(pipeline.agents) == 3
        agent_names = [a.agent for a in pipeline.agents]
        assert agent_names == ["extractor", "scorer", "advisor"]

    def test_final_result_json_serialisable(self, compliance_check_state):
        from agents.extractor import extractor_node
        from agents.scorer import scorer_node
        from agents.advisor import advisor_node
        ext_result = extractor_node(compliance_check_state)
        state = {**compliance_check_state, **ext_result}
        scorer_result = scorer_node(state)
        state = {**state, **scorer_result}
        result = advisor_node(state)
        json_str = result["final_result"].model_dump_json()
        parsed = json.loads(json_str)
        assert parsed["mode"] == "free_text"


# ===========================================================================
# FastAPI — Free Text Endpoint
# ===========================================================================


class TestFreeTextEndpoint:
    @pytest.fixture(autouse=True)
    def _mock_extractor_api(self):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _mock_claude_response(_MOCK_EXTRACTOR_LITE_JSON)
        with patch("agents.extractor.anthropic.Anthropic", return_value=mock_client):
            yield

    def test_free_text_returns_run_id(self):
        r = _upload_free_text()
        assert r.status_code == 200
        assert "run_id" in r.json()

    def test_free_text_run_id_is_valid_uuid(self):
        r = _upload_free_text()
        uuid.UUID(r.json()["run_id"])

    def test_rejects_free_text_without_text(self):
        r = client.post(
            "/audit/run",
            data={"entity_id": "Test", "mode": "free_text"},
        )
        assert r.status_code == 400

    def test_rejects_free_text_with_empty_text(self):
        r = client.post(
            "/audit/run",
            data={"entity_id": "Test", "mode": "free_text", "free_text": "   "},
        )
        assert r.status_code == 400

    def test_rejects_invalid_mode(self):
        r = client.post(
            "/audit/run",
            data={"entity_id": "Test", "mode": "invalid_mode"},
        )
        assert r.status_code == 400

    def test_structured_still_requires_report_json(self):
        r = client.post(
            "/audit/run",
            data={"entity_id": "Test", "mode": "structured_document"},
        )
        assert r.status_code == 400

    def test_free_text_result_cached(self):
        run_id = _run_and_wait_free_text()
        r = client.get(f"/audit/{run_id}")
        assert r.status_code == 200
        body = r.json()
        assert body["mode"] == "free_text"

    def test_free_text_result_has_score(self):
        run_id = _run_and_wait_free_text()
        r = client.get(f"/audit/{run_id}")
        body = r.json()
        assert "score" in body
        assert 0 <= body["score"]["overall"] <= 100

    def test_free_text_result_has_recommendations(self):
        run_id = _run_and_wait_free_text()
        r = client.get(f"/audit/{run_id}")
        body = r.json()
        assert "recommendations" in body
        assert isinstance(body["recommendations"], list)

    def test_free_text_result_has_company_inputs(self):
        run_id = _run_and_wait_free_text()
        r = client.get(f"/audit/{run_id}")
        body = r.json()
        assert "company_inputs" in body


# ===========================================================================
# SSE — Free Text Mode
# ===========================================================================


class TestFreeTextSSE:
    @pytest.fixture(autouse=True)
    def _mock_extractor_api(self):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _mock_claude_response(_MOCK_EXTRACTOR_LITE_JSON)
        with patch("agents.extractor.anthropic.Anthropic", return_value=mock_client):
            yield

    def test_free_text_sse_has_three_node_completes(self):
        run_id = _run_and_wait_free_text()
        events = _collect_sse_events(run_id)
        node_completes = [e for e in events if e["type"] == "node_complete"]
        assert len(node_completes) == 3

    def test_free_text_sse_no_fetcher_events(self):
        run_id = _run_and_wait_free_text()
        events = _collect_sse_events(run_id)
        fetcher_events = [e for e in events if e.get("agent") == "fetcher"]
        assert len(fetcher_events) == 0, "Fetcher events should not appear in v5.0 pipeline"

    def test_free_text_sse_agents_in_order(self):
        run_id = _run_and_wait_free_text()
        events = _collect_sse_events(run_id)
        node_completes = [e for e in events if e["type"] == "node_complete"]
        agents = [e["agent"] for e in node_completes]
        assert agents == ["extractor", "scorer", "advisor"]

    def test_free_text_complete_event_has_result_key(self):
        run_id = _run_and_wait_free_text()
        events = _collect_sse_events(run_id)
        complete = next(e for e in events if e["type"] == "complete")
        assert "result" in complete

    def test_free_text_complete_event_valid(self):
        run_id = _run_and_wait_free_text()
        events = _collect_sse_events(run_id)
        complete = next(e for e in events if e["type"] == "complete")
        result = complete["result"]
        assert result["mode"] == "free_text"
        assert result["audit_id"] == run_id


# ===========================================================================
# Structured Document Regression — Verify Zero Breakage
# ===========================================================================


class TestStructuredDocumentRegression:
    @pytest.fixture(autouse=True)
    def _mock_extractor_api(self):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _mock_claude_response(_MOCK_EXTRACTOR_JSON)
        with patch("agents.extractor.anthropic.Anthropic", return_value=mock_client):
            yield

    def test_structured_endpoint_still_works(self):
        r = _upload_structured()
        assert r.status_code == 200

    def test_structured_cached_result_still_valid(self):
        run_id = _run_and_wait_structured()
        r = client.get(f"/audit/{run_id}")
        assert r.status_code == 200
        body = r.json()
        assert body["schema_version"] == "3.0"
        assert "company" in body
        assert "score" in body
        assert "recommendations" in body

    def test_structured_sse_still_has_three_agents(self):
        run_id = _run_and_wait_structured()
        events = _collect_sse_events(run_id)
        node_completes = [e for e in events if e["type"] == "node_complete"]
        assert len(node_completes) == 3
        agents = [e["agent"] for e in node_completes]
        assert agents == ["extractor", "scorer", "advisor"]

    def test_structured_complete_event_has_result_key(self):
        run_id = _run_and_wait_structured()
        events = _collect_sse_events(run_id)
        complete = next(e for e in events if e["type"] == "complete")
        assert "result" in complete

    def test_structured_default_mode(self):
        """POST without explicit mode should default to structured_document."""
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
        assert body.get("schema_version") == "3.0"

    def test_structured_pipeline_still_has_three_agents(self):
        run_id = _run_and_wait_structured()
        r = client.get(f"/audit/{run_id}")
        pipeline = r.json()["pipeline"]
        assert len(pipeline["agents"]) == 3


# ===========================================================================
# Gate Checks
# ===========================================================================


class TestGateChecks:
    @pytest.fixture(autouse=True)
    def _mock_extractor_api(self):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _mock_claude_response(_MOCK_EXTRACTOR_JSON)
        with patch("agents.extractor.anthropic.Anthropic", return_value=mock_client):
            yield
    def test_gate_schemas_ok(self):
        from schemas import ComplianceResult, ComplianceScore  # noqa: F401
        assert True

    def test_gate_graph_ok(self):
        from graph import graph  # noqa: F401
        assert graph is not None

    def test_gate_free_text_end_to_end(self):
        """Gate: free_text graph produces final_result (ComplianceResult)."""
        from graph import graph
        from schemas import CompanyInputs
        state = {
            "audit_id": "gate-test",
            "mode": "free_text",
            "free_text_input": "We aim for net-zero by 2045.",
            "entity_id": "GateCorp",
            "company_inputs": CompanyInputs(
                number_of_employees=50, revenue_eur=5_000_000,
                total_assets_eur=2_000_000, reporting_year=2025,
            ),
            "report_json": {},
            "esrs_data": {},
            "taxonomy_data": {},
            "logs": [],
            "pipeline_trace": [],
        }
        result = graph.invoke(state)
        assert "final_result" in result
        assert isinstance(result["final_result"], ComplianceResult)
        assert result["final_result"].audit_id == "gate-test"

    def test_gate_structured_document_unchanged(self):
        """Gate: structured_document graph still produces final_result."""
        from graph import graph
        from schemas import CompanyInputs
        state = {
            "audit_id": "gate-test-full",
            "mode": "structured_document",
            "report_json": {"report_info": {}, "facts": []},
            "esrs_data": {"facts": []},
            "taxonomy_data": {"facts": []},
            "entity_id": "GateCorp Full",
            "company_inputs": CompanyInputs(
                number_of_employees=500, revenue_eur=85_000_000,
                total_assets_eur=42_000_000, reporting_year=2025,
            ),
            "logs": [],
            "pipeline_trace": [],
        }
        result = graph.invoke(state)
        assert "final_result" in result
        assert isinstance(result["final_result"], ComplianceResult)
