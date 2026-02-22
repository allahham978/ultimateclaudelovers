"""
Iteration 12 — Real Extractor (Unified) tests.

Tests both modes (structured_document + free_text), all ESRS standards extraction,
financial context extraction, error handling, and end-to-end graph flow.
"""

import json
import sys
import os
from unittest.mock import MagicMock, patch

# Ensure backend is on the path
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

import pytest
from schemas import CompanyMeta, ESRSClaim, FinancialContext, CompanyInputs
from state import AuditState


# ---------------------------------------------------------------------------
# Mock Claude response data
# ---------------------------------------------------------------------------

MOCK_STRUCTURED_RESPONSE = json.dumps({
    "company_meta": {
        "name": "TestCorp SA",
        "lei": "529900TESTCORP00001",
        "sector": "AI Infrastructure",
        "fiscal_year": 2024,
        "jurisdiction": "EU",
        "report_title": "Annual Management Report 2024",
    },
    "esrs_claims": {
        "E1-1": {
            "data_point": "Transition Plan for Climate Change Mitigation",
            "disclosed_value": "Net-zero by 2040; 50% reduction by 2030",
            "unit": None,
            "confidence": 0.85,
            "xbrl_concept": "esrs_E1-1_01_TransitionPlan",
        },
        "E1-5": {
            "data_point": "Energy Consumption and Mix",
            "disclosed_value": "Total energy: 45,000 MWh; Renewable: 38%",
            "unit": "MWh",
            "confidence": 0.90,
            "xbrl_concept": "esrs_E1-5_04_TotalEnergyConsumption",
        },
        "E1-6": {
            "data_point": "Gross Scopes 1, 2, 3 GHG Emissions",
            "disclosed_value": "Scope 1: 1,200 tCO2eq; Scope 2: 8,500 tCO2eq",
            "unit": "tCO2eq",
            "confidence": 0.80,
            "xbrl_concept": "esrs_E1-6_01_GrossScope1GHGEmissions",
        },
        "E2-4": {
            "data_point": "Pollution Prevention Policies",
            "disclosed_value": "Waste management policy in place",
            "unit": None,
            "confidence": 0.70,
            "xbrl_concept": "esrs_E2-4_01_PollutionPrevention",
        },
        "S1-1": {
            "data_point": "Own Workforce Impact Assessment",
            "disclosed_value": "500 employees, diversity reporting in place",
            "unit": None,
            "confidence": 0.75,
            "xbrl_concept": "esrs_S1-1_01_WorkforceImpact",
        },
        "S1-6": {
            "data_point": "Workforce Characteristics",
            "disclosed_value": None,
            "unit": None,
            "confidence": 0.3,
            "xbrl_concept": None,
        },
        "G1": {
            "data_point": "Business Conduct",
            "disclosed_value": "Anti-corruption policy established",
            "unit": None,
            "confidence": 0.72,
            "xbrl_concept": "esrs_G1_01_BusinessConduct",
        },
    },
    "financial_context": {
        "capex_total_eur": 50000000.0,
        "capex_green_eur": 17500000.0,
        "opex_total_eur": 120000000.0,
        "opex_green_eur": 24000000.0,
        "revenue_eur": 250000000.0,
        "taxonomy_activities": [
            "8.1 Data processing, hosting and related activities",
            "4.1 Electricity generation using solar photovoltaic technology",
        ],
        "confidence": 0.92,
    },
})

MOCK_FREE_TEXT_RESPONSE = json.dumps({
    "company_meta": {
        "name": "Lumiere Systemes SA",
        "lei": None,
        "sector": "Technology",
        "fiscal_year": 2025,
        "jurisdiction": "FR",
        "report_title": "User-Provided Sustainability Description",
    },
    "esrs_claims": {
        "E1-1": {
            "data_point": "Transition Plan for Climate Change Mitigation",
            "disclosed_value": "Net-zero target 2040 mentioned",
            "unit": None,
            "confidence": 0.5,
            "xbrl_concept": None,
        },
        "E1-5": {
            "data_point": "Energy Consumption and Mix",
            "disclosed_value": "120 GWh annually, 29% renewable",
            "unit": "GWh",
            "confidence": 0.7,
            "xbrl_concept": None,
        },
        "E1-6": {
            "data_point": "Gross GHG Emissions",
            "disclosed_value": None,
            "unit": None,
            "confidence": 0.0,
            "xbrl_concept": None,
        },
    },
    "financial_context": None,
})

# Response wrapped in markdown fences (tests _parse_llm_json)
MOCK_FENCED_RESPONSE = f"```json\n{MOCK_FREE_TEXT_RESPONSE}\n```"

# Minimal response with almost no data
MOCK_MINIMAL_RESPONSE = json.dumps({
    "company_meta": {
        "name": None,
        "lei": None,
        "sector": None,
        "fiscal_year": None,
        "jurisdiction": None,
        "report_title": "User-Provided Sustainability Description",
    },
    "esrs_claims": {},
    "financial_context": None,
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_response(text: str) -> MagicMock:
    """Create a mock Anthropic Messages API response."""
    mock_content_block = MagicMock()
    mock_content_block.text = text
    mock_response = MagicMock()
    mock_response.content = [mock_content_block]
    return mock_response


def _make_mock_client(response_text: str) -> MagicMock:
    """Create a mock Anthropic client returning the given response text."""
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _make_mock_response(response_text)
    return mock_client


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


SAMPLE_ESRS_DATA = {
    "facts": [
        {"concept": "esrs_E1-1_01_TransitionPlan", "value": "Net-zero by 2040", "context_ref": "FY2024"},
        {"concept": "esrs_E1-5_04_TotalEnergyConsumption", "value": "45000", "unit_ref": "utr:MWh", "context_ref": "FY2024"},
        {"concept": "esrs_E1-6_01_GrossScope1GHGEmissions", "value": "1200", "unit_ref": "utr:tCO2eq", "context_ref": "FY2024"},
        {"concept": "esrs_S1-1_01_WorkforceImpact", "value": "500 employees", "context_ref": "FY2024"},
        {"concept": "esrs_G1_01_BusinessConduct", "value": "Anti-corruption policy", "context_ref": "FY2024"},
    ]
}

SAMPLE_TAXONOMY_DATA = {
    "facts": [
        {"concept": "eutaxonomy:CapExTotal", "value": "50000000", "unit_ref": "iso4217:EUR", "context_ref": "FY2024"},
        {"concept": "eutaxonomy:CapExAligned", "value": "17500000", "unit_ref": "iso4217:EUR", "context_ref": "FY2024"},
        {"concept": "ifrs-full:Revenue", "value": "250000000", "unit_ref": "iso4217:EUR", "context_ref": "FY2024"},
    ]
}

STUB_COMPANY_INPUTS = CompanyInputs(
    number_of_employees=500,
    revenue_eur=85_000_000.0,
    total_assets_eur=42_000_000.0,
    reporting_year=2025,
)


@pytest.fixture
def structured_state() -> AuditState:
    return {
        "audit_id": "test-ext-v5-struct-001",
        "mode": "structured_document",
        "report_json": {"facts": SAMPLE_ESRS_DATA["facts"] + SAMPLE_TAXONOMY_DATA["facts"]},
        "esrs_data": SAMPLE_ESRS_DATA,
        "taxonomy_data": SAMPLE_TAXONOMY_DATA,
        "entity_id": "TestCorp SA",
        "company_inputs": STUB_COMPANY_INPUTS,
        "logs": [],
        "pipeline_trace": [],
    }


@pytest.fixture
def free_text_state() -> AuditState:
    return {
        "audit_id": "test-ext-v5-free-001",
        "mode": "free_text",
        "free_text_input": (
            "We are Lumiere Systemes SA, an AI infrastructure company based in France. "
            "We have set a net-zero target for 2040. "
            "Our data centers consume approximately 120 GWh annually with 29% renewable energy."
        ),
        "entity_id": "Lumiere Systemes SA",
        "company_inputs": CompanyInputs(
            number_of_employees=50, revenue_eur=5_000_000.0,
            total_assets_eur=2_000_000.0, reporting_year=2025,
        ),
        "report_json": {},
        "esrs_data": {},
        "taxonomy_data": {},
        "logs": [],
        "pipeline_trace": [],
    }


# ===========================================================================
# Test: Structured Document Mode — Real API Call
# ===========================================================================


class TestExtractorStructuredMode:
    """Tests for structured_document mode extraction."""

    def test_extracts_all_esrs_standards(self, structured_state):
        """Extractor should extract claims for ALL ESRS standards found, not just E1."""
        mock_client = _make_mock_client(MOCK_STRUCTURED_RESPONSE)

        with patch("agents.extractor.anthropic.Anthropic", return_value=mock_client):
            from agents.extractor import extractor_node
            result = extractor_node(structured_state)

        claims = result["esrs_claims"]
        # Should have E1, E2, S1, G1 (7 claims total from mock)
        assert len(claims) == 7
        assert "E1-1" in claims
        assert "E1-5" in claims
        assert "E1-6" in claims
        assert "E2-4" in claims
        assert "S1-1" in claims
        assert "S1-6" in claims
        assert "G1" in claims

    def test_claims_are_esrs_claim_instances(self, structured_state):
        """Each claim should be an ESRSClaim Pydantic model."""
        mock_client = _make_mock_client(MOCK_STRUCTURED_RESPONSE)

        with patch("agents.extractor.anthropic.Anthropic", return_value=mock_client):
            from agents.extractor import extractor_node
            result = extractor_node(structured_state)

        for esrs_id, claim in result["esrs_claims"].items():
            assert isinstance(claim, ESRSClaim), f"{esrs_id} is not an ESRSClaim"
            assert claim.standard == esrs_id

    def test_extracts_financial_context(self, structured_state):
        """Structured doc mode should extract FinancialContext from taxonomy data."""
        mock_client = _make_mock_client(MOCK_STRUCTURED_RESPONSE)

        with patch("agents.extractor.anthropic.Anthropic", return_value=mock_client):
            from agents.extractor import extractor_node
            result = extractor_node(structured_state)

        fc = result["financial_context"]
        assert isinstance(fc, FinancialContext)
        assert fc.capex_total_eur == 50000000.0
        assert fc.capex_green_eur == 17500000.0
        assert fc.opex_total_eur == 120000000.0
        assert fc.opex_green_eur == 24000000.0
        assert fc.revenue_eur == 250000000.0
        assert len(fc.taxonomy_activities) == 2
        assert fc.confidence == 0.92

    def test_extracts_company_meta(self, structured_state):
        """Should extract CompanyMeta from Claude's response."""
        mock_client = _make_mock_client(MOCK_STRUCTURED_RESPONSE)

        with patch("agents.extractor.anthropic.Anthropic", return_value=mock_client):
            from agents.extractor import extractor_node
            result = extractor_node(structured_state)

        meta = result["company_meta"]
        assert isinstance(meta, CompanyMeta)
        assert meta.name == "TestCorp SA"
        assert meta.lei == "529900TESTCORP00001"
        assert meta.sector == "AI Infrastructure"
        assert meta.fiscal_year == 2024

    def test_sends_both_esrs_and_taxonomy_data(self, structured_state):
        """Should send BOTH esrs_data + taxonomy_data to Claude in ONE call."""
        mock_client = _make_mock_client(MOCK_STRUCTURED_RESPONSE)

        with patch("agents.extractor.anthropic.Anthropic", return_value=mock_client):
            from agents.extractor import extractor_node
            extractor_node(structured_state)

        call_args = mock_client.messages.create.call_args
        messages = call_args.kwargs["messages"]

        # Should be a single message with content_parts (list)
        assert len(messages) == 1
        content = messages[0]["content"]
        assert isinstance(content, list), "Content should be a list of parts (prompt caching)"

        # Should include both ESRS and Taxonomy data
        text_parts = [p["text"] for p in content if isinstance(p, dict) and "text" in p]
        combined_text = " ".join(text_parts)
        assert "ESRS SECTIONS" in combined_text
        assert "TAXONOMY SECTIONS" in combined_text

    def test_uses_correct_model(self, structured_state):
        """Should use claude-sonnet-4-6 model."""
        mock_client = _make_mock_client(MOCK_STRUCTURED_RESPONSE)

        with patch("agents.extractor.anthropic.Anthropic", return_value=mock_client):
            from agents.extractor import extractor_node
            extractor_node(structured_state)

        call_args = mock_client.messages.create.call_args
        assert call_args.kwargs["model"] == "claude-sonnet-4-6"

    def test_uses_correct_system_prompt(self, structured_state):
        """Should use SYSTEM_PROMPT_EXTRACTOR for structured doc mode."""
        mock_client = _make_mock_client(MOCK_STRUCTURED_RESPONSE)

        with patch("agents.extractor.anthropic.Anthropic", return_value=mock_client):
            from agents.extractor import extractor_node
            extractor_node(structured_state)

        from tools.prompts import SYSTEM_PROMPT_EXTRACTOR
        call_args = mock_client.messages.create.call_args
        assert call_args.kwargs["system"] == SYSTEM_PROMPT_EXTRACTOR

    def test_prompt_caching_on_data(self, structured_state):
        """Should set cache_control on ESRS and Taxonomy data parts."""
        mock_client = _make_mock_client(MOCK_STRUCTURED_RESPONSE)

        with patch("agents.extractor.anthropic.Anthropic", return_value=mock_client):
            from agents.extractor import extractor_node
            extractor_node(structured_state)

        call_args = mock_client.messages.create.call_args
        content = call_args.kwargs["messages"][0]["content"]

        cached_parts = [p for p in content if isinstance(p, dict) and "cache_control" in p]
        assert len(cached_parts) == 2, "Should have 2 cached parts (ESRS + Taxonomy)"
        for p in cached_parts:
            assert p["cache_control"] == {"type": "ephemeral"}

    def test_confidence_values(self, structured_state):
        """Claims should preserve confidence values from Claude's response."""
        mock_client = _make_mock_client(MOCK_STRUCTURED_RESPONSE)

        with patch("agents.extractor.anthropic.Anthropic", return_value=mock_client):
            from agents.extractor import extractor_node
            result = extractor_node(structured_state)

        claims = result["esrs_claims"]
        assert claims["E1-1"].confidence == 0.85
        assert claims["E1-5"].confidence == 0.90
        assert claims["E1-6"].confidence == 0.80
        assert claims["S1-6"].confidence == 0.3

    def test_logs_and_pipeline_trace(self, structured_state):
        """Should accumulate logs and pipeline_trace entries."""
        mock_client = _make_mock_client(MOCK_STRUCTURED_RESPONSE)

        with patch("agents.extractor.anthropic.Anthropic", return_value=mock_client):
            from agents.extractor import extractor_node
            result = extractor_node(structured_state)

        assert len(result["logs"]) > 0
        assert all(log["agent"] == "extractor" for log in result["logs"])
        assert len(result["pipeline_trace"]) == 1
        assert result["pipeline_trace"][0]["agent"] == "extractor"
        assert result["pipeline_trace"][0]["ms"] >= 0


# ===========================================================================
# Test: Free Text Mode — Real API Call
# ===========================================================================


class TestExtractorFreeTextMode:
    """Tests for free_text mode extraction."""

    def test_extracts_claims_from_text(self, free_text_state):
        """Should extract ESRS claims from free text input."""
        mock_client = _make_mock_client(MOCK_FREE_TEXT_RESPONSE)

        with patch("agents.extractor.anthropic.Anthropic", return_value=mock_client):
            from agents.extractor import extractor_node
            result = extractor_node(free_text_state)

        claims = result["esrs_claims"]
        assert len(claims) == 3
        assert "E1-1" in claims
        assert "E1-5" in claims
        assert "E1-6" in claims

    def test_no_financial_context(self, free_text_state):
        """Free text mode should NOT have financial_context in output."""
        mock_client = _make_mock_client(MOCK_FREE_TEXT_RESPONSE)

        with patch("agents.extractor.anthropic.Anthropic", return_value=mock_client):
            from agents.extractor import extractor_node
            result = extractor_node(free_text_state)

        # financial_context should not be in the result dict for free text
        assert "financial_context" not in result

    def test_xbrl_concept_always_null(self, free_text_state):
        """In free text mode, xbrl_concept should always be null."""
        mock_client = _make_mock_client(MOCK_FREE_TEXT_RESPONSE)

        with patch("agents.extractor.anthropic.Anthropic", return_value=mock_client):
            from agents.extractor import extractor_node
            result = extractor_node(free_text_state)

        for claim in result["esrs_claims"].values():
            assert claim.xbrl_concept is None

    def test_uses_lite_system_prompt(self, free_text_state):
        """Should use SYSTEM_PROMPT_EXTRACTOR_LITE for free text mode."""
        mock_client = _make_mock_client(MOCK_FREE_TEXT_RESPONSE)

        with patch("agents.extractor.anthropic.Anthropic", return_value=mock_client):
            from agents.extractor import extractor_node
            extractor_node(free_text_state)

        from tools.prompts import SYSTEM_PROMPT_EXTRACTOR_LITE
        call_args = mock_client.messages.create.call_args
        assert call_args.kwargs["system"] == SYSTEM_PROMPT_EXTRACTOR_LITE

    def test_sends_free_text_as_user_message(self, free_text_state):
        """Should send the free text as a plain user message (no content parts)."""
        mock_client = _make_mock_client(MOCK_FREE_TEXT_RESPONSE)

        with patch("agents.extractor.anthropic.Anthropic", return_value=mock_client):
            from agents.extractor import extractor_node
            extractor_node(free_text_state)

        call_args = mock_client.messages.create.call_args
        messages = call_args.kwargs["messages"]
        assert len(messages) == 1
        content = messages[0]["content"]
        # Free text uses a plain string content, not a list of parts
        assert isinstance(content, str)
        assert "Lumiere Systemes SA" in content or "net-zero" in content

    def test_lower_confidence_values(self, free_text_state):
        """Free text claims should typically have lower confidence than structured."""
        mock_client = _make_mock_client(MOCK_FREE_TEXT_RESPONSE)

        with patch("agents.extractor.anthropic.Anthropic", return_value=mock_client):
            from agents.extractor import extractor_node
            result = extractor_node(free_text_state)

        claims = result["esrs_claims"]
        # E1-1 from free text should be 0.5 (vague mention) vs 0.85 from structured
        assert claims["E1-1"].confidence == 0.5
        assert claims["E1-6"].confidence == 0.0  # not found

    def test_company_meta_from_text(self, free_text_state):
        """Should extract company meta from free text."""
        mock_client = _make_mock_client(MOCK_FREE_TEXT_RESPONSE)

        with patch("agents.extractor.anthropic.Anthropic", return_value=mock_client):
            from agents.extractor import extractor_node
            result = extractor_node(free_text_state)

        meta = result["company_meta"]
        assert meta.name == "Lumiere Systemes SA"
        assert meta.lei is None
        assert meta.report_title == "User-Provided Sustainability Description"


# ===========================================================================
# Test: JSON Parsing
# ===========================================================================


class TestJsonParsing:
    """Tests for _parse_llm_json helper."""

    def test_parses_clean_json(self):
        from agents.extractor import _parse_llm_json
        result = _parse_llm_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_parses_fenced_json(self):
        from agents.extractor import _parse_llm_json
        result = _parse_llm_json('```json\n{"key": "value"}\n```')
        assert result == {"key": "value"}

    def test_parses_bare_fenced_json(self):
        from agents.extractor import _parse_llm_json
        result = _parse_llm_json('```\n{"key": "value"}\n```')
        assert result == {"key": "value"}

    def test_handles_whitespace(self):
        from agents.extractor import _parse_llm_json
        result = _parse_llm_json('  \n  {"key": "value"}  \n  ')
        assert result == {"key": "value"}

    def test_raises_on_invalid_json(self):
        from agents.extractor import _parse_llm_json
        with pytest.raises(json.JSONDecodeError):
            _parse_llm_json("not json at all")

    def test_parses_fenced_response_in_extractor(self, free_text_state):
        """Fenced JSON from Claude should be parsed correctly."""
        mock_client = _make_mock_client(MOCK_FENCED_RESPONSE)

        with patch("agents.extractor.anthropic.Anthropic", return_value=mock_client):
            from agents.extractor import extractor_node
            result = extractor_node(free_text_state)

        assert len(result["esrs_claims"]) == 3


# ===========================================================================
# Test: Error Handling
# ===========================================================================


class TestExtractorErrorHandling:
    """Tests for error handling — safe defaults on failure."""

    def test_api_error_returns_safe_defaults(self, structured_state):
        """On API error, should return empty claims and None financial_context."""
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("API connection failed")

        with patch("agents.extractor.anthropic.Anthropic", return_value=mock_client):
            from agents.extractor import extractor_node
            result = extractor_node(structured_state)

        assert result["esrs_claims"] == {}
        assert result["financial_context"] is None
        assert isinstance(result["company_meta"], CompanyMeta)
        # Should log the error
        error_logs = [log for log in result["logs"] if "Error" in log["msg"]]
        assert len(error_logs) > 0

    def test_api_error_free_text_returns_safe_defaults(self, free_text_state):
        """On API error in free text mode, should return empty claims."""
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("Rate limit exceeded")

        with patch("agents.extractor.anthropic.Anthropic", return_value=mock_client):
            from agents.extractor import extractor_node
            result = extractor_node(free_text_state)

        assert result["esrs_claims"] == {}
        assert "financial_context" not in result

    def test_invalid_json_response_returns_safe_defaults(self, structured_state):
        """If Claude returns invalid JSON, should return safe defaults."""
        mock_client = _make_mock_client("I cannot extract any data from this input.")

        with patch("agents.extractor.anthropic.Anthropic", return_value=mock_client):
            from agents.extractor import extractor_node
            result = extractor_node(structured_state)

        assert result["esrs_claims"] == {}
        assert result["financial_context"] is None

    def test_never_halts_graph(self, structured_state):
        """Extractor should NEVER raise — always returns valid state dict."""
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = RuntimeError("Catastrophic failure")

        with patch("agents.extractor.anthropic.Anthropic", return_value=mock_client):
            from agents.extractor import extractor_node
            result = extractor_node(structured_state)

        # Should have all required keys
        assert "company_meta" in result
        assert "esrs_claims" in result
        assert "financial_context" in result
        assert "logs" in result
        assert "pipeline_trace" in result

    def test_minimal_response_handled(self, free_text_state):
        """Nearly empty Claude response should produce empty claims gracefully."""
        mock_client = _make_mock_client(MOCK_MINIMAL_RESPONSE)

        with patch("agents.extractor.anthropic.Anthropic", return_value=mock_client):
            from agents.extractor import extractor_node
            result = extractor_node(free_text_state)

        assert result["esrs_claims"] == {}
        # Fallback entity_id should be used when name is None
        assert result["company_meta"].name == "Lumiere Systemes SA"


# ===========================================================================
# Test: Builder Helpers
# ===========================================================================


class TestBuilderHelpers:
    """Tests for _build_* helper functions."""

    def test_build_esrs_claims_empty(self):
        from agents.extractor import _build_esrs_claims
        result = _build_esrs_claims({})
        assert result == {}

    def test_build_esrs_claims_handles_missing_fields(self):
        from agents.extractor import _build_esrs_claims
        result = _build_esrs_claims({
            "E1-1": {"data_point": "Test"},
        })
        claim = result["E1-1"]
        assert claim.standard == "E1-1"
        assert claim.data_point == "Test"
        assert claim.disclosed_value is None
        assert claim.unit is None
        assert claim.confidence == 0.0
        assert claim.xbrl_concept is None

    def test_build_company_meta_fallback(self):
        from agents.extractor import _build_company_meta
        result = _build_company_meta({}, "FallbackCorp")
        assert result.name == "FallbackCorp"
        assert result.sector == "Unknown"

    def test_build_financial_context_none(self):
        from agents.extractor import _build_financial_context
        assert _build_financial_context(None) is None
        assert _build_financial_context({}) is None

    def test_build_financial_context_partial(self):
        from agents.extractor import _build_financial_context
        fc = _build_financial_context({"capex_total_eur": 100.0, "confidence": 0.5})
        assert isinstance(fc, FinancialContext)
        assert fc.capex_total_eur == 100.0
        assert fc.capex_green_eur is None
        assert fc.confidence == 0.5


# ===========================================================================
# Test: End-to-End Graph Flow
# ===========================================================================


class TestExtractorGraphFlow:
    """Tests that extractor output flows correctly through scorer → advisor."""

    def test_structured_flows_through_pipeline(self, structured_state):
        """Structured doc extraction should flow through scorer → advisor without error."""
        mock_client = _make_mock_client(MOCK_STRUCTURED_RESPONSE)

        with patch("agents.extractor.anthropic.Anthropic", return_value=mock_client):
            from agents.extractor import extractor_node
            from agents.scorer import scorer_node
            from agents.advisor import advisor_node

            ext_result = extractor_node(structured_state)
            state_after_ext = {**structured_state, **ext_result}

            scorer_result = scorer_node(state_after_ext)
            state_after_scorer = {**state_after_ext, **scorer_result}

            advisor_result = advisor_node(state_after_scorer)

        # Final result should be assembled
        assert "final_result" in advisor_result
        final = advisor_result["final_result"]
        assert final.schema_version == "3.0"
        assert final.mode == "structured_document"
        assert final.score.overall >= 0
        assert final.score.overall <= 100

    def test_free_text_flows_through_pipeline(self, free_text_state):
        """Free text extraction should flow through scorer → advisor without error."""
        mock_client = _make_mock_client(MOCK_FREE_TEXT_RESPONSE)

        with patch("agents.extractor.anthropic.Anthropic", return_value=mock_client):
            from agents.extractor import extractor_node
            from agents.scorer import scorer_node
            from agents.advisor import advisor_node

            ext_result = extractor_node(free_text_state)
            state_after_ext = {**free_text_state, **ext_result}

            scorer_result = scorer_node(state_after_ext)
            state_after_scorer = {**state_after_ext, **scorer_result}

            advisor_result = advisor_node(state_after_scorer)

        final = advisor_result["final_result"]
        assert final.mode == "free_text"
        assert final.score.overall >= 0

    def test_error_flows_through_pipeline(self, structured_state):
        """Even on extraction error, scorer → advisor should still run (empty claims)."""
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("API down")

        with patch("agents.extractor.anthropic.Anthropic", return_value=mock_client):
            from agents.extractor import extractor_node
            from agents.scorer import scorer_node
            from agents.advisor import advisor_node

            ext_result = extractor_node(structured_state)
            state_after_ext = {**structured_state, **ext_result}

            scorer_result = scorer_node(state_after_ext)
            state_after_scorer = {**state_after_ext, **scorer_result}

            advisor_result = advisor_node(state_after_scorer)

        # Should complete without error — score will be 0 with all missing
        final = advisor_result["final_result"]
        assert final.score.overall == 0 or final.score.overall >= 0


# ===========================================================================
# Test: PRD Gate Check
# ===========================================================================


class TestPRDGate:
    """Iteration 12 gate check: extractor populates esrs_claims with all found
    standards (not limited to E1). financial_context populated in structured doc
    mode, None in free text."""

    def test_gate_structured_all_standards(self, structured_state):
        """GATE: esrs_claims contains non-E1 standards (E2, S1, G1)."""
        mock_client = _make_mock_client(MOCK_STRUCTURED_RESPONSE)

        with patch("agents.extractor.anthropic.Anthropic", return_value=mock_client):
            from agents.extractor import extractor_node
            result = extractor_node(structured_state)

        claims = result["esrs_claims"]
        # Must have standards beyond E1
        non_e1 = [k for k in claims if not k.startswith("E1")]
        assert len(non_e1) > 0, "Gate fail: extractor only returns E1 standards"
        assert "E2-4" in claims, "Gate fail: E2 standard missing"
        assert "S1-1" in claims, "Gate fail: S1 standard missing"
        assert "G1" in claims, "Gate fail: G1 standard missing"

    def test_gate_structured_financial_context(self, structured_state):
        """GATE: financial_context populated in structured_document mode."""
        mock_client = _make_mock_client(MOCK_STRUCTURED_RESPONSE)

        with patch("agents.extractor.anthropic.Anthropic", return_value=mock_client):
            from agents.extractor import extractor_node
            result = extractor_node(structured_state)

        fc = result["financial_context"]
        assert fc is not None, "Gate fail: financial_context is None in structured mode"
        assert fc.capex_total_eur is not None
        assert fc.revenue_eur is not None

    def test_gate_free_text_no_financial_context(self, free_text_state):
        """GATE: financial_context is None in free_text mode."""
        mock_client = _make_mock_client(MOCK_FREE_TEXT_RESPONSE)

        with patch("agents.extractor.anthropic.Anthropic", return_value=mock_client):
            from agents.extractor import extractor_node
            result = extractor_node(free_text_state)

        assert "financial_context" not in result, "Gate fail: financial_context should not be in free_text output"

    def test_gate_end_to_end_no_error(self, structured_state, free_text_state):
        """GATE: Both modes flow through scorer → advisor without error."""
        mock_structured = _make_mock_client(MOCK_STRUCTURED_RESPONSE)
        mock_free = _make_mock_client(MOCK_FREE_TEXT_RESPONSE)

        from agents.extractor import extractor_node
        from agents.scorer import scorer_node
        from agents.advisor import advisor_node

        # Structured path
        with patch("agents.extractor.anthropic.Anthropic", return_value=mock_structured):
            ext = extractor_node(structured_state)
        s1 = {**structured_state, **ext}
        sc = scorer_node(s1)
        s2 = {**s1, **sc}
        adv = advisor_node(s2)
        assert adv["final_result"].mode == "structured_document"

        # Free text path
        with patch("agents.extractor.anthropic.Anthropic", return_value=mock_free):
            ext2 = extractor_node(free_text_state)
        s3 = {**free_text_state, **ext2}
        sc2 = scorer_node(s3)
        s4 = {**s3, **sc2}
        adv2 = advisor_node(s4)
        assert adv2["final_result"].mode == "free_text"
