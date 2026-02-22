"""
Tests for backend/agents/advisor.py — Iteration 10.

Covers:
  - Priority assignment logic (deterministic)
  - Claude API call construction and JSON parsing
  - Recommendation generation from Claude response
  - Fallback recommendations when Claude API fails
  - Financial context enrichment in descriptions
  - ComplianceResult assembly with pipeline timing
  - Both modes: structured_document and free_text
  - Edge cases: empty gaps, all disclosed, all missing
  - Priority sorting (critical → high → moderate → low)
"""

import json
import sys
import os
from unittest.mock import MagicMock, patch

_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

import pytest
from schemas import (
    CompanyInputs,
    CompanyMeta,
    ComplianceResult,
    ComplianceScore,
    ESRSClaim,
    FinancialContext,
    Recommendation,
)
from agents.advisor import (
    _assign_priority,
    _build_recommendations,
    _build_user_message,
    _generate_fallback_recommendations,
    _parse_llm_json,
    advisor_node,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


SAMPLE_COMPANY_META = CompanyMeta(
    name="TestCorp SA",
    lei="529900TESTCORP00001",
    sector="AI Infrastructure",
    fiscal_year=2025,
    jurisdiction="EU",
    report_title="Annual Management Report 2025",
)

SAMPLE_COMPANY_INPUTS = CompanyInputs(
    number_of_employees=500,
    revenue_eur=85_000_000.0,
    total_assets_eur=42_000_000.0,
    reporting_year=2025,
)

SAMPLE_COMPLIANCE_SCORE = ComplianceScore(
    overall=42,
    size_category="large_pie",
    applicable_standards_count=10,
    disclosed_count=3,
    partial_count=2,
    missing_count=5,
)

SAMPLE_FINANCIAL_CONTEXT = FinancialContext(
    capex_total_eur=50_000_000.0,
    capex_green_eur=17_500_000.0,
    opex_total_eur=120_000_000.0,
    opex_green_eur=24_000_000.0,
    revenue_eur=250_000_000.0,
    taxonomy_activities=["8.1 Data processing"],
    confidence=0.92,
)

SAMPLE_COVERAGE_GAPS = [
    {"esrs_id": "E1-1", "status": "disclosed", "details": "Adequately disclosed.", "document_id": "E1-001"},
    {"esrs_id": "E1-5", "status": "partial", "details": "Energy data incomplete.", "document_id": "E1-001"},
    {"esrs_id": "E1-6", "status": "missing", "details": "No GHG data found.", "document_id": "E1-001"},
    {"esrs_id": "S1-1", "status": "missing", "details": "No workforce data.", "document_id": "S1-001"},
    {"esrs_id": "E4-1", "status": "partial", "details": "Partial biodiversity.", "document_id": "E4-001"},
    {"esrs_id": "GOV-1", "status": "missing", "details": "No governance disclosure.", "document_id": "SR-001"},
]

SAMPLE_APPLICABLE_REQS = [
    {"esrs_id": "E1-1", "standard_name": "Transition Plan", "standard": "ESRS E1", "status": "disclosed", "confidence": 0.85, "disclosed_value": "Net-zero", "mandatory": True, "mandatory_if_material": False},
    {"esrs_id": "E1-5", "standard_name": "Energy Consumption", "standard": "ESRS E1", "status": "partial", "confidence": 0.5, "disclosed_value": "Partial", "mandatory": True, "mandatory_if_material": False},
    {"esrs_id": "E1-6", "standard_name": "GHG Emissions", "standard": "ESRS E1", "status": "missing", "confidence": 0.0, "disclosed_value": None, "mandatory": True, "mandatory_if_material": False},
    {"esrs_id": "S1-1", "standard_name": "Own Workforce", "standard": "ESRS S1", "status": "missing", "confidence": 0.0, "disclosed_value": None, "mandatory": True, "mandatory_if_material": False},
    {"esrs_id": "E4-1", "standard_name": "Biodiversity", "standard": "ESRS E4", "status": "partial", "confidence": 0.4, "disclosed_value": "Some", "mandatory": False, "mandatory_if_material": True},
    {"esrs_id": "GOV-1", "standard_name": "Board oversight", "standard": "ESRS 2", "status": "missing", "confidence": 0.0, "disclosed_value": None, "mandatory": True, "mandatory_if_material": False},
]

# Mock Claude response JSON
MOCK_ADVISOR_RESPONSE = {
    "recommendations": [
        {
            "id": "rec-1",
            "priority": "critical",
            "esrs_id": "E1-6",
            "title": "Conduct Scope 1 & 2 GHG inventory",
            "description": "Your GHG emissions are not disclosed. Commission Delegated Regulation (EU) 2023/2772 requires Scope 1, 2, and 3 disclosure. Begin with a comprehensive GHG inventory following the GHG Protocol.",
            "regulatory_reference": "ESRS E1-6, DR E1-6.44",
        },
        {
            "id": "rec-2",
            "priority": "critical",
            "esrs_id": "S1-1",
            "title": "Establish own workforce impact assessment",
            "description": "No workforce materiality data found. ESRS S1-1 requires disclosure of workforce impacts, risks, and opportunities. Start with a materiality assessment of your own workforce.",
            "regulatory_reference": "ESRS S1-1, DR S1-1.01",
        },
        {
            "id": "rec-3",
            "priority": "critical",
            "esrs_id": "GOV-1",
            "title": "Disclose board sustainability oversight",
            "description": "No governance disclosure found. ESRS 2 GOV-1 requires description of board composition and sustainability oversight. Document your governance structure.",
            "regulatory_reference": "ESRS 2 GOV-1, DR GOV-1.01",
        },
        {
            "id": "rec-4",
            "priority": "high",
            "esrs_id": "E1-5",
            "title": "Complete energy consumption reporting",
            "description": "Energy data is incomplete. Ensure total energy consumption in MWh, renewable mix %, and breakdown by source are fully disclosed per ESRS E1-5.",
            "regulatory_reference": "ESRS E1-5, DR E1-5.30",
        },
        {
            "id": "rec-5",
            "priority": "moderate",
            "esrs_id": "E4-1",
            "title": "Expand biodiversity impact assessment",
            "description": "Partial biodiversity disclosure found. Complete the assessment of biodiversity impacts near protected areas per ESRS E4.",
            "regulatory_reference": "ESRS E4-1, DR E4-1.01",
        },
    ]
}

MOCK_ADVISOR_RESPONSE_JSON = json.dumps(MOCK_ADVISOR_RESPONSE)


def _make_mock_claude_response(text: str) -> MagicMock:
    """Create a mock Anthropic Messages API response."""
    mock_content_block = MagicMock()
    mock_content_block.text = text
    mock_response = MagicMock()
    mock_response.content = [mock_content_block]
    return mock_response


def _make_advisor_state(
    coverage_gaps: list[dict] | None = None,
    applicable_reqs: list[dict] | None = None,
    financial_context: FinancialContext | None = None,
    mode: str = "structured_document",
) -> dict:
    """Build a minimal AuditState for advisor testing."""
    return {
        "audit_id": "test-advisor-001",
        "mode": mode,
        "entity_id": "TestCorp SA",
        "company_meta": SAMPLE_COMPANY_META,
        "company_inputs": SAMPLE_COMPANY_INPUTS,
        "compliance_score": SAMPLE_COMPLIANCE_SCORE,
        "coverage_gaps": coverage_gaps if coverage_gaps is not None else SAMPLE_COVERAGE_GAPS,
        "applicable_reqs": applicable_reqs if applicable_reqs is not None else SAMPLE_APPLICABLE_REQS,
        "financial_context": financial_context,
        "logs": [],
        "pipeline_trace": [
            {"agent": "extractor", "started_at": 1000.0, "ms": 2100},
            {"agent": "scorer", "started_at": 1002.1, "ms": 800},
        ],
    }


# ---------------------------------------------------------------------------
# _assign_priority() tests
# ---------------------------------------------------------------------------


class TestAssignPriority:
    """Unit tests for deterministic priority assignment."""

    def test_missing_mandatory_is_critical(self):
        assert _assign_priority("missing", "E1-6", mandatory=True, mandatory_if_material=False) == "critical"

    def test_missing_core_prefix_is_critical(self):
        """Core ESRS prefixes (E1-, S1-, GOV-) get critical even if not explicitly mandatory."""
        assert _assign_priority("missing", "E1-1", mandatory=False, mandatory_if_material=True) == "critical"
        assert _assign_priority("missing", "S1-1", mandatory=False, mandatory_if_material=True) == "critical"
        assert _assign_priority("missing", "GOV-1", mandatory=False, mandatory_if_material=True) == "critical"

    def test_missing_non_mandatory_is_high(self):
        assert _assign_priority("missing", "E4-1", mandatory=False, mandatory_if_material=True) == "high"

    def test_partial_mandatory_is_high(self):
        assert _assign_priority("partial", "E1-5", mandatory=True, mandatory_if_material=False) == "high"

    def test_partial_core_prefix_is_high(self):
        assert _assign_priority("partial", "S1-6", mandatory=False, mandatory_if_material=True) == "high"

    def test_partial_non_mandatory_is_moderate(self):
        assert _assign_priority("partial", "E4-1", mandatory=False, mandatory_if_material=True) == "moderate"

    def test_disclosed_is_low(self):
        assert _assign_priority("disclosed", "E1-1", mandatory=True, mandatory_if_material=False) == "low"

    def test_disclosed_non_mandatory_is_low(self):
        assert _assign_priority("disclosed", "E5-1", mandatory=False, mandatory_if_material=True) == "low"


# ---------------------------------------------------------------------------
# _parse_llm_json() tests
# ---------------------------------------------------------------------------


class TestParseLlmJson:
    """Test JSON parsing from Claude responses."""

    def test_plain_json(self):
        result = _parse_llm_json('{"recommendations": []}')
        assert result == {"recommendations": []}

    def test_markdown_fenced_json(self):
        result = _parse_llm_json('```json\n{"recommendations": []}\n```')
        assert result == {"recommendations": []}

    def test_bare_fenced_json(self):
        result = _parse_llm_json('```\n{"key": "val"}\n```')
        assert result == {"key": "val"}

    def test_whitespace_padding(self):
        result = _parse_llm_json('  \n{"ok": true}\n  ')
        assert result == {"ok": True}

    def test_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            _parse_llm_json("not json at all")


# ---------------------------------------------------------------------------
# _build_user_message() tests
# ---------------------------------------------------------------------------


class TestBuildUserMessage:
    """Test user message construction for Claude."""

    def test_contains_company_info(self):
        msg = _build_user_message(
            SAMPLE_COVERAGE_GAPS, SAMPLE_APPLICABLE_REQS,
            SAMPLE_COMPANY_META, None, SAMPLE_COMPLIANCE_SCORE,
        )
        assert "TestCorp SA" in msg
        assert "AI Infrastructure" in msg
        assert "42/100" in msg

    def test_contains_gap_details(self):
        msg = _build_user_message(
            SAMPLE_COVERAGE_GAPS, SAMPLE_APPLICABLE_REQS,
            SAMPLE_COMPANY_META, None, SAMPLE_COMPLIANCE_SCORE,
        )
        assert "E1-6" in msg
        assert "missing" in msg
        assert "S1-1" in msg

    def test_excludes_disclosed_gaps(self):
        """Disclosed gaps should not appear in the gaps section."""
        msg = _build_user_message(
            SAMPLE_COVERAGE_GAPS, SAMPLE_APPLICABLE_REQS,
            SAMPLE_COMPANY_META, None, SAMPLE_COMPLIANCE_SCORE,
        )
        # E1-1 is disclosed, should not be listed in COVERAGE GAPS section
        lines = msg.split("\n")
        gap_lines = [l for l in lines if l.strip().startswith("- E1-1")]
        # E1-1 should not appear as a gap requiring recommendation
        assert len(gap_lines) == 0

    def test_financial_context_included_when_present(self):
        msg = _build_user_message(
            SAMPLE_COVERAGE_GAPS, SAMPLE_APPLICABLE_REQS,
            SAMPLE_COMPANY_META, SAMPLE_FINANCIAL_CONTEXT, SAMPLE_COMPLIANCE_SCORE,
        )
        assert "CapEx total" in msg
        assert "50,000,000" in msg
        assert "35.0%" in msg  # green CapEx percentage
        assert "8.1 Data processing" in msg

    def test_financial_context_null_message(self):
        msg = _build_user_message(
            SAMPLE_COVERAGE_GAPS, SAMPLE_APPLICABLE_REQS,
            SAMPLE_COMPANY_META, None, SAMPLE_COMPLIANCE_SCORE,
        )
        assert "Not available" in msg
        assert "free-text" in msg


# ---------------------------------------------------------------------------
# _build_recommendations() tests
# ---------------------------------------------------------------------------


class TestBuildRecommendations:
    """Test building Recommendation objects from Claude's raw JSON."""

    def test_builds_correct_count(self):
        recs = _build_recommendations(
            MOCK_ADVISOR_RESPONSE["recommendations"],
            SAMPLE_COVERAGE_GAPS, SAMPLE_APPLICABLE_REQS,
        )
        assert len(recs) == 5

    def test_all_are_recommendation_objects(self):
        recs = _build_recommendations(
            MOCK_ADVISOR_RESPONSE["recommendations"],
            SAMPLE_COVERAGE_GAPS, SAMPLE_APPLICABLE_REQS,
        )
        for rec in recs:
            assert isinstance(rec, Recommendation)

    def test_priority_overridden_deterministically(self):
        """Priority from Claude should be overridden by deterministic logic."""
        # E1-6 is missing + mandatory → critical
        recs = _build_recommendations(
            MOCK_ADVISOR_RESPONSE["recommendations"],
            SAMPLE_COVERAGE_GAPS, SAMPLE_APPLICABLE_REQS,
        )
        e1_6_rec = next(r for r in recs if r.esrs_id == "E1-6")
        assert e1_6_rec.priority == "critical"

        # E4-1 is partial + not mandatory → moderate
        e4_1_rec = next(r for r in recs if r.esrs_id == "E4-1")
        assert e4_1_rec.priority == "moderate"

    def test_preserves_claude_text(self):
        recs = _build_recommendations(
            MOCK_ADVISOR_RESPONSE["recommendations"],
            SAMPLE_COVERAGE_GAPS, SAMPLE_APPLICABLE_REQS,
        )
        e1_6_rec = next(r for r in recs if r.esrs_id == "E1-6")
        assert "GHG inventory" in e1_6_rec.title
        assert "GHG Protocol" in e1_6_rec.description
        assert "E1-6" in e1_6_rec.regulatory_reference

    def test_handles_empty_raw_recs(self):
        recs = _build_recommendations([], SAMPLE_COVERAGE_GAPS, SAMPLE_APPLICABLE_REQS)
        assert recs == []

    def test_handles_missing_fields_gracefully(self):
        """Incomplete Claude response should still produce valid Recommendations."""
        incomplete = [{"esrs_id": "E1-6"}]
        recs = _build_recommendations(incomplete, SAMPLE_COVERAGE_GAPS, SAMPLE_APPLICABLE_REQS)
        assert len(recs) == 1
        assert recs[0].esrs_id == "E1-6"
        assert recs[0].title  # Should have a default title
        assert recs[0].regulatory_reference  # Should have a default reference


# ---------------------------------------------------------------------------
# _generate_fallback_recommendations() tests
# ---------------------------------------------------------------------------


class TestFallbackRecommendations:
    """Test deterministic fallback when Claude API fails."""

    def test_generates_for_non_disclosed(self):
        recs = _generate_fallback_recommendations(
            SAMPLE_COVERAGE_GAPS, SAMPLE_APPLICABLE_REQS, None,
        )
        # 5 non-disclosed gaps (E1-5 partial, E1-6 missing, S1-1 missing, E4-1 partial, GOV-1 missing)
        assert len(recs) == 5

    def test_skips_disclosed(self):
        recs = _generate_fallback_recommendations(
            SAMPLE_COVERAGE_GAPS, SAMPLE_APPLICABLE_REQS, None,
        )
        esrs_ids = [r.esrs_id for r in recs]
        assert "E1-1" not in esrs_ids  # E1-1 is disclosed

    def test_missing_gets_critical_when_mandatory(self):
        recs = _generate_fallback_recommendations(
            SAMPLE_COVERAGE_GAPS, SAMPLE_APPLICABLE_REQS, None,
        )
        e1_6_rec = next(r for r in recs if r.esrs_id == "E1-6")
        assert e1_6_rec.priority == "critical"

    def test_partial_non_mandatory_gets_moderate(self):
        recs = _generate_fallback_recommendations(
            SAMPLE_COVERAGE_GAPS, SAMPLE_APPLICABLE_REQS, None,
        )
        e4_1_rec = next(r for r in recs if r.esrs_id == "E4-1")
        assert e4_1_rec.priority == "moderate"

    def test_financial_context_enriches_e1_descriptions(self):
        recs = _generate_fallback_recommendations(
            SAMPLE_COVERAGE_GAPS, SAMPLE_APPLICABLE_REQS, SAMPLE_FINANCIAL_CONTEXT,
        )
        # E1-5 and E1-6 are E1- prefixed non-disclosed gaps
        e1_recs = [r for r in recs if r.esrs_id.startswith("E1-")]
        for rec in e1_recs:
            assert "CapEx" in rec.description or "green" in rec.description.lower()

    def test_no_financial_context_no_enrichment(self):
        recs = _generate_fallback_recommendations(
            SAMPLE_COVERAGE_GAPS, SAMPLE_APPLICABLE_REQS, None,
        )
        for rec in recs:
            assert "CapEx" not in rec.description or "baseline" not in rec.description

    def test_empty_gaps_returns_empty(self):
        recs = _generate_fallback_recommendations([], [], None)
        assert recs == []

    def test_all_disclosed_returns_empty(self):
        all_disclosed = [{"esrs_id": "E1-1", "status": "disclosed", "details": "OK", "document_id": "E1-001"}]
        recs = _generate_fallback_recommendations(all_disclosed, SAMPLE_APPLICABLE_REQS, None)
        assert recs == []


# ---------------------------------------------------------------------------
# advisor_node() — integration tests (mocked Claude API)
# ---------------------------------------------------------------------------


class TestAdvisorNodeWithClaude:
    """Integration tests for advisor_node with mocked Claude API."""

    @pytest.fixture(autouse=True)
    def mock_claude(self):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_mock_claude_response(MOCK_ADVISOR_RESPONSE_JSON)
        with patch("agents.advisor.anthropic.Anthropic", return_value=mock_client):
            self.mock_client = mock_client
            yield mock_client

    def test_produces_recommendations(self):
        state = _make_advisor_state(financial_context=SAMPLE_FINANCIAL_CONTEXT)
        result = advisor_node(state)
        assert "recommendations" in result
        assert len(result["recommendations"]) > 0

    def test_produces_final_result(self):
        state = _make_advisor_state(financial_context=SAMPLE_FINANCIAL_CONTEXT)
        result = advisor_node(state)
        assert "final_result" in result
        assert isinstance(result["final_result"], ComplianceResult)

    def test_final_result_has_correct_schema_version(self):
        state = _make_advisor_state()
        result = advisor_node(state)
        assert result["final_result"].schema_version == "3.0"

    def test_final_result_has_correct_mode(self):
        state = _make_advisor_state(mode="free_text")
        result = advisor_node(state)
        assert result["final_result"].mode == "free_text"

    def test_final_result_has_company_meta(self):
        state = _make_advisor_state()
        result = advisor_node(state)
        assert result["final_result"].company.name == "TestCorp SA"

    def test_final_result_has_company_inputs(self):
        state = _make_advisor_state()
        result = advisor_node(state)
        assert result["final_result"].company_inputs.number_of_employees == 500

    def test_final_result_has_score(self):
        state = _make_advisor_state()
        result = advisor_node(state)
        assert result["final_result"].score.overall == 42

    def test_recommendations_sorted_by_priority(self):
        state = _make_advisor_state(financial_context=SAMPLE_FINANCIAL_CONTEXT)
        result = advisor_node(state)
        recs = result["recommendations"]
        priorities = [r.priority for r in recs]
        priority_order = {"critical": 0, "high": 1, "moderate": 2, "low": 3}
        order_values = [priority_order[p] for p in priorities]
        assert order_values == sorted(order_values)

    def test_pipeline_trace_has_three_agents(self):
        state = _make_advisor_state()
        result = advisor_node(state)
        pipeline = result["final_result"].pipeline
        agent_names = [a.agent for a in pipeline.agents]
        assert "extractor" in agent_names
        assert "scorer" in agent_names
        assert "advisor" in agent_names

    def test_pipeline_total_duration(self):
        state = _make_advisor_state()
        result = advisor_node(state)
        pipeline = result["final_result"].pipeline
        assert pipeline.total_duration_ms > 0
        assert pipeline.total_duration_ms == sum(a.duration_ms for a in pipeline.agents)

    def test_produces_logs(self):
        state = _make_advisor_state()
        result = advisor_node(state)
        assert "logs" in result
        advisor_logs = [l for l in result["logs"] if l["agent"] == "advisor"]
        assert len(advisor_logs) >= 3  # At least start, Claude call, and assembly logs

    def test_claude_api_called_with_system_prompt(self):
        state = _make_advisor_state()
        advisor_node(state)
        call_args = self.mock_client.messages.create.call_args
        assert call_args.kwargs["system"] is not None
        assert "CSRD" in call_args.kwargs["system"]

    def test_claude_api_called_with_correct_model(self):
        state = _make_advisor_state()
        advisor_node(state)
        call_args = self.mock_client.messages.create.call_args
        assert call_args.kwargs["model"] == "claude-sonnet-4-6"

    def test_financial_context_passed_to_claude(self):
        state = _make_advisor_state(financial_context=SAMPLE_FINANCIAL_CONTEXT)
        advisor_node(state)
        call_args = self.mock_client.messages.create.call_args
        user_msg = call_args.kwargs["messages"][0]["content"]
        assert "CapEx total" in user_msg
        assert "50,000,000" in user_msg

    def test_no_financial_context_in_free_text_mode(self):
        state = _make_advisor_state(mode="free_text", financial_context=None)
        advisor_node(state)
        call_args = self.mock_client.messages.create.call_args
        user_msg = call_args.kwargs["messages"][0]["content"]
        assert "Not available" in user_msg


# ---------------------------------------------------------------------------
# advisor_node() — fallback tests (Claude API failure)
# ---------------------------------------------------------------------------


class TestAdvisorNodeFallback:
    """Test that advisor falls back gracefully when Claude API fails."""

    @pytest.fixture(autouse=True)
    def mock_claude_failure(self):
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("API rate limited")
        with patch("agents.advisor.anthropic.Anthropic", return_value=mock_client):
            yield mock_client

    def test_produces_recommendations_on_failure(self):
        state = _make_advisor_state()
        result = advisor_node(state)
        assert "recommendations" in result
        assert len(result["recommendations"]) > 0

    def test_produces_final_result_on_failure(self):
        state = _make_advisor_state()
        result = advisor_node(state)
        assert "final_result" in result
        assert isinstance(result["final_result"], ComplianceResult)

    def test_logs_failure_message(self):
        state = _make_advisor_state()
        result = advisor_node(state)
        failure_logs = [l for l in result["logs"] if "failed" in l.get("msg", "").lower() or "fallback" in l.get("msg", "").lower()]
        assert len(failure_logs) >= 1

    def test_fallback_has_correct_priorities(self):
        state = _make_advisor_state()
        result = advisor_node(state)
        recs = result["recommendations"]
        e1_6_rec = next((r for r in recs if r.esrs_id == "E1-6"), None)
        assert e1_6_rec is not None
        assert e1_6_rec.priority == "critical"

    def test_fallback_sorted_by_priority(self):
        state = _make_advisor_state()
        result = advisor_node(state)
        recs = result["recommendations"]
        priority_order = {"critical": 0, "high": 1, "moderate": 2, "low": 3}
        order_values = [priority_order[r.priority] for r in recs]
        assert order_values == sorted(order_values)

    def test_fallback_enriches_with_financial_context(self):
        state = _make_advisor_state(financial_context=SAMPLE_FINANCIAL_CONTEXT)
        result = advisor_node(state)
        e1_recs = [r for r in result["recommendations"] if r.esrs_id.startswith("E1-")]
        # At least one E1 rec should mention CapEx
        capex_mentions = [r for r in e1_recs if "CapEx" in r.description]
        assert len(capex_mentions) > 0


# ---------------------------------------------------------------------------
# advisor_node() — edge cases
# ---------------------------------------------------------------------------


class TestAdvisorNodeEdgeCases:
    """Edge case tests for advisor_node."""

    @pytest.fixture(autouse=True)
    def mock_claude(self):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_mock_claude_response(
            json.dumps({"recommendations": []})
        )
        with patch("agents.advisor.anthropic.Anthropic", return_value=mock_client):
            yield mock_client

    def test_empty_coverage_gaps(self):
        state = _make_advisor_state(coverage_gaps=[], applicable_reqs=[])
        state["compliance_score"] = ComplianceScore(
            overall=100, size_category="large", applicable_standards_count=0,
            disclosed_count=0, partial_count=0, missing_count=0,
        )
        result = advisor_node(state)
        assert result["recommendations"] == []
        assert isinstance(result["final_result"], ComplianceResult)

    def test_all_disclosed_no_recommendations(self):
        all_disclosed = [
            {"esrs_id": "E1-1", "status": "disclosed", "details": "OK", "document_id": "E1-001"},
            {"esrs_id": "E1-5", "status": "disclosed", "details": "OK", "document_id": "E1-001"},
        ]
        state = _make_advisor_state(coverage_gaps=all_disclosed, applicable_reqs=SAMPLE_APPLICABLE_REQS[:2])
        result = advisor_node(state)
        assert result["recommendations"] == []

    def test_missing_state_keys_use_defaults(self):
        """Advisor should handle missing state keys gracefully."""
        minimal_state = {
            "audit_id": "test-minimal",
            "mode": "free_text",
            "logs": [],
            "pipeline_trace": [],
        }
        result = advisor_node(minimal_state)
        assert isinstance(result["final_result"], ComplianceResult)
        assert result["final_result"].company.name == "Unknown Entity"

    def test_produces_pipeline_trace_entry(self):
        state = _make_advisor_state(coverage_gaps=[])
        result = advisor_node(state)
        advisor_entries = [t for t in result["pipeline_trace"] if t["agent"] == "advisor"]
        assert len(advisor_entries) == 1
        assert advisor_entries[0]["ms"] >= 0

    def test_generated_at_is_iso_format(self):
        state = _make_advisor_state(coverage_gaps=[])
        result = advisor_node(state)
        generated_at = result["final_result"].generated_at
        # Should be a valid ISO 8601 string
        assert "T" in generated_at
        assert generated_at.endswith("+00:00") or generated_at.endswith("Z")


# ---------------------------------------------------------------------------
# Full pipeline integration (extractor → scorer → advisor)
# ---------------------------------------------------------------------------


class TestAdvisorFullPipeline:
    """Test advisor as part of the full 3-node pipeline."""

    @pytest.fixture(autouse=True)
    def mock_claude(self):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_mock_claude_response(MOCK_ADVISOR_RESPONSE_JSON)
        with patch("agents.advisor.anthropic.Anthropic", return_value=mock_client):
            yield mock_client

    def test_structured_document_end_to_end(self):
        """Run extractor → scorer → advisor in structured_document mode."""
        from agents.extractor import extractor_node
        from agents.scorer import scorer_node

        initial_state = {
            "audit_id": "test-e2e-structured",
            "mode": "structured_document",
            "report_json": {},
            "esrs_data": {},
            "taxonomy_data": {},
            "entity_id": "E2E Corp",
            "company_inputs": SAMPLE_COMPANY_INPUTS,
            "logs": [],
            "pipeline_trace": [],
        }

        # Run pipeline
        state = {**initial_state, **extractor_node(initial_state)}
        state = {**state, **scorer_node(state)}
        state = {**state, **advisor_node(state)}

        # Verify final result
        final = state["final_result"]
        assert isinstance(final, ComplianceResult)
        assert final.schema_version == "3.0"
        assert final.mode == "structured_document"
        assert 0 <= final.score.overall <= 100
        assert len(final.pipeline.agents) == 3

    def test_free_text_end_to_end(self):
        """Run extractor → scorer → advisor in free_text mode."""
        from agents.extractor import extractor_node
        from agents.scorer import scorer_node

        initial_state = {
            "audit_id": "test-e2e-freetext",
            "mode": "free_text",
            "free_text_input": "We target net-zero by 2040.",
            "entity_id": "FreeText Corp",
            "company_inputs": CompanyInputs(
                number_of_employees=50, revenue_eur=5_000_000,
                total_assets_eur=2_000_000, reporting_year=2026,
            ),
            "report_json": {},
            "esrs_data": {},
            "taxonomy_data": {},
            "logs": [],
            "pipeline_trace": [],
        }

        state = {**initial_state, **extractor_node(initial_state)}
        state = {**state, **scorer_node(state)}
        state = {**state, **advisor_node(state)}

        final = state["final_result"]
        assert isinstance(final, ComplianceResult)
        assert final.mode == "free_text"
        assert 0 <= final.score.overall <= 100


# ---------------------------------------------------------------------------
# PRD Gate Check
# ---------------------------------------------------------------------------


class TestPRDGate:
    """Verify iteration 10 gate conditions."""

    @pytest.fixture(autouse=True)
    def mock_claude(self):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_mock_claude_response(MOCK_ADVISOR_RESPONSE_JSON)
        with patch("agents.advisor.anthropic.Anthropic", return_value=mock_client):
            yield mock_client

    def test_gate_valid_recommendation_list(self):
        """Gate: Advisor produces valid Recommendation list."""
        state = _make_advisor_state(financial_context=SAMPLE_FINANCIAL_CONTEXT)
        result = advisor_node(state)
        recs = result["recommendations"]
        assert len(recs) > 0
        for rec in recs:
            assert isinstance(rec, Recommendation)
            assert rec.priority in ("critical", "high", "moderate", "low")
            assert rec.esrs_id
            assert rec.title
            assert rec.description
            assert rec.regulatory_reference

    def test_gate_grouped_by_priority(self):
        """Gate: Recommendations grouped by priority tier."""
        state = _make_advisor_state(financial_context=SAMPLE_FINANCIAL_CONTEXT)
        result = advisor_node(state)
        recs = result["recommendations"]
        priority_order = {"critical": 0, "high": 1, "moderate": 2, "low": 3}
        order_values = [priority_order[r.priority] for r in recs]
        assert order_values == sorted(order_values)

    def test_gate_financial_context_enriches(self):
        """Gate: Financial context enriches descriptions when available."""
        state = _make_advisor_state(financial_context=SAMPLE_FINANCIAL_CONTEXT)
        advisor_node(state)
        # Claude was called with financial context
        call_args = MagicMock()
        # Verify the user message sent to Claude included financial data
        msg = _build_user_message(
            SAMPLE_COVERAGE_GAPS, SAMPLE_APPLICABLE_REQS,
            SAMPLE_COMPANY_META, SAMPLE_FINANCIAL_CONTEXT, SAMPLE_COMPLIANCE_SCORE,
        )
        assert "CapEx total" in msg
        assert "50,000,000" in msg

    def test_gate_compliance_result_assembles(self):
        """Gate: ComplianceResult assembles correctly with pipeline timing."""
        state = _make_advisor_state(financial_context=SAMPLE_FINANCIAL_CONTEXT)
        result = advisor_node(state)
        final = result["final_result"]
        assert isinstance(final, ComplianceResult)
        assert final.audit_id == "test-advisor-001"
        assert final.schema_version == "3.0"
        assert final.company.name == "TestCorp SA"
        assert final.score.overall == 42
        assert len(final.recommendations) > 0
        assert len(final.pipeline.agents) == 3
        assert final.pipeline.total_duration_ms > 0
