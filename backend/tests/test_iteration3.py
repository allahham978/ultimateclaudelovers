"""
Iteration 3 tests — Real Extractor Node with mocked Claude API.

LEGACY: These tests target the v2.0 Claude-API-calling extractor which has been
replaced by a dual-mode stub in v5.0 (Iteration 8). The functions tested here
(MODEL, _build_claims, _build_company_meta, _parse_llm_json, _safe_defaults)
no longer exist in agents/extractor.py.

All tests in this file are skipped until the real Claude extractor is
re-implemented (planned for a future iteration).
"""

import pytest

pytestmark = pytest.mark.skip(reason="v5.0 pivot: extractor is now a stub; real Claude API extractor tests deferred")


# ═══════════════════════════════════════════════════════════════════════════
# A. Claude API Call Construction
# ═══════════════════════════════════════════════════════════════════════════

class TestClaudeAPICall:
    """Verify that the extractor builds and sends the correct Claude API request."""

    def test_calls_correct_model(self, minimal_state, mock_anthropic_client):
        extractor_node(minimal_state)
        call_kwargs = mock_anthropic_client.messages.create.call_args
        assert call_kwargs.kwargs["model"] == "claude-sonnet-4-6"

    def test_uses_extractor_system_prompt(self, minimal_state, mock_anthropic_client):
        extractor_node(minimal_state)
        call_kwargs = mock_anthropic_client.messages.create.call_args
        assert call_kwargs.kwargs["system"] == SYSTEM_PROMPT_EXTRACTOR

    def test_sends_esrs_data_in_message(self, minimal_state, mock_anthropic_client):
        extractor_node(minimal_state)
        call_kwargs = mock_anthropic_client.messages.create.call_args
        messages = call_kwargs.kwargs["messages"]
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        # The esrs_data JSON should appear in one of the content blocks
        content_blocks = messages[0]["content"]
        esrs_json_str = json.dumps(minimal_state["esrs_data"], indent=2)
        found = any(block.get("text") == esrs_json_str for block in content_blocks)
        assert found, "esrs_data JSON not found in message content blocks"

    def test_prompt_caching_enabled(self, minimal_state, mock_anthropic_client):
        extractor_node(minimal_state)
        call_kwargs = mock_anthropic_client.messages.create.call_args
        messages = call_kwargs.kwargs["messages"]
        content_blocks = messages[0]["content"]
        cache_blocks = [b for b in content_blocks if b.get("cache_control") == {"type": "ephemeral"}]
        assert len(cache_blocks) == 1, "Exactly one content block should have cache_control: ephemeral"

    def test_max_tokens_set(self, minimal_state, mock_anthropic_client):
        extractor_node(minimal_state)
        call_kwargs = mock_anthropic_client.messages.create.call_args
        assert call_kwargs.kwargs["max_tokens"] == MAX_TOKENS

    def test_api_called_exactly_once(self, minimal_state, mock_anthropic_client):
        extractor_node(minimal_state)
        assert mock_anthropic_client.messages.create.call_count == 1


# ═══════════════════════════════════════════════════════════════════════════
# B. JSON Response Parsing (_parse_llm_json)
# ═══════════════════════════════════════════════════════════════════════════

class TestParseLLMJson:
    """Verify robust JSON parsing from Claude responses."""

    def test_parses_clean_json(self):
        raw = '{"company_meta": {"name": "Foo"}, "esrs_claims": {}}'
        result = _parse_llm_json(raw)
        assert result["company_meta"]["name"] == "Foo"

    def test_parses_json_in_markdown_fences(self):
        raw = '```json\n{"company_meta": {"name": "Bar"}, "esrs_claims": {}}\n```'
        result = _parse_llm_json(raw)
        assert result["company_meta"]["name"] == "Bar"

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

    def test_parses_nested_structures(self):
        data = {"esrs_claims": {"E1-1": {"data_point": "test", "confidence": 0.9}}}
        raw = json.dumps(data)
        result = _parse_llm_json(raw)
        assert result["esrs_claims"]["E1-1"]["confidence"] == 0.9


# ═══════════════════════════════════════════════════════════════════════════
# C. CompanyMeta Extraction (_build_company_meta)
# ═══════════════════════════════════════════════════════════════════════════

class TestBuildCompanyMeta:
    """Verify CompanyMeta construction from Claude's parsed response."""

    def test_extracts_all_fields(self):
        raw = {
            "name": "Lumiere SA",
            "lei": "529900A1B2C3D4E5F6G7",
            "sector": "AI Infrastructure",
            "fiscal_year": 2024,
            "jurisdiction": "France",
            "report_title": "Annual Management Report 2024",
        }
        meta = _build_company_meta(raw, "fallback")
        assert meta.name == "Lumiere SA"
        assert meta.lei == "529900A1B2C3D4E5F6G7"
        assert meta.sector == "AI Infrastructure"
        assert meta.fiscal_year == 2024
        assert meta.jurisdiction == "France"
        assert meta.report_title == "Annual Management Report 2024"

    def test_handles_null_lei(self):
        raw = {"name": "Corp", "lei": None, "sector": "Tech", "fiscal_year": 2024,
               "jurisdiction": "DE", "report_title": "Report"}
        meta = _build_company_meta(raw, "fallback")
        assert meta.lei is None

    def test_falls_back_to_entity_id_for_missing_name(self):
        raw = {"sector": "Tech", "fiscal_year": 2024,
               "jurisdiction": "DE", "report_title": "Report"}
        meta = _build_company_meta(raw, "FallbackCorp")
        assert meta.name == "FallbackCorp"

    def test_fiscal_year_is_int(self):
        raw = {"name": "Corp", "sector": "Tech", "fiscal_year": "2024",
               "jurisdiction": "DE", "report_title": "Report"}
        meta = _build_company_meta(raw, "fallback")
        assert isinstance(meta.fiscal_year, int)
        assert meta.fiscal_year == 2024


# ═══════════════════════════════════════════════════════════════════════════
# D. ESRSClaim Building (_build_claims)
# ═══════════════════════════════════════════════════════════════════════════

class TestBuildClaims:
    """Verify ESRSClaim dict construction from Claude's parsed response."""

    def test_builds_all_three_standards(self):
        raw = {
            "E1-1": {"data_point": "Transition Plan", "disclosed_value": "Net-zero 2040", "confidence": 0.85},
            "E1-5": {"data_point": "Energy", "disclosed_value": "45000 MWh", "unit": "MWh", "confidence": 0.90},
            "E1-6": {"data_point": "GHG", "disclosed_value": "1200 tCO2eq", "unit": "tCO2eq", "confidence": 0.80},
        }
        claims = _build_claims(raw)
        assert set(claims.keys()) == {"E1-1", "E1-5", "E1-6"}
        assert all(isinstance(c, ESRSClaim) for c in claims.values())

    def test_fills_missing_standard_with_defaults(self):
        raw = {"E1-1": {"data_point": "Transition Plan", "confidence": 0.85}}
        claims = _build_claims(raw)
        assert claims["E1-5"].confidence == 0.0
        assert claims["E1-5"].disclosed_value is None
        assert claims["E1-6"].confidence == 0.0

    def test_confidence_boundary_values(self):
        raw = {
            "E1-1": {"data_point": "test", "confidence": 0.0},
            "E1-5": {"data_point": "test", "confidence": 0.5},
            "E1-6": {"data_point": "test", "confidence": 1.0},
        }
        claims = _build_claims(raw)
        assert claims["E1-1"].confidence == 0.0
        assert claims["E1-5"].confidence == 0.5
        assert claims["E1-6"].confidence == 1.0

    def test_preserves_xbrl_concept(self):
        raw = {"E1-1": {"data_point": "test", "confidence": 0.9, "xbrl_concept": "esrs_E1-1_01"}}
        claims = _build_claims(raw)
        assert claims["E1-1"].xbrl_concept == "esrs_E1-1_01"

    def test_handles_null_optional_fields(self):
        raw = {"E1-1": {"data_point": "test", "disclosed_value": None, "unit": None, "confidence": 0.0, "xbrl_concept": None}}
        claims = _build_claims(raw)
        assert claims["E1-1"].disclosed_value is None
        assert claims["E1-1"].unit is None
        assert claims["E1-1"].xbrl_concept is None


# ═══════════════════════════════════════════════════════════════════════════
# E. Error Handling / Fallback
# ═══════════════════════════════════════════════════════════════════════════

class TestErrorHandling:
    """Verify graceful degradation — never halts the graph."""

    def test_api_error_returns_safe_defaults(self, minimal_state, mock_anthropic_client):
        mock_anthropic_client.messages.create.side_effect = Exception("API connection failed")
        result = extractor_node(minimal_state)
        claims = result["esrs_claims"]
        assert all(claims[std].confidence == 0.0 for std in ("E1-1", "E1-5", "E1-6"))
        assert all(claims[std].disclosed_value is None for std in ("E1-1", "E1-5", "E1-6"))

    def test_api_error_logs_error(self, minimal_state, mock_anthropic_client):
        mock_anthropic_client.messages.create.side_effect = Exception("API connection failed")
        result = extractor_node(minimal_state)
        error_logs = [l for l in result["logs"] if "Error" in l.get("msg", "")]
        assert len(error_logs) >= 1
        assert "API connection failed" in error_logs[0]["msg"]

    def test_malformed_json_returns_safe_defaults(self, minimal_state, mock_anthropic_client):
        mock_anthropic_client.messages.create.return_value = _make_mock_claude_response("not valid json {{{")
        result = extractor_node(minimal_state)
        claims = result["esrs_claims"]
        assert all(claims[std].confidence == 0.0 for std in ("E1-1", "E1-5", "E1-6"))

    def test_missing_esrs_claims_key_returns_defaults(self, minimal_state, mock_anthropic_client):
        mock_anthropic_client.messages.create.return_value = _make_mock_claude_response(
            json.dumps({"company_meta": {"name": "Corp"}})
        )
        result = extractor_node(minimal_state)
        claims = result["esrs_claims"]
        # Missing standards get confidence 0.0
        assert all(claims[std].confidence == 0.0 for std in ("E1-1", "E1-5", "E1-6"))

    def test_missing_company_meta_uses_entity_id(self, minimal_state, mock_anthropic_client):
        mock_anthropic_client.messages.create.return_value = _make_mock_claude_response(
            json.dumps({"esrs_claims": {}})
        )
        result = extractor_node(minimal_state)
        assert result["company_meta"].name == "TestCorp SA"

    def test_empty_esrs_data_still_calls_api(self, mock_anthropic_client):
        state = {
            "audit_id": "test-empty",
            "report_json": {},
            "esrs_data": {},
            "taxonomy_data": {},
            "entity_id": "EmptyCorp",
            "logs": [],
            "pipeline_trace": [],
        }
        extractor_node(state)
        assert mock_anthropic_client.messages.create.call_count == 1


# ═══════════════════════════════════════════════════════════════════════════
# F. Safe Defaults Helper
# ═══════════════════════════════════════════════════════════════════════════

class TestSafeDefaults:
    """Verify _safe_defaults returns properly shaped fallback data."""

    def test_all_claims_have_zero_confidence(self):
        claims, _ = _safe_defaults("TestCorp")
        assert all(c.confidence == 0.0 for c in claims.values())

    def test_all_claims_have_null_disclosed_value(self):
        claims, _ = _safe_defaults("TestCorp")
        assert all(c.disclosed_value is None for c in claims.values())

    def test_meta_uses_entity_id(self):
        _, meta = _safe_defaults("TestCorp")
        assert meta.name == "TestCorp"

    def test_contains_all_three_standards(self):
        claims, _ = _safe_defaults("TestCorp")
        assert set(claims.keys()) == {"E1-1", "E1-5", "E1-6"}


# ═══════════════════════════════════════════════════════════════════════════
# G. State Management
# ═══════════════════════════════════════════════════════════════════════════

class TestStateManagement:
    """Verify state keys are correctly read and written."""

    def test_logs_are_accumulated(self, minimal_state, mock_anthropic_client):
        minimal_state["logs"] = [{"agent": "init", "msg": "pre-existing", "ts": 0}]
        result = extractor_node(minimal_state)
        assert result["logs"][0]["msg"] == "pre-existing"
        assert len(result["logs"]) > 1

    def test_pipeline_trace_includes_extractor(self, minimal_state, mock_anthropic_client):
        result = extractor_node(minimal_state)
        extractor_traces = [t for t in result["pipeline_trace"] if t["agent"] == "extractor"]
        assert len(extractor_traces) == 1
        assert "ms" in extractor_traces[0]
        assert "started_at" in extractor_traces[0]

    def test_does_not_modify_input_keys(self, minimal_state, mock_anthropic_client):
        original_audit_id = minimal_state["audit_id"]
        original_entity_id = minimal_state["entity_id"]
        result = extractor_node(minimal_state)
        assert "audit_id" not in result
        assert "entity_id" not in result
        assert minimal_state["audit_id"] == original_audit_id
        assert minimal_state["entity_id"] == original_entity_id

    def test_returns_correct_output_keys(self, minimal_state, mock_anthropic_client):
        result = extractor_node(minimal_state)
        assert "company_meta" in result
        assert "esrs_claims" in result
        assert "logs" in result
        assert "pipeline_trace" in result
        assert isinstance(result["company_meta"], CompanyMeta)
        assert isinstance(result["esrs_claims"], dict)


# ═══════════════════════════════════════════════════════════════════════════
# H. PRD Gate — esrs_claims contains values with confidence > 0.5
# ═══════════════════════════════════════════════════════════════════════════

class TestPRDGate:
    """Verify the PRD iteration 3 gate: esrs_claims contains real values with confidence > 0.5."""

    def test_gate_esrs_claims_have_confidence_above_half(self, minimal_state, mock_anthropic_client):
        """With a realistic mock response, at least one claim should have confidence > 0.5."""
        result = extractor_node(minimal_state)
        claims = result["esrs_claims"]
        high_confidence = [c for c in claims.values() if c.confidence > 0.5]
        assert len(high_confidence) >= 1, "PRD Gate: at least one esrs_claim must have confidence > 0.5"

    def test_gate_all_three_standards_present(self, minimal_state, mock_anthropic_client):
        result = extractor_node(minimal_state)
        claims = result["esrs_claims"]
        assert "E1-1" in claims
        assert "E1-5" in claims
        assert "E1-6" in claims

    def test_gate_company_meta_populated(self, minimal_state, mock_anthropic_client):
        result = extractor_node(minimal_state)
        meta = result["company_meta"]
        assert meta.name != "Unknown Entity"
        assert meta.fiscal_year > 0
