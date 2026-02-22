"""
End-to-end tests for the v5.0 unified 3-agent pipeline.

Tests both structured_document and free_text modes through the full
LangGraph pipeline (extractor → scorer → advisor) with mocked Claude API.
"""

import json
import sys
import os
from unittest.mock import MagicMock, patch

import pytest

_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from graph import graph
from schemas import ComplianceResult, CompanyInputs
from state import AuditState


# ---------------------------------------------------------------------------
# Mock response helpers
# ---------------------------------------------------------------------------

def _make_mock_response(text: str) -> MagicMock:
    mock_block = MagicMock()
    mock_block.text = text
    mock_resp = MagicMock()
    mock_resp.content = [mock_block]
    return mock_resp


EXTRACTOR_STRUCTURED_RESPONSE = json.dumps({
    "company_meta": {
        "name": "TestCorp SA",
        "lei": "529900TESTCORP00001",
        "sector": "AI Infrastructure",
        "fiscal_year": 2025,
        "jurisdiction": "EU",
        "report_title": "Annual Management Report 2025",
    },
    "esrs_claims": {
        "E1-1": {"data_point": "Transition Plan", "disclosed_value": "Net-zero by 2040", "unit": None, "confidence": 0.85, "xbrl_concept": "esrs_E1-1_01"},
        "E1-5": {"data_point": "Energy Consumption", "disclosed_value": "45,000 MWh", "unit": "MWh", "confidence": 0.90, "xbrl_concept": "esrs_E1-5_04"},
        "E1-6": {"data_point": "GHG Emissions", "disclosed_value": "Scope 1: 1,200 tCO2eq", "unit": "tCO2eq", "confidence": 0.80, "xbrl_concept": "esrs_E1-6_01"},
        "S1-6": {"data_point": "Employee Characteristics", "disclosed_value": "500 employees", "unit": None, "confidence": 0.75, "xbrl_concept": None},
        "G1-1": {"data_point": "Business Conduct", "disclosed_value": "Anti-corruption policy in place", "unit": None, "confidence": 0.70, "xbrl_concept": None},
    },
    "financial_context": {
        "capex_total_eur": 65000000.0,
        "capex_green_eur": 12000000.0,
        "opex_total_eur": 120000000.0,
        "opex_green_eur": 24000000.0,
        "revenue_eur": 85000000.0,
        "taxonomy_activities": ["8.1 Data processing"],
        "confidence": 0.88,
    },
})

EXTRACTOR_FREE_TEXT_RESPONSE = json.dumps({
    "company_meta": {
        "name": "GreenTech GmbH",
        "lei": None,
        "sector": "Software",
        "fiscal_year": 2025,
        "jurisdiction": "DE",
        "report_title": "User-Provided Sustainability Description",
    },
    "esrs_claims": {
        "E1-1": {"data_point": "Transition Plan", "disclosed_value": "Carbon neutral by 2035", "unit": None, "confidence": 0.5, "xbrl_concept": None},
    },
    "financial_context": None,
})

ADVISOR_RESPONSE = json.dumps({
    "recommendations": [
        {
            "id": "rec-1",
            "priority": "critical",
            "esrs_id": "E1-6",
            "title": "Complete GHG inventory",
            "description": "Conduct Scope 3 emissions screening.",
            "regulatory_reference": "ESRS E1-6, DR E1-6.44",
        },
        {
            "id": "rec-2",
            "priority": "high",
            "esrs_id": "E1-1",
            "title": "Quantify transition plan",
            "description": "Add interim milestones.",
            "regulatory_reference": "ESRS E1-1, DR E1-1.01",
        },
        {
            "id": "rec-3",
            "priority": "moderate",
            "esrs_id": "S1-6",
            "title": "Enhance workforce data",
            "description": "Add gender pay gap data.",
            "regulatory_reference": "ESRS S1-6, DR S1-6.48",
        },
    ]
})


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_claude():
    """Mock Claude API for both extractor and advisor agents."""
    from tools.prompts import SYSTEM_PROMPT_ADVISOR

    def _route(**kwargs):
        system = kwargs.get("system", "")
        if system == SYSTEM_PROMPT_ADVISOR:
            return _make_mock_response(ADVISOR_RESPONSE)
        return _make_mock_response(EXTRACTOR_STRUCTURED_RESPONSE)

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = _route

    with patch("agents.extractor.anthropic.Anthropic", return_value=mock_client), \
         patch("agents.advisor.anthropic.Anthropic", return_value=mock_client):
        yield mock_client


@pytest.fixture
def mock_claude_free_text():
    """Mock Claude API for free_text mode."""
    from tools.prompts import SYSTEM_PROMPT_ADVISOR

    def _route(**kwargs):
        system = kwargs.get("system", "")
        if system == SYSTEM_PROMPT_ADVISOR:
            return _make_mock_response(ADVISOR_RESPONSE)
        return _make_mock_response(EXTRACTOR_FREE_TEXT_RESPONSE)

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = _route

    with patch("agents.extractor.anthropic.Anthropic", return_value=mock_client), \
         patch("agents.advisor.anthropic.Anthropic", return_value=mock_client):
        yield mock_client


# ---------------------------------------------------------------------------
# End-to-end tests
# ---------------------------------------------------------------------------

class TestE2EStructuredDocument:
    """Full pipeline test: structured_document mode."""

    def test_full_pipeline_produces_compliance_result(self, mock_claude):
        """extractor → scorer → advisor should produce a valid ComplianceResult."""
        state: AuditState = {
            "audit_id": "e2e-structured-001",
            "mode": "structured_document",
            "report_json": {"facts": []},
            "esrs_data": {"facts": [
                {"ix_type": "ix:nonNumeric", "concept": "esrs_E1-1_01", "context_ref": "FY2025", "value": "Net-zero by 2040"},
            ]},
            "taxonomy_data": {"facts": [
                {"ix_type": "ix:nonFraction", "concept": "eutaxonomy:CapExTotal", "context_ref": "FY2025", "value": "65000000", "unit_ref": "iso4217:EUR"},
            ]},
            "entity_id": "TestCorp SA",
            "company_inputs": CompanyInputs(
                number_of_employees=500,
                revenue_eur=85_000_000.0,
                total_assets_eur=42_000_000.0,
                reporting_year=2025,
            ),
            "logs": [],
            "pipeline_trace": [],
        }

        result = graph.invoke(state)

        # Final result should exist
        assert "final_result" in result
        final = result["final_result"]
        assert isinstance(final, ComplianceResult)

        # Check basic fields
        assert final.audit_id == "e2e-structured-001"
        assert final.mode == "structured_document"
        assert final.schema_version == "3.0"

        # Company meta should be populated
        assert final.company.name == "TestCorp SA"

        # Score should be computed
        assert 0 <= final.score.overall <= 100
        assert final.score.size_category != ""
        assert final.score.applicable_standards_count > 0

        # Recommendations should exist
        assert len(final.recommendations) > 0
        for rec in final.recommendations:
            assert rec.priority in ("critical", "high", "moderate", "low")
            assert rec.esrs_id != ""

        # Pipeline trace should have 3 agents
        assert final.pipeline.total_duration_ms >= 0
        assert len(final.pipeline.agents) == 3
        agent_names = [a.agent for a in final.pipeline.agents]
        assert agent_names == ["extractor", "scorer", "advisor"]
        for agent in final.pipeline.agents:
            assert agent.status == "completed"

    def test_logs_accumulated(self, mock_claude):
        """Pipeline should accumulate log entries from all 3 agents."""
        state: AuditState = {
            "audit_id": "e2e-logs-001",
            "mode": "structured_document",
            "report_json": {"facts": []},
            "esrs_data": {"facts": []},
            "taxonomy_data": {"facts": []},
            "entity_id": "TestCorp SA",
            "company_inputs": CompanyInputs(
                number_of_employees=500,
                revenue_eur=85_000_000.0,
                total_assets_eur=42_000_000.0,
                reporting_year=2025,
            ),
            "logs": [],
            "pipeline_trace": [],
        }

        result = graph.invoke(state)

        logs = result.get("logs", [])
        assert len(logs) > 0

        # Should have logs from all 3 agents
        agents_in_logs = set(log["agent"] for log in logs)
        assert "extractor" in agents_in_logs
        assert "scorer" in agents_in_logs
        assert "advisor" in agents_in_logs

    def test_pipeline_trace_has_timings(self, mock_claude):
        """Pipeline trace should record execution time for each agent."""
        state: AuditState = {
            "audit_id": "e2e-trace-001",
            "mode": "structured_document",
            "report_json": {"facts": []},
            "esrs_data": {"facts": []},
            "taxonomy_data": {"facts": []},
            "entity_id": "TestCorp SA",
            "company_inputs": CompanyInputs(
                number_of_employees=500,
                revenue_eur=85_000_000.0,
                total_assets_eur=42_000_000.0,
                reporting_year=2025,
            ),
            "logs": [],
            "pipeline_trace": [],
        }

        result = graph.invoke(state)

        trace = result.get("pipeline_trace", [])
        assert len(trace) == 3
        for entry in trace:
            assert "agent" in entry
            assert "ms" in entry
            assert entry["ms"] >= 0


class TestE2EFreeText:
    """Full pipeline test: free_text mode."""

    def test_full_pipeline_free_text(self, mock_claude_free_text):
        """Free text mode should produce a valid ComplianceResult with no financial_context."""
        state: AuditState = {
            "audit_id": "e2e-freetext-001",
            "mode": "free_text",
            "free_text_input": (
                "We are a software company in Germany with 200 employees. "
                "We have committed to being carbon neutral by 2035. "
                "Current energy consumption is approximately 5,000 MWh annually."
            ),
            "entity_id": "GreenTech GmbH",
            "company_inputs": CompanyInputs(
                number_of_employees=200,
                revenue_eur=30_000_000.0,
                total_assets_eur=15_000_000.0,
                reporting_year=2025,
            ),
            "report_json": {},
            "esrs_data": {},
            "taxonomy_data": {},
            "logs": [],
            "pipeline_trace": [],
        }

        result = graph.invoke(state)

        assert "final_result" in result
        final = result["final_result"]
        assert isinstance(final, ComplianceResult)

        assert final.mode == "free_text"
        assert final.audit_id == "e2e-freetext-001"
        assert 0 <= final.score.overall <= 100

        # Free text typically has lower scores due to less disclosed data
        assert len(final.recommendations) > 0

        # Pipeline should have 3 agents
        assert len(final.pipeline.agents) == 3

    def test_financial_context_none_in_free_text(self, mock_claude_free_text):
        """In free_text mode, financial_context should be None."""
        state: AuditState = {
            "audit_id": "e2e-freetext-fc-001",
            "mode": "free_text",
            "free_text_input": "Basic sustainability info.",
            "entity_id": "TestCo",
            "company_inputs": CompanyInputs(
                number_of_employees=100,
                revenue_eur=10_000_000.0,
                total_assets_eur=5_000_000.0,
                reporting_year=2025,
            ),
            "report_json": {},
            "esrs_data": {},
            "taxonomy_data": {},
            "logs": [],
            "pipeline_trace": [],
        }

        result = graph.invoke(state)

        # financial_context should be None for free_text mode
        assert result.get("financial_context") is None


class TestE2ECompanyInputsValidation:
    """Test that company inputs drive correct size categorization."""

    def test_large_undertaking_classification(self, mock_claude):
        """500 employees + EUR 85M revenue → large_undertaking."""
        state: AuditState = {
            "audit_id": "e2e-size-large-001",
            "mode": "structured_document",
            "report_json": {"facts": []},
            "esrs_data": {"facts": []},
            "taxonomy_data": {"facts": []},
            "entity_id": "BigCorp",
            "company_inputs": CompanyInputs(
                number_of_employees=500,
                revenue_eur=85_000_000.0,
                total_assets_eur=42_000_000.0,
                reporting_year=2025,
            ),
            "logs": [],
            "pipeline_trace": [],
        }

        result = graph.invoke(state)
        final = result["final_result"]
        assert final.score.size_category == "large_pie"

    def test_small_company_classification(self, mock_claude_free_text):
        """50 employees + EUR 5M revenue → should not be large_undertaking."""
        state: AuditState = {
            "audit_id": "e2e-size-small-001",
            "mode": "free_text",
            "free_text_input": "Small company sustainability info.",
            "entity_id": "SmallCo",
            "company_inputs": CompanyInputs(
                number_of_employees=50,
                revenue_eur=5_000_000.0,
                total_assets_eur=2_000_000.0,
                reporting_year=2025,
            ),
            "report_json": {},
            "esrs_data": {},
            "taxonomy_data": {},
            "logs": [],
            "pipeline_trace": [],
        }

        result = graph.invoke(state)
        final = result["final_result"]
        # Small company should not be classified as large_undertaking
        assert final.score.size_category != "large_undertaking"
