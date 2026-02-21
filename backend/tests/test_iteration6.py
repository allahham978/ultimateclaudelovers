"""
Iteration 6 tests — Real Fetcher Node with mocked Claude API.

Tests Claude API call construction, JSON response parsing, TaxonomyFinancials
extraction, error handling / fallback, state management, and the PRD gate.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from agents.fetcher import (
    MODEL,
    MAX_TOKENS,
    _build_taxonomy_financials,
    _parse_llm_json,
    _safe_defaults,
    fetcher_node,
)
from schemas import RegistrySource, TaxonomyFinancials
from tools.prompts import SYSTEM_PROMPT_FETCHER
from tests.conftest import MOCK_FETCHER_RESPONSE_JSON, _make_mock_claude_response


# ═══════════════════════════════════════════════════════════════════════════
# A. Claude API Call Construction
# ═══════════════════════════════════════════════════════════════════════════

class TestClaudeAPICall:
    """Verify that the fetcher builds and sends the correct Claude API request."""

    def test_calls_correct_model(self, minimal_state, mock_anthropic_client):
        fetcher_node(minimal_state)
        call_kwargs = mock_anthropic_client.messages.create.call_args
        assert call_kwargs.kwargs["model"] == "claude-sonnet-4-6"

    def test_uses_fetcher_system_prompt(self, minimal_state, mock_anthropic_client):
        fetcher_node(minimal_state)
        call_kwargs = mock_anthropic_client.messages.create.call_args
        assert call_kwargs.kwargs["system"] == SYSTEM_PROMPT_FETCHER

    def test_sends_taxonomy_data_in_message(self, minimal_state, mock_anthropic_client):
        fetcher_node(minimal_state)
        call_kwargs = mock_anthropic_client.messages.create.call_args
        messages = call_kwargs.kwargs["messages"]
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        # The taxonomy_data JSON should appear in one of the content blocks
        content_blocks = messages[0]["content"]
        taxonomy_json_str = json.dumps(minimal_state["taxonomy_data"], indent=2)
        found = any(block.get("text") == taxonomy_json_str for block in content_blocks)
        assert found, "taxonomy_data JSON not found in message content blocks"

    def test_prompt_caching_enabled(self, minimal_state, mock_anthropic_client):
        fetcher_node(minimal_state)
        call_kwargs = mock_anthropic_client.messages.create.call_args
        messages = call_kwargs.kwargs["messages"]
        content_blocks = messages[0]["content"]
        cache_blocks = [b for b in content_blocks if b.get("cache_control") == {"type": "ephemeral"}]
        assert len(cache_blocks) == 1, "Exactly one content block should have cache_control: ephemeral"

    def test_max_tokens_set(self, minimal_state, mock_anthropic_client):
        fetcher_node(minimal_state)
        call_kwargs = mock_anthropic_client.messages.create.call_args
        assert call_kwargs.kwargs["max_tokens"] == MAX_TOKENS

    def test_api_called_exactly_once(self, minimal_state, mock_anthropic_client):
        fetcher_node(minimal_state)
        assert mock_anthropic_client.messages.create.call_count == 1


# ═══════════════════════════════════════════════════════════════════════════
# B. JSON Response Parsing (_parse_llm_json)
# ═══════════════════════════════════════════════════════════════════════════

class TestParseLLMJson:
    """Verify robust JSON parsing from Claude responses."""

    def test_parses_clean_json(self):
        raw = '{"taxonomy_financials": {"capex_total_eur": 100}}'
        result = _parse_llm_json(raw)
        assert result["taxonomy_financials"]["capex_total_eur"] == 100

    def test_parses_json_in_markdown_fences(self):
        raw = '```json\n{"taxonomy_financials": {"capex_total_eur": 200}}\n```'
        result = _parse_llm_json(raw)
        assert result["taxonomy_financials"]["capex_total_eur"] == 200

    def test_parses_json_in_bare_fences(self):
        raw = '```\n{"key": "value"}\n```'
        result = _parse_llm_json(raw)
        assert result["key"] == "value"

    def test_parses_json_with_leading_whitespace(self):
        raw = '  \n  {"key": "value"}  \n  '
        result = _parse_llm_json(raw)
        assert result["key"] == "value"

    def test_raises_on_invalid_json(self):
        with pytest.raises(json.JSONDecodeError):
            _parse_llm_json("not json at all")

    def test_parses_nested_financial_structures(self):
        data = {"taxonomy_financials": {"capex_total_eur": 50000000, "taxonomy_activities": ["8.1 Data processing"]}}
        raw = json.dumps(data)
        result = _parse_llm_json(raw)
        assert result["taxonomy_financials"]["capex_total_eur"] == 50000000
        assert len(result["taxonomy_financials"]["taxonomy_activities"]) == 1


# ═══════════════════════════════════════════════════════════════════════════
# C. TaxonomyFinancials Construction (_build_taxonomy_financials)
# ═══════════════════════════════════════════════════════════════════════════

class TestBuildTaxonomyFinancials:
    """Verify TaxonomyFinancials construction from Claude's parsed response."""

    def test_extracts_all_fields(self):
        raw = {
            "capex_total_eur": 50000000.0,
            "capex_green_eur": 17500000.0,
            "opex_total_eur": 120000000.0,
            "opex_green_eur": 24000000.0,
            "revenue_eur": 250000000.0,
            "fiscal_year": "2024",
            "taxonomy_activities": ["8.1 Data processing"],
            "source_document": "Annual Management Report — Taxonomy Section",
            "confidence": 0.92,
        }
        fin = _build_taxonomy_financials(raw)
        assert fin.capex_total_eur == 50000000.0
        assert fin.capex_green_eur == 17500000.0
        assert fin.opex_total_eur == 120000000.0
        assert fin.opex_green_eur == 24000000.0
        assert fin.revenue_eur == 250000000.0
        assert fin.fiscal_year == "2024"
        assert fin.taxonomy_activities == ["8.1 Data processing"]
        assert fin.confidence == 0.92

    def test_handles_null_optional_fields(self):
        raw = {
            "capex_total_eur": None,
            "capex_green_eur": None,
            "opex_total_eur": None,
            "opex_green_eur": None,
            "revenue_eur": None,
            "fiscal_year": "2024",
            "taxonomy_activities": [],
            "confidence": 0.0,
        }
        fin = _build_taxonomy_financials(raw)
        assert fin.capex_total_eur is None
        assert fin.capex_green_eur is None
        assert fin.revenue_eur is None
        assert fin.confidence == 0.0

    def test_handles_missing_fields_gracefully(self):
        raw = {"fiscal_year": "2024", "confidence": 0.5}
        fin = _build_taxonomy_financials(raw)
        assert fin.capex_total_eur is None
        assert fin.capex_green_eur is None
        assert fin.taxonomy_activities == []
        assert fin.source_document == "Annual Management Report — Taxonomy Section"

    def test_fiscal_year_coerced_to_string(self):
        raw = {"fiscal_year": 2024, "confidence": 0.9}
        fin = _build_taxonomy_financials(raw)
        assert isinstance(fin.fiscal_year, str)
        assert fin.fiscal_year == "2024"

    def test_handles_empty_dict(self):
        fin = _build_taxonomy_financials({})
        assert fin.capex_total_eur is None
        assert fin.fiscal_year == "Unknown"
        assert fin.confidence == 0.0

    def test_multiple_taxonomy_activities(self):
        raw = {
            "fiscal_year": "2024",
            "taxonomy_activities": [
                "8.1 Data processing, hosting and related activities",
                "4.1 Electricity generation using solar photovoltaic technology",
                "7.7 Acquisition and ownership of buildings",
            ],
            "confidence": 0.85,
        }
        fin = _build_taxonomy_financials(raw)
        assert len(fin.taxonomy_activities) == 3


# ═══════════════════════════════════════════════════════════════════════════
# D. Safe Defaults
# ═══════════════════════════════════════════════════════════════════════════

class TestSafeDefaults:
    """Verify _safe_defaults returns properly shaped fallback data."""

    def test_all_financial_fields_are_none(self):
        fin = _safe_defaults()
        assert fin.capex_total_eur is None
        assert fin.capex_green_eur is None
        assert fin.opex_total_eur is None
        assert fin.opex_green_eur is None
        assert fin.revenue_eur is None

    def test_confidence_is_zero(self):
        fin = _safe_defaults()
        assert fin.confidence == 0.0

    def test_fiscal_year_is_unknown(self):
        fin = _safe_defaults()
        assert fin.fiscal_year == "Unknown"

    def test_taxonomy_activities_is_empty(self):
        fin = _safe_defaults()
        assert fin.taxonomy_activities == []

    def test_source_document_is_set(self):
        fin = _safe_defaults()
        assert fin.source_document == "Annual Management Report — Taxonomy Section"

    def test_returns_valid_pydantic_model(self):
        fin = _safe_defaults()
        assert isinstance(fin, TaxonomyFinancials)
        # Should serialize without errors
        d = fin.model_dump()
        assert "capex_total_eur" in d


# ═══════════════════════════════════════════════════════════════════════════
# E. Error Handling / Fallback
# ═══════════════════════════════════════════════════════════════════════════

class TestErrorHandling:
    """Verify graceful degradation — never halts the graph."""

    def test_api_error_returns_safe_defaults(self, minimal_state, mock_anthropic_client):
        mock_anthropic_client.messages.create.side_effect = Exception("API connection failed")
        result = fetcher_node(minimal_state)
        fin = result["taxonomy_financials"]
        assert fin.capex_total_eur is None
        assert fin.capex_green_eur is None
        assert fin.confidence == 0.0

    def test_api_error_logs_error(self, minimal_state, mock_anthropic_client):
        mock_anthropic_client.messages.create.side_effect = Exception("API connection failed")
        result = fetcher_node(minimal_state)
        error_logs = [l for l in result["logs"] if "Error" in l.get("msg", "")]
        assert len(error_logs) >= 1
        assert "API connection failed" in error_logs[0]["msg"]

    def test_malformed_json_returns_safe_defaults(self, minimal_state, mock_anthropic_client):
        mock_anthropic_client.messages.create.return_value = _make_mock_claude_response("not valid json {{{")
        result = fetcher_node(minimal_state)
        fin = result["taxonomy_financials"]
        assert fin.capex_total_eur is None
        assert fin.confidence == 0.0

    def test_missing_taxonomy_financials_key_still_works(self, minimal_state, mock_anthropic_client):
        # Claude returns flat JSON without the "taxonomy_financials" wrapper
        flat_response = json.dumps({
            "capex_total_eur": 30000000.0,
            "capex_green_eur": 9000000.0,
            "revenue_eur": 200000000.0,
            "fiscal_year": "2024",
            "taxonomy_activities": [],
            "confidence": 0.7,
        })
        mock_anthropic_client.messages.create.return_value = _make_mock_claude_response(flat_response)
        result = fetcher_node(minimal_state)
        fin = result["taxonomy_financials"]
        assert fin.capex_total_eur == 30000000.0
        assert fin.capex_green_eur == 9000000.0
        assert fin.confidence == 0.7

    def test_empty_response_returns_safe_defaults(self, minimal_state, mock_anthropic_client):
        mock_anthropic_client.messages.create.return_value = _make_mock_claude_response("{}")
        result = fetcher_node(minimal_state)
        fin = result["taxonomy_financials"]
        assert fin.capex_total_eur is None
        assert fin.fiscal_year == "Unknown"

    def test_empty_taxonomy_data_still_calls_api(self, mock_anthropic_client):
        state = {
            "audit_id": "test-empty",
            "mode": "full_audit",
            "report_json": {},
            "esrs_data": {},
            "taxonomy_data": {},
            "entity_id": "EmptyCorp",
            "logs": [],
            "pipeline_trace": [],
        }
        fetcher_node(state)
        assert mock_anthropic_client.messages.create.call_count == 1


# ═══════════════════════════════════════════════════════════════════════════
# F. State Management
# ═══════════════════════════════════════════════════════════════════════════

class TestStateManagement:
    """Verify state keys are correctly read and written."""

    def test_logs_are_accumulated(self, minimal_state, mock_anthropic_client):
        minimal_state["logs"] = [{"agent": "extractor", "msg": "pre-existing", "ts": 0}]
        result = fetcher_node(minimal_state)
        assert result["logs"][0]["msg"] == "pre-existing"
        assert len(result["logs"]) > 1

    def test_pipeline_trace_includes_fetcher(self, minimal_state, mock_anthropic_client):
        result = fetcher_node(minimal_state)
        fetcher_traces = [t for t in result["pipeline_trace"] if t["agent"] == "fetcher"]
        assert len(fetcher_traces) == 1
        assert "ms" in fetcher_traces[0]
        assert "started_at" in fetcher_traces[0]

    def test_does_not_modify_input_keys(self, minimal_state, mock_anthropic_client):
        original_audit_id = minimal_state["audit_id"]
        original_entity_id = minimal_state["entity_id"]
        result = fetcher_node(minimal_state)
        assert "audit_id" not in result
        assert "entity_id" not in result
        assert minimal_state["audit_id"] == original_audit_id
        assert minimal_state["entity_id"] == original_entity_id

    def test_returns_correct_output_keys(self, minimal_state, mock_anthropic_client):
        result = fetcher_node(minimal_state)
        assert "taxonomy_financials" in result
        assert "document_source" in result
        assert "logs" in result
        assert "pipeline_trace" in result
        assert isinstance(result["taxonomy_financials"], TaxonomyFinancials)
        assert isinstance(result["document_source"], RegistrySource)

    def test_document_source_populated(self, minimal_state, mock_anthropic_client):
        result = fetcher_node(minimal_state)
        doc = result["document_source"]
        assert doc.name == "Annual Management Report"
        assert doc.registry_type == "eu_bris"
        assert doc.jurisdiction == "EU"

    def test_pipeline_trace_accumulates_from_prior_nodes(self, minimal_state, mock_anthropic_client):
        minimal_state["pipeline_trace"] = [{"agent": "extractor", "started_at": 1.0, "ms": 500}]
        result = fetcher_node(minimal_state)
        assert len(result["pipeline_trace"]) == 2
        assert result["pipeline_trace"][0]["agent"] == "extractor"
        assert result["pipeline_trace"][1]["agent"] == "fetcher"


# ═══════════════════════════════════════════════════════════════════════════
# G. PRD Gate — taxonomy_financials.capex_total_eur and capex_green_eur populated
# ═══════════════════════════════════════════════════════════════════════════

class TestPRDGate:
    """Verify the PRD iteration 6 gate: taxonomy_financials populated from real report JSON."""

    def test_gate_capex_total_eur_populated(self, minimal_state, mock_anthropic_client):
        """With a realistic mock response, capex_total_eur should be populated."""
        result = fetcher_node(minimal_state)
        fin = result["taxonomy_financials"]
        assert fin.capex_total_eur is not None, "PRD Gate: capex_total_eur must be populated"
        assert fin.capex_total_eur > 0

    def test_gate_capex_green_eur_populated(self, minimal_state, mock_anthropic_client):
        """With a realistic mock response, capex_green_eur should be populated."""
        result = fetcher_node(minimal_state)
        fin = result["taxonomy_financials"]
        assert fin.capex_green_eur is not None, "PRD Gate: capex_green_eur must be populated"
        assert fin.capex_green_eur > 0

    def test_gate_confidence_above_threshold(self, minimal_state, mock_anthropic_client):
        """Confidence should be above 0.5 for structured iXBRL data."""
        result = fetcher_node(minimal_state)
        fin = result["taxonomy_financials"]
        assert fin.confidence > 0.5, "PRD Gate: confidence should be > 0.5 for structured data"

    def test_gate_fiscal_year_populated(self, minimal_state, mock_anthropic_client):
        result = fetcher_node(minimal_state)
        fin = result["taxonomy_financials"]
        assert fin.fiscal_year != "Unknown"

    def test_gate_valid_pydantic_model(self, minimal_state, mock_anthropic_client):
        """Result must be a valid TaxonomyFinancials model that serializes cleanly."""
        result = fetcher_node(minimal_state)
        fin = result["taxonomy_financials"]
        assert isinstance(fin, TaxonomyFinancials)
        d = fin.model_dump()
        assert "capex_total_eur" in d
        assert "capex_green_eur" in d
        assert "revenue_eur" in d
        assert "taxonomy_activities" in d

    def test_gate_revenue_populated(self, minimal_state, mock_anthropic_client):
        result = fetcher_node(minimal_state)
        fin = result["taxonomy_financials"]
        assert fin.revenue_eur is not None
        assert fin.revenue_eur > 0


# ═══════════════════════════════════════════════════════════════════════════
# H. Integration with downstream nodes (regression)
# ═══════════════════════════════════════════════════════════════════════════

class TestDownstreamIntegration:
    """Verify fetcher output is compatible with auditor and consultant stubs."""

    def test_auditor_accepts_fetcher_output(self, minimal_state, mock_anthropic_client):
        """Auditor stub should run without error using real fetcher's output."""
        from agents.auditor import auditor_node

        fetcher_result = fetcher_node(minimal_state)
        combined_state = {**minimal_state}
        # Simulate extractor output (stub)
        from agents.extractor import extractor_node
        ext_result = extractor_node(minimal_state)
        combined_state.update(ext_result)
        combined_state.update(fetcher_result)

        auditor_result = auditor_node(combined_state)
        assert "esrs_ledger" in auditor_result
        assert "taxonomy_alignment" in auditor_result

    def test_full_pipeline_with_real_fetcher(self, minimal_state, mock_anthropic_client):
        """v5.0 3-node pipeline completes end-to-end (extractor→scorer→advisor)."""
        from graph import graph
        from schemas import ComplianceResult

        result = graph.invoke(minimal_state)
        assert result.get("final_result") is not None
        fr = result["final_result"]
        assert isinstance(fr, ComplianceResult)
        assert fr.schema_version == "3.0"
