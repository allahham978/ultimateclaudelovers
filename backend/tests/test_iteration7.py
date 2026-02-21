"""
Iteration 7 Unit Tests — Real Auditor Node (Both Modes)

Gate: esrs_ledger contains 3 valid ESRSLedgerItem objects.
      Full audit produces valid ESRS ledger.
      Compliance check produces valid coverage assessment + cost estimate range.

Tests cover:
  - Claude API call construction (model, prompt, input payload)
  - JSON response parsing (_parse_llm_json)
  - Deterministic double materiality scoring (all 3 ESRS standards)
  - Financial materiality scoring from TaxonomyFinancials
  - Taxonomy alignment calculation
  - Compliance cost computation (Art. 51 CSRD)
  - Full audit output validation (3 ESRSLedgerItem, taxonomy_alignment, compliance_cost)
  - Compliance check output validation (esrs_coverage + compliance_cost_estimate)
  - Error handling / fallback to deterministic scoring
  - State management (logs, pipeline_trace)
  - PRD gate checks
"""

import json
from unittest.mock import MagicMock, patch

import pytest

import sys
import os

_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from agents.auditor import (
    MODEL,
    MAX_TOKENS,
    ESRS_STANDARDS,
    _parse_llm_json,
    _score_impact_e1_1,
    _score_impact_e1_5,
    _score_impact_e1_6,
    _score_financial_materiality,
    _materiality_level,
    _esrs_status,
    _compute_taxonomy_alignment,
    _compute_compliance_cost,
    _build_ledger_deterministic,
    _build_ledger_from_llm,
    _build_coverage_deterministic,
    _compute_cost_estimate,
    auditor_node,
)
from schemas import (
    ComplianceCost,
    ESRSClaim,
    ESRSLedgerItem,
    TaxonomyAlignment,
    TaxonomyFinancials,
)
from tools.prompts import SYSTEM_PROMPT_AUDITOR, SYSTEM_PROMPT_AUDITOR_LITE
from tests.conftest import (
    MOCK_AUDITOR_RESPONSE_JSON,
    MOCK_AUDITOR_LITE_RESPONSE_JSON,
    STUB_TAXONOMY_FINANCIALS,
    STUB_ESRS_CLAIMS,
    STUB_COMPLIANCE_ESRS_CLAIMS,
    _make_mock_claude_response,
)


# ═══════════════════════════════════════════════════════════════════════════
# A. JSON Response Parsing (_parse_llm_json)
# ═══════════════════════════════════════════════════════════════════════════

class TestParseLLMJson:
    """Verify robust JSON parsing from Claude responses."""

    def test_parses_clean_json(self):
        raw = '{"esrs_ledger": [], "taxonomy_alignment": {}}'
        result = _parse_llm_json(raw)
        assert "esrs_ledger" in result

    def test_parses_json_in_markdown_fences(self):
        raw = '```json\n{"key": "value"}\n```'
        result = _parse_llm_json(raw)
        assert result["key"] == "value"

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
        data = {"esrs_ledger": [{"esrs_id": "E1-1", "status": "disclosed"}]}
        result = _parse_llm_json(json.dumps(data))
        assert result["esrs_ledger"][0]["status"] == "disclosed"


# ═══════════════════════════════════════════════════════════════════════════
# B. Impact Materiality Scoring — E1-1 (Transition Plan)
# ═══════════════════════════════════════════════════════════════════════════

class TestScoreImpactE1_1:
    """Verify E1-1 scoring rubric against known claim patterns."""

    def test_full_disclosure_high_score(self):
        claim = ESRSClaim(
            standard="E1-1",
            data_point="Transition Plan",
            disclosed_value="Net-zero by 2040; EUR 15M CapEx committed; 1.5°C pathway aligned",
            unit=None,
            confidence=0.85,
        )
        score = _score_impact_e1_1(claim)
        # +35 (target year 2040) +25 (CapEx EUR) +20 (1.5°C) = 80
        assert score == 80

    def test_target_year_only(self):
        claim = ESRSClaim(
            standard="E1-1",
            data_point="Transition Plan",
            disclosed_value="Net-zero by 2040",
            unit=None,
            confidence=0.85,
        )
        score = _score_impact_e1_1(claim)
        # +35 (target year) = 35
        assert score == 35

    def test_low_confidence_penalty(self):
        claim = ESRSClaim(
            standard="E1-1",
            data_point="Transition Plan",
            disclosed_value="Net-zero by 2040",
            unit=None,
            confidence=0.3,
        )
        score = _score_impact_e1_1(claim)
        # +35 (target year) -30 (confidence < 0.5) = 5
        assert score == 5

    def test_no_target_year_penalty(self):
        claim = ESRSClaim(
            standard="E1-1",
            data_point="Transition Plan",
            disclosed_value="We plan to decarbonise",
            unit=None,
            confidence=0.6,
        )
        score = _score_impact_e1_1(claim)
        # -20 (no target year) → clamped to 0
        assert score == 0

    def test_null_claim_returns_zero(self):
        assert _score_impact_e1_1(None) == 0

    def test_null_disclosed_value(self):
        claim = ESRSClaim(
            standard="E1-1",
            data_point="Transition Plan",
            disclosed_value=None,
            unit=None,
            confidence=0.0,
        )
        score = _score_impact_e1_1(claim)
        # No value → -30 (confidence 0 < 0.5) -20 (no year) → clamped to 0
        assert score == 0

    def test_stub_data_score(self):
        """Score against the known stub E1-1 claim from extractor."""
        claim = STUB_ESRS_CLAIMS["E1-1"]
        score = _score_impact_e1_1(claim)
        # disclosed_value="Net-zero by 2040; 50% reduction by 2030 vs 2019 baseline"
        # +35 (target year 2040 or 2030) = 35, no EUR CapEx → 0, no 1.5C → 0
        # confidence 0.85 → no penalty
        assert score == 35


# ═══════════════════════════════════════════════════════════════════════════
# C. Impact Materiality Scoring — E1-5 (Energy)
# ═══════════════════════════════════════════════════════════════════════════

class TestScoreImpactE1_5:
    """Verify E1-5 scoring rubric."""

    def test_full_disclosure_high_score(self):
        claim = ESRSClaim(
            standard="E1-5",
            data_point="Energy",
            disclosed_value="Total energy: 45,000 MWh; Renewable mix: 38%; YoY reduction 5%",
            unit="MWh",
            confidence=0.95,
        )
        score = _score_impact_e1_5(claim)
        # +40 (energy+unit) +30 (renewable %) +20 (YoY) = 90
        assert score == 90

    def test_energy_with_unit_only(self):
        claim = ESRSClaim(
            standard="E1-5",
            data_point="Energy",
            disclosed_value="Total energy consumption 45,000",
            unit="MWh",
            confidence=0.90,
        )
        score = _score_impact_e1_5(claim)
        # +40 (unit present + digit) = 40
        assert score == 40

    def test_estimated_values_penalty(self):
        claim = ESRSClaim(
            standard="E1-5",
            data_point="Energy",
            disclosed_value="Approximately 45,000 MWh estimated; Renewable 38%",
            unit="MWh",
            confidence=0.7,
        )
        score = _score_impact_e1_5(claim)
        # +40 (energy+unit) +30 (renewable %) -25 (estimated) = 45
        assert score == 45

    def test_null_claim_returns_zero(self):
        assert _score_impact_e1_5(None) == 0

    def test_missing_unit_penalty(self):
        claim = ESRSClaim(
            standard="E1-5",
            data_point="Energy",
            disclosed_value="We consume energy",
            unit=None,
            confidence=0.5,
        )
        score = _score_impact_e1_5(claim)
        # No digit in value with unit → no +40. No unit → -15. Clamped to 0.
        assert score == 0

    def test_stub_data_score(self):
        """Score against the known stub E1-5 claim from extractor."""
        claim = STUB_ESRS_CLAIMS["E1-5"]
        score = _score_impact_e1_5(claim)
        # disclosed_value="Total energy: 45,000 MWh; Renewable mix: 38%"
        # unit="MWh", confidence=0.90
        # +40 (unit+digit) +30 (renewable %) = 70
        assert score == 70


# ═══════════════════════════════════════════════════════════════════════════
# D. Impact Materiality Scoring — E1-6 (GHG Emissions)
# ═══════════════════════════════════════════════════════════════════════════

class TestScoreImpactE1_6:
    """Verify E1-6 scoring rubric."""

    def test_full_disclosure_high_score(self):
        claim = ESRSClaim(
            standard="E1-6",
            data_point="GHG",
            disclosed_value="Scope 1: 1,200 tCO2eq; Scope 2 (market-based): 8,500; Scope 3 total: 50,000; GHG intensity: 0.5 per EUR revenue; GHG Protocol methodology",
            unit="tCO2eq",
            confidence=0.95,
        )
        score = _score_impact_e1_6(claim)
        # +30 (Scope 1+2) +30 (Scope 3) +20 (intensity) = 80
        assert score == 80

    def test_scope1_and_2_only(self):
        claim = ESRSClaim(
            standard="E1-6",
            data_point="GHG",
            disclosed_value="Scope 1: 1,200 tCO2eq; Scope 2 (market-based): 8,500 tCO2eq",
            unit="tCO2eq",
            confidence=0.80,
        )
        score = _score_impact_e1_6(claim)
        # +30 (Scope 1+2) -20 (no Scope 3) -15 (no methodology) = -5 → clamped to 0
        assert score == 0

    def test_all_scopes_no_intensity(self):
        claim = ESRSClaim(
            standard="E1-6",
            data_point="GHG",
            disclosed_value="Scope 1: 1,200; Scope 2: 8,500; Scope 3: 50,000",
            unit="tCO2eq",
            confidence=0.80,
        )
        score = _score_impact_e1_6(claim)
        # +30 (Scope 1+2) +30 (Scope 3) -15 (no methodology) = 45
        assert score == 45

    def test_null_claim_returns_zero(self):
        assert _score_impact_e1_6(None) == 0

    def test_stub_data_score(self):
        """Score against the known stub E1-6 claim from extractor."""
        claim = STUB_ESRS_CLAIMS["E1-6"]
        score = _score_impact_e1_6(claim)
        # disclosed_value="Scope 1: 1,200 tCO2eq; Scope 2 (market-based): 8,500 tCO2eq"
        # +30 (Scope 1+2) -20 (no Scope 3) -15 (no methodology) → clamped to 0
        assert score == 0


# ═══════════════════════════════════════════════════════════════════════════
# E. Financial Materiality Scoring
# ═══════════════════════════════════════════════════════════════════════════

class TestScoreFinancialMateriality:
    """Verify financial materiality scoring from TaxonomyFinancials."""

    def test_green_capex_above_30pct(self):
        """Stub data: 35% green CapEx → +20 (present) +40 (>30%) = 60."""
        score = _score_financial_materiality(STUB_TAXONOMY_FINANCIALS)
        assert score == 60

    def test_green_capex_between_15_and_30pct(self):
        tf = TaxonomyFinancials(
            capex_total_eur=100_000_000,
            capex_green_eur=20_000_000,  # 20%
            revenue_eur=250_000_000,
            fiscal_year="2024",
            confidence=0.9,
        )
        score = _score_financial_materiality(tf)
        # +20 (present) +30 (>15%) = 50
        assert score == 50

    def test_green_capex_below_10pct(self):
        tf = TaxonomyFinancials(
            capex_total_eur=100_000_000,
            capex_green_eur=5_000_000,  # 5%
            revenue_eur=250_000_000,
            fiscal_year="2024",
            confidence=0.9,
        )
        score = _score_financial_materiality(tf)
        # +20 (present) -30 (<10%) = 0 (clamped)
        assert score == 0

    def test_null_taxonomy_financials(self):
        score = _score_financial_materiality(None)
        # -20 (null capex_total) → clamped to 0
        assert score == 0

    def test_null_capex_total(self):
        tf = TaxonomyFinancials(
            capex_total_eur=None,
            capex_green_eur=None,
            revenue_eur=250_000_000,
            fiscal_year="2024",
            confidence=0.0,
        )
        score = _score_financial_materiality(tf)
        assert score == 0

    def test_zero_capex_total(self):
        tf = TaxonomyFinancials(
            capex_total_eur=0.0,
            capex_green_eur=0.0,
            revenue_eur=250_000_000,
            fiscal_year="2024",
            confidence=0.9,
        )
        score = _score_financial_materiality(tf)
        assert score == 0

    def test_null_capex_green(self):
        tf = TaxonomyFinancials(
            capex_total_eur=50_000_000,
            capex_green_eur=None,
            revenue_eur=250_000_000,
            fiscal_year="2024",
            confidence=0.9,
        )
        score = _score_financial_materiality(tf)
        # +20 (present) -20 (null green) = 0
        assert score == 0


# ═══════════════════════════════════════════════════════════════════════════
# F. Materiality Level Mapping
# ═══════════════════════════════════════════════════════════════════════════

class TestMaterialityLevel:
    """Verify score → label mapping boundaries."""

    def test_high(self):
        assert _materiality_level(70) == "high"
        assert _materiality_level(100) == "high"

    def test_medium(self):
        assert _materiality_level(40) == "medium"
        assert _materiality_level(69) == "medium"

    def test_low(self):
        assert _materiality_level(20) == "low"
        assert _materiality_level(39) == "low"

    def test_not_material(self):
        assert _materiality_level(0) == "not_material"
        assert _materiality_level(19) == "not_material"


# ═══════════════════════════════════════════════════════════════════════════
# G. ESRS Status Classification
# ═══════════════════════════════════════════════════════════════════════════

class TestESRSStatus:
    """Verify status classification rules."""

    def test_disclosed(self):
        assert _esrs_status(70, 60, "some value") == "disclosed"

    def test_partial(self):
        assert _esrs_status(45, 60, "some value") == "partial"

    def test_missing_null_value(self):
        assert _esrs_status(50, 60, None) == "missing"

    def test_non_compliant_override(self):
        """Financial score < 20 overrides everything."""
        assert _esrs_status(90, 15, "some value") == "non_compliant"
        assert _esrs_status(90, 10, None) == "non_compliant"

    def test_missing_low_impact(self):
        assert _esrs_status(30, 60, "value") == "missing"

    def test_boundary_disclosed(self):
        assert _esrs_status(70, 20, "value") == "disclosed"

    def test_boundary_partial(self):
        assert _esrs_status(40, 20, "value") == "partial"


# ═══════════════════════════════════════════════════════════════════════════
# H. Taxonomy Alignment Calculation
# ═══════════════════════════════════════════════════════════════════════════

class TestTaxonomyAlignment:
    """Verify taxonomy alignment formula and thresholds."""

    def test_stub_financials_35pct(self):
        pct, status, label = _compute_taxonomy_alignment(STUB_TAXONOMY_FINANCIALS)
        assert pct == 35.0
        assert status == "partially_aligned"
        assert "35.0%" in label

    def test_aligned_above_60(self):
        tf = TaxonomyFinancials(
            capex_total_eur=100, capex_green_eur=65, fiscal_year="2024", confidence=1.0,
        )
        pct, status, _ = _compute_taxonomy_alignment(tf)
        assert pct == 65.0
        assert status == "aligned"

    def test_non_compliant_below_20(self):
        tf = TaxonomyFinancials(
            capex_total_eur=100, capex_green_eur=10, fiscal_year="2024", confidence=1.0,
        )
        pct, status, _ = _compute_taxonomy_alignment(tf)
        assert pct == 10.0
        assert status == "non_compliant"

    def test_null_financials_returns_zero(self):
        pct, status, _ = _compute_taxonomy_alignment(None)
        assert pct == 0.0
        assert status == "non_compliant"

    def test_clamps_to_100(self):
        tf = TaxonomyFinancials(
            capex_total_eur=50, capex_green_eur=100, fiscal_year="2024", confidence=1.0,
        )
        pct, _, _ = _compute_taxonomy_alignment(tf)
        assert pct == 100.0


# ═══════════════════════════════════════════════════════════════════════════
# I. Compliance Cost Calculation (Art. 51 CSRD)
# ═══════════════════════════════════════════════════════════════════════════

class TestComplianceCost:
    """Verify Art. 51 compliance cost formula."""

    def test_no_non_compliant_items(self):
        ledger = [
            ESRSLedgerItem(id="1", esrs_id="E1-1", data_point="a", impact_materiality="high",
                           financial_materiality="high", status="disclosed",
                           evidence_source="management_report", registry_evidence="x"),
            ESRSLedgerItem(id="2", esrs_id="E1-5", data_point="b", impact_materiality="high",
                           financial_materiality="high", status="disclosed",
                           evidence_source="management_report", registry_evidence="x"),
            ESRSLedgerItem(id="3", esrs_id="E1-6", data_point="c", impact_materiality="high",
                           financial_materiality="high", status="partial",
                           evidence_source="management_report", registry_evidence="x"),
        ]
        cost = _compute_compliance_cost(ledger, 250_000_000)
        assert cost.projected_fine_eur == 0.0

    def test_one_missing_item(self):
        ledger = [
            ESRSLedgerItem(id="1", esrs_id="E1-1", data_point="a", impact_materiality="high",
                           financial_materiality="high", status="disclosed",
                           evidence_source="management_report", registry_evidence="x"),
            ESRSLedgerItem(id="2", esrs_id="E1-5", data_point="b", impact_materiality="high",
                           financial_materiality="high", status="disclosed",
                           evidence_source="management_report", registry_evidence="x"),
            ESRSLedgerItem(id="3", esrs_id="E1-6", data_point="c", impact_materiality="low",
                           financial_materiality="low", status="missing",
                           evidence_source="management_report", registry_evidence="x"),
        ]
        cost = _compute_compliance_cost(ledger, 250_000_000)
        # 1/3 * 250M * 0.05 = 4,166,666.67
        assert cost.projected_fine_eur == pytest.approx(4_166_666.67, abs=0.01)

    def test_all_non_compliant(self):
        ledger = [
            ESRSLedgerItem(id="1", esrs_id="E1-1", data_point="a", impact_materiality="not_material",
                           financial_materiality="not_material", status="non_compliant",
                           evidence_source="management_report", registry_evidence="x"),
            ESRSLedgerItem(id="2", esrs_id="E1-5", data_point="b", impact_materiality="not_material",
                           financial_materiality="not_material", status="missing",
                           evidence_source="management_report", registry_evidence="x"),
            ESRSLedgerItem(id="3", esrs_id="E1-6", data_point="c", impact_materiality="not_material",
                           financial_materiality="not_material", status="non_compliant",
                           evidence_source="management_report", registry_evidence="x"),
        ]
        cost = _compute_compliance_cost(ledger, 250_000_000)
        # 3/3 * 250M * 0.05 = 12,500,000
        assert cost.projected_fine_eur == 12_500_000.0

    def test_basis_references_art_51(self):
        ledger = [
            ESRSLedgerItem(id="1", esrs_id="E1-1", data_point="a", impact_materiality="high",
                           financial_materiality="high", status="disclosed",
                           evidence_source="management_report", registry_evidence="x"),
        ]
        cost = _compute_compliance_cost(ledger, 250_000_000)
        assert "Art. 51" in cost.basis


# ═══════════════════════════════════════════════════════════════════════════
# J. Deterministic Ledger Builder
# ═══════════════════════════════════════════════════════════════════════════

class TestBuildLedgerDeterministic:
    """Verify deterministic ledger building against stub data."""

    def test_produces_three_items(self):
        ledger = _build_ledger_deterministic(STUB_ESRS_CLAIMS, STUB_TAXONOMY_FINANCIALS)
        assert len(ledger) == 3

    def test_all_items_are_esrs_ledger_items(self):
        ledger = _build_ledger_deterministic(STUB_ESRS_CLAIMS, STUB_TAXONOMY_FINANCIALS)
        assert all(isinstance(item, ESRSLedgerItem) for item in ledger)

    def test_esrs_ids_are_correct(self):
        ledger = _build_ledger_deterministic(STUB_ESRS_CLAIMS, STUB_TAXONOMY_FINANCIALS)
        ids = [item.esrs_id for item in ledger]
        assert ids == ["E1-1", "E1-5", "E1-6"]

    def test_impact_materiality_is_valid(self):
        ledger = _build_ledger_deterministic(STUB_ESRS_CLAIMS, STUB_TAXONOMY_FINANCIALS)
        valid = {"high", "medium", "low", "not_material"}
        assert all(item.impact_materiality in valid for item in ledger)

    def test_financial_materiality_is_valid(self):
        ledger = _build_ledger_deterministic(STUB_ESRS_CLAIMS, STUB_TAXONOMY_FINANCIALS)
        valid = {"high", "medium", "low", "not_material"}
        assert all(item.financial_materiality in valid for item in ledger)

    def test_status_is_valid(self):
        ledger = _build_ledger_deterministic(STUB_ESRS_CLAIMS, STUB_TAXONOMY_FINANCIALS)
        valid = {"disclosed", "partial", "missing", "non_compliant"}
        assert all(item.status in valid for item in ledger)

    def test_evidence_source_is_management_report(self):
        ledger = _build_ledger_deterministic(STUB_ESRS_CLAIMS, STUB_TAXONOMY_FINANCIALS)
        assert all(item.evidence_source == "management_report" for item in ledger)

    def test_registry_evidence_populated(self):
        ledger = _build_ledger_deterministic(STUB_ESRS_CLAIMS, STUB_TAXONOMY_FINANCIALS)
        assert all(len(item.registry_evidence) > 0 for item in ledger)

    def test_each_item_has_unique_id(self):
        ledger = _build_ledger_deterministic(STUB_ESRS_CLAIMS, STUB_TAXONOMY_FINANCIALS)
        ids = [item.id for item in ledger]
        assert len(set(ids)) == 3

    def test_stub_financial_materiality_is_medium(self):
        """Stub TaxonomyFinancials: 35% green → financial_score=60 → 'medium'."""
        ledger = _build_ledger_deterministic(STUB_ESRS_CLAIMS, STUB_TAXONOMY_FINANCIALS)
        # All items share the same financial materiality (computed once)
        assert all(item.financial_materiality == "medium" for item in ledger)

    def test_empty_claims_produce_missing_items(self):
        ledger = _build_ledger_deterministic({}, STUB_TAXONOMY_FINANCIALS)
        assert len(ledger) == 3
        assert all(item.status == "missing" for item in ledger)

    def test_null_taxonomy_still_produces_ledger(self):
        ledger = _build_ledger_deterministic(STUB_ESRS_CLAIMS, None)
        assert len(ledger) == 3


# ═══════════════════════════════════════════════════════════════════════════
# K. LLM Ledger Builder
# ═══════════════════════════════════════════════════════════════════════════

class TestBuildLedgerFromLLM:
    """Verify ledger construction from Claude's parsed JSON."""

    def test_builds_three_items_from_mock(self):
        ledger = _build_ledger_from_llm(MOCK_AUDITOR_RESPONSE_JSON, 60)
        assert len(ledger) == 3

    def test_preserves_esrs_ids(self):
        ledger = _build_ledger_from_llm(MOCK_AUDITOR_RESPONSE_JSON, 60)
        ids = [item.esrs_id for item in ledger]
        assert ids == ["E1-1", "E1-5", "E1-6"]

    def test_all_items_are_esrs_ledger_items(self):
        ledger = _build_ledger_from_llm(MOCK_AUDITOR_RESPONSE_JSON, 60)
        assert all(isinstance(item, ESRSLedgerItem) for item in ledger)

    def test_empty_response_returns_empty_list(self):
        ledger = _build_ledger_from_llm({"esrs_ledger": []}, 60)
        assert len(ledger) == 0

    def test_missing_key_returns_empty_list(self):
        ledger = _build_ledger_from_llm({}, 60)
        assert len(ledger) == 0


# ═══════════════════════════════════════════════════════════════════════════
# L. Compliance Check — Coverage Builder
# ═══════════════════════════════════════════════════════════════════════════

class TestBuildCoverageDeterministic:
    """Verify deterministic coverage assessment for compliance check mode."""

    def test_produces_three_items(self):
        coverage = _build_coverage_deterministic(STUB_COMPLIANCE_ESRS_CLAIMS)
        assert len(coverage) == 3

    def test_esrs_ids_correct(self):
        coverage = _build_coverage_deterministic(STUB_COMPLIANCE_ESRS_CLAIMS)
        ids = [c["esrs_id"] for c in coverage]
        assert ids == ["E1-1", "E1-5", "E1-6"]

    def test_coverage_values_valid(self):
        coverage = _build_coverage_deterministic(STUB_COMPLIANCE_ESRS_CLAIMS)
        valid = {"covered", "partial", "not_covered"}
        assert all(c["coverage"] in valid for c in coverage)

    def test_stub_claims_coverage(self):
        """E1-1 confidence=0.5 → partial; E1-5/E1-6 confidence=0.0 → not_covered."""
        coverage = _build_coverage_deterministic(STUB_COMPLIANCE_ESRS_CLAIMS)
        cov_map = {c["esrs_id"]: c["coverage"] for c in coverage}
        assert cov_map["E1-1"] == "partial"
        assert cov_map["E1-5"] == "not_covered"
        assert cov_map["E1-6"] == "not_covered"

    def test_high_confidence_covered(self):
        claims = {
            "E1-1": ESRSClaim(standard="E1-1", data_point="Test", disclosed_value="Net-zero 2040", confidence=0.8),
            "E1-5": ESRSClaim(standard="E1-5", data_point="Test", disclosed_value="45000 MWh", confidence=0.9),
            "E1-6": ESRSClaim(standard="E1-6", data_point="Test", disclosed_value="Scope 1: 1200", confidence=0.75),
        }
        coverage = _build_coverage_deterministic(claims)
        assert all(c["coverage"] == "covered" for c in coverage)

    def test_empty_claims(self):
        coverage = _build_coverage_deterministic({})
        assert len(coverage) == 3
        assert all(c["coverage"] == "not_covered" for c in coverage)


# ═══════════════════════════════════════════════════════════════════════════
# M. Compliance Check — Cost Estimate
# ═══════════════════════════════════════════════════════════════════════════

class TestComputeCostEstimate:
    """Verify compliance cost estimate range calculation."""

    def test_stub_coverage_cost_range(self):
        """E1-1 partial, E1-5/E1-6 not_covered → severity = (2*1.0 + 1*0.5)/3 = 0.833..."""
        coverage = _build_coverage_deterministic(STUB_COMPLIANCE_ESRS_CLAIMS)
        est = _compute_cost_estimate(coverage)
        severity = (2 * 1.0 + 1 * 0.5) / 3
        expected_low = round(500_000 * severity * 2.0, 2)
        expected_high = round(2_000_000 * severity * 2.0, 2)
        assert est["estimated_range_low_eur"] == pytest.approx(expected_low, abs=0.01)
        assert est["estimated_range_high_eur"] == pytest.approx(expected_high, abs=0.01)

    def test_low_less_than_high(self):
        coverage = _build_coverage_deterministic(STUB_COMPLIANCE_ESRS_CLAIMS)
        est = _compute_cost_estimate(coverage)
        assert est["estimated_range_low_eur"] <= est["estimated_range_high_eur"]

    def test_all_covered_zero_cost(self):
        coverage = [
            {"esrs_id": "E1-1", "coverage": "covered", "standard_name": "a", "details": "x"},
            {"esrs_id": "E1-5", "coverage": "covered", "standard_name": "b", "details": "x"},
            {"esrs_id": "E1-6", "coverage": "covered", "standard_name": "c", "details": "x"},
        ]
        est = _compute_cost_estimate(coverage)
        assert est["estimated_range_low_eur"] == 0.0
        assert est["estimated_range_high_eur"] == 0.0

    def test_has_caveat(self):
        coverage = _build_coverage_deterministic(STUB_COMPLIANCE_ESRS_CLAIMS)
        est = _compute_cost_estimate(coverage)
        assert "incomplete" in est["caveat"].lower() or "unstructured" in est["caveat"].lower()

    def test_has_basis(self):
        coverage = _build_coverage_deterministic(STUB_COMPLIANCE_ESRS_CLAIMS)
        est = _compute_cost_estimate(coverage)
        assert "Art. 51" in est["basis"]


# ═══════════════════════════════════════════════════════════════════════════
# N. Full Audit — Claude API Call Construction
# ═══════════════════════════════════════════════════════════════════════════

class TestClaudeAPICallFullAudit:
    """Verify auditor builds and sends correct Claude API request (full audit)."""

    def test_calls_correct_model(self, auditor_full_audit_state, mock_anthropic_client):
        auditor_node(auditor_full_audit_state)
        call_kwargs = mock_anthropic_client.messages.create.call_args
        assert call_kwargs.kwargs["model"] == "claude-sonnet-4-6"

    def test_uses_auditor_system_prompt(self, auditor_full_audit_state, mock_anthropic_client):
        auditor_node(auditor_full_audit_state)
        call_kwargs = mock_anthropic_client.messages.create.call_args
        assert call_kwargs.kwargs["system"] == SYSTEM_PROMPT_AUDITOR

    def test_sends_esrs_claims_in_message(self, auditor_full_audit_state, mock_anthropic_client):
        auditor_node(auditor_full_audit_state)
        call_kwargs = mock_anthropic_client.messages.create.call_args
        messages = call_kwargs.kwargs["messages"]
        content_blocks = messages[0]["content"]
        found = any("ESRS Claims" in block.get("text", "") for block in content_blocks)
        assert found, "ESRS claims should appear in message content"

    def test_sends_taxonomy_financials_in_message(self, auditor_full_audit_state, mock_anthropic_client):
        auditor_node(auditor_full_audit_state)
        call_kwargs = mock_anthropic_client.messages.create.call_args
        messages = call_kwargs.kwargs["messages"]
        content_blocks = messages[0]["content"]
        found = any("Taxonomy Financials" in block.get("text", "") for block in content_blocks)
        assert found, "Taxonomy financials should appear in message content"

    def test_prompt_caching_enabled(self, auditor_full_audit_state, mock_anthropic_client):
        auditor_node(auditor_full_audit_state)
        call_kwargs = mock_anthropic_client.messages.create.call_args
        content_blocks = call_kwargs.kwargs["messages"][0]["content"]
        cache_blocks = [b for b in content_blocks if b.get("cache_control") == {"type": "ephemeral"}]
        assert len(cache_blocks) == 1

    def test_max_tokens_set(self, auditor_full_audit_state, mock_anthropic_client):
        auditor_node(auditor_full_audit_state)
        call_kwargs = mock_anthropic_client.messages.create.call_args
        assert call_kwargs.kwargs["max_tokens"] == MAX_TOKENS

    def test_api_called_exactly_once(self, auditor_full_audit_state, mock_anthropic_client):
        auditor_node(auditor_full_audit_state)
        assert mock_anthropic_client.messages.create.call_count == 1


# ═══════════════════════════════════════════════════════════════════════════
# O. Full Audit — Output Validation (with LLM mock)
# ═══════════════════════════════════════════════════════════════════════════

class TestFullAuditOutputWithLLM:
    """Verify full audit output when Claude responds successfully."""

    def test_returns_esrs_ledger(self, auditor_full_audit_state, mock_anthropic_client):
        result = auditor_node(auditor_full_audit_state)
        assert "esrs_ledger" in result
        assert len(result["esrs_ledger"]) == 3

    def test_all_ledger_items_are_pydantic(self, auditor_full_audit_state, mock_anthropic_client):
        result = auditor_node(auditor_full_audit_state)
        assert all(isinstance(item, ESRSLedgerItem) for item in result["esrs_ledger"])

    def test_returns_taxonomy_alignment(self, auditor_full_audit_state, mock_anthropic_client):
        result = auditor_node(auditor_full_audit_state)
        assert "taxonomy_alignment" in result
        ta = result["taxonomy_alignment"]
        assert isinstance(ta, TaxonomyAlignment)
        assert ta.capex_aligned_pct == 35.0
        assert ta.status == "partially_aligned"

    def test_returns_compliance_cost(self, auditor_full_audit_state, mock_anthropic_client):
        result = auditor_node(auditor_full_audit_state)
        assert "compliance_cost" in result
        assert isinstance(result["compliance_cost"], ComplianceCost)

    def test_returns_taxonomy_alignment_score(self, auditor_full_audit_state, mock_anthropic_client):
        result = auditor_node(auditor_full_audit_state)
        assert "taxonomy_alignment_score" in result
        assert result["taxonomy_alignment_score"] == 35.0

    def test_does_not_return_compliance_check_keys(self, auditor_full_audit_state, mock_anthropic_client):
        result = auditor_node(auditor_full_audit_state)
        assert "esrs_coverage" not in result
        assert "compliance_cost_estimate" not in result


# ═══════════════════════════════════════════════════════════════════════════
# P. Full Audit — Error Handling / Fallback
# ═══════════════════════════════════════════════════════════════════════════

class TestFullAuditFallback:
    """Verify graceful fallback to deterministic scoring on Claude failures."""

    def test_api_error_falls_back(self, auditor_full_audit_state, mock_anthropic_client):
        mock_anthropic_client.messages.create.side_effect = Exception("API down")
        result = auditor_node(auditor_full_audit_state)
        assert len(result["esrs_ledger"]) == 3
        assert all(isinstance(item, ESRSLedgerItem) for item in result["esrs_ledger"])

    def test_api_error_logs_error(self, auditor_full_audit_state, mock_anthropic_client):
        mock_anthropic_client.messages.create.side_effect = Exception("API down")
        result = auditor_node(auditor_full_audit_state)
        error_logs = [l for l in result["logs"] if "Error" in l.get("msg", "")]
        assert len(error_logs) >= 1

    def test_malformed_json_falls_back(self, auditor_full_audit_state, mock_anthropic_client):
        mock_anthropic_client.messages.create.return_value = _make_mock_claude_response("not valid json")
        result = auditor_node(auditor_full_audit_state)
        assert len(result["esrs_ledger"]) == 3

    def test_wrong_item_count_falls_back(self, auditor_full_audit_state, mock_anthropic_client):
        """If Claude returns != 3 ledger items, fall back to deterministic."""
        bad_response = {"esrs_ledger": [{"esrs_id": "E1-1", "data_point": "x", "status": "partial"}]}
        mock_anthropic_client.messages.create.return_value = _make_mock_claude_response(json.dumps(bad_response))
        result = auditor_node(auditor_full_audit_state)
        assert len(result["esrs_ledger"]) == 3

    def test_fallback_taxonomy_alignment_still_correct(self, auditor_full_audit_state, mock_anthropic_client):
        mock_anthropic_client.messages.create.side_effect = Exception("API down")
        result = auditor_node(auditor_full_audit_state)
        # Taxonomy alignment is always computed deterministically
        assert result["taxonomy_alignment"].capex_aligned_pct == 35.0
        assert result["taxonomy_alignment"].status == "partially_aligned"


# ═══════════════════════════════════════════════════════════════════════════
# Q. Compliance Check — Claude API Call
# ═══════════════════════════════════════════════════════════════════════════

class TestClaudeAPICallComplianceCheck:
    """Verify auditor builds correct Claude request for compliance check."""

    def test_uses_auditor_lite_prompt(self, auditor_compliance_state):
        with patch("agents.auditor.Anthropic") as MockClass:
            mock_client = MagicMock()
            MockClass.return_value = mock_client
            mock_client.messages.create.return_value = _make_mock_claude_response(
                json.dumps(MOCK_AUDITOR_LITE_RESPONSE_JSON)
            )
            auditor_node(auditor_compliance_state)
            call_kwargs = mock_client.messages.create.call_args
            assert call_kwargs.kwargs["system"] == SYSTEM_PROMPT_AUDITOR_LITE

    def test_sends_extracted_goals(self, auditor_compliance_state):
        with patch("agents.auditor.Anthropic") as MockClass:
            mock_client = MagicMock()
            MockClass.return_value = mock_client
            mock_client.messages.create.return_value = _make_mock_claude_response(
                json.dumps(MOCK_AUDITOR_LITE_RESPONSE_JSON)
            )
            auditor_node(auditor_compliance_state)
            call_kwargs = mock_client.messages.create.call_args
            content_blocks = call_kwargs.kwargs["messages"][0]["content"]
            found = any("Extracted Goals" in block.get("text", "") for block in content_blocks)
            assert found


# ═══════════════════════════════════════════════════════════════════════════
# R. Compliance Check — Output Validation
# ═══════════════════════════════════════════════════════════════════════════

class TestComplianceCheckOutput:
    """Verify compliance check output (with LLM mock)."""

    def _run_with_mock(self, state):
        with patch("agents.auditor.Anthropic") as MockClass:
            mock_client = MagicMock()
            MockClass.return_value = mock_client
            mock_client.messages.create.return_value = _make_mock_claude_response(
                json.dumps(MOCK_AUDITOR_LITE_RESPONSE_JSON)
            )
            return auditor_node(state)

    def test_returns_esrs_coverage(self, auditor_compliance_state):
        result = self._run_with_mock(auditor_compliance_state)
        assert "esrs_coverage" in result
        assert len(result["esrs_coverage"]) == 3

    def test_coverage_values_valid(self, auditor_compliance_state):
        result = self._run_with_mock(auditor_compliance_state)
        valid = {"covered", "partial", "not_covered"}
        assert all(c["coverage"] in valid for c in result["esrs_coverage"])

    def test_returns_cost_estimate(self, auditor_compliance_state):
        result = self._run_with_mock(auditor_compliance_state)
        assert "compliance_cost_estimate" in result
        est = result["compliance_cost_estimate"]
        assert "estimated_range_low_eur" in est
        assert "estimated_range_high_eur" in est
        assert est["estimated_range_low_eur"] <= est["estimated_range_high_eur"]

    def test_does_not_return_full_audit_keys(self, auditor_compliance_state):
        result = self._run_with_mock(auditor_compliance_state)
        assert "esrs_ledger" not in result
        assert "taxonomy_alignment" not in result
        assert "taxonomy_alignment_score" not in result

    def test_cost_estimate_has_caveat(self, auditor_compliance_state):
        result = self._run_with_mock(auditor_compliance_state)
        caveat = result["compliance_cost_estimate"]["caveat"]
        assert "incomplete" in caveat.lower() or "unstructured" in caveat.lower()


# ═══════════════════════════════════════════════════════════════════════════
# S. Compliance Check — Fallback
# ═══════════════════════════════════════════════════════════════════════════

class TestComplianceCheckFallback:
    """Verify compliance check falls back to deterministic on API failure."""

    def test_api_error_produces_coverage(self, auditor_compliance_state):
        with patch("agents.auditor.Anthropic") as MockClass:
            mock_client = MagicMock()
            MockClass.return_value = mock_client
            mock_client.messages.create.side_effect = Exception("API down")
            result = auditor_node(auditor_compliance_state)
            assert len(result["esrs_coverage"]) == 3

    def test_api_error_produces_cost_estimate(self, auditor_compliance_state):
        with patch("agents.auditor.Anthropic") as MockClass:
            mock_client = MagicMock()
            MockClass.return_value = mock_client
            mock_client.messages.create.side_effect = Exception("API down")
            result = auditor_node(auditor_compliance_state)
            assert "estimated_range_low_eur" in result["compliance_cost_estimate"]


# ═══════════════════════════════════════════════════════════════════════════
# T. State Management
# ═══════════════════════════════════════════════════════════════════════════

class TestStateManagement:
    """Verify state keys are correctly read and written."""

    def test_logs_accumulated_full_audit(self, auditor_full_audit_state, mock_anthropic_client):
        auditor_full_audit_state["logs"] = [{"agent": "extractor", "msg": "prior", "ts": 0}]
        result = auditor_node(auditor_full_audit_state)
        assert result["logs"][0]["msg"] == "prior"
        auditor_logs = [l for l in result["logs"] if l["agent"] == "auditor"]
        assert len(auditor_logs) >= 3

    def test_pipeline_trace_includes_auditor(self, auditor_full_audit_state, mock_anthropic_client):
        result = auditor_node(auditor_full_audit_state)
        traces = [t for t in result["pipeline_trace"] if t["agent"] == "auditor"]
        assert len(traces) == 1
        assert "ms" in traces[0]
        assert "started_at" in traces[0]

    def test_does_not_modify_input_keys(self, auditor_full_audit_state, mock_anthropic_client):
        original_audit_id = auditor_full_audit_state["audit_id"]
        result = auditor_node(auditor_full_audit_state)
        assert "audit_id" not in result
        assert auditor_full_audit_state["audit_id"] == original_audit_id

    def test_compliance_check_logs(self, auditor_compliance_state):
        with patch("agents.auditor.Anthropic") as MockClass:
            mock_client = MagicMock()
            MockClass.return_value = mock_client
            mock_client.messages.create.side_effect = Exception("API down")
            result = auditor_node(auditor_compliance_state)
            auditor_logs = [l for l in result["logs"] if l["agent"] == "auditor"]
            assert len(auditor_logs) >= 3


# ═══════════════════════════════════════════════════════════════════════════
# U. PRD Gate — Iteration 7
# ═══════════════════════════════════════════════════════════════════════════

class TestPRDGate:
    """PRD Gate: esrs_ledger contains 3 valid ESRSLedgerItem objects (both modes)."""

    def test_gate_full_audit_ledger_has_three_items(self, auditor_full_audit_state, mock_anthropic_client):
        result = auditor_node(auditor_full_audit_state)
        assert len(result["esrs_ledger"]) == 3

    def test_gate_full_audit_ledger_items_valid(self, auditor_full_audit_state, mock_anthropic_client):
        result = auditor_node(auditor_full_audit_state)
        for item in result["esrs_ledger"]:
            assert isinstance(item, ESRSLedgerItem)
            assert item.id
            assert item.esrs_id in ("E1-1", "E1-5", "E1-6")
            assert item.data_point
            assert item.impact_materiality in ("high", "medium", "low", "not_material")
            assert item.financial_materiality in ("high", "medium", "low", "not_material")
            assert item.status in ("disclosed", "partial", "missing", "non_compliant")
            assert item.evidence_source in ("management_report", "taxonomy_table", "transition_plan")
            assert item.registry_evidence

    def test_gate_full_audit_taxonomy_alignment_valid(self, auditor_full_audit_state, mock_anthropic_client):
        result = auditor_node(auditor_full_audit_state)
        ta = result["taxonomy_alignment"]
        assert isinstance(ta, TaxonomyAlignment)
        assert 0 <= ta.capex_aligned_pct <= 100
        assert ta.status in ("aligned", "partially_aligned", "non_compliant")

    def test_gate_full_audit_compliance_cost_valid(self, auditor_full_audit_state, mock_anthropic_client):
        result = auditor_node(auditor_full_audit_state)
        cc = result["compliance_cost"]
        assert isinstance(cc, ComplianceCost)
        assert cc.projected_fine_eur >= 0
        assert "Art. 51" in cc.basis

    def test_gate_compliance_check_coverage_has_three_items(self, auditor_compliance_state):
        with patch("agents.auditor.Anthropic") as MockClass:
            mock_client = MagicMock()
            MockClass.return_value = mock_client
            mock_client.messages.create.return_value = _make_mock_claude_response(
                json.dumps(MOCK_AUDITOR_LITE_RESPONSE_JSON)
            )
            result = auditor_node(auditor_compliance_state)
            assert len(result["esrs_coverage"]) == 3

    def test_gate_compliance_check_cost_estimate_valid(self, auditor_compliance_state):
        with patch("agents.auditor.Anthropic") as MockClass:
            mock_client = MagicMock()
            MockClass.return_value = mock_client
            mock_client.messages.create.return_value = _make_mock_claude_response(
                json.dumps(MOCK_AUDITOR_LITE_RESPONSE_JSON)
            )
            result = auditor_node(auditor_compliance_state)
            est = result["compliance_cost_estimate"]
            assert est["estimated_range_low_eur"] >= 0
            assert est["estimated_range_high_eur"] >= est["estimated_range_low_eur"]
            assert "basis" in est
            assert "caveat" in est

    def test_gate_deterministic_fallback_full_audit(self, auditor_full_audit_state, mock_anthropic_client):
        """Gate still passes when Claude is unavailable (deterministic fallback)."""
        mock_anthropic_client.messages.create.side_effect = Exception("No API")
        result = auditor_node(auditor_full_audit_state)
        assert len(result["esrs_ledger"]) == 3
        assert isinstance(result["taxonomy_alignment"], TaxonomyAlignment)
        assert isinstance(result["compliance_cost"], ComplianceCost)
        assert result["taxonomy_alignment_score"] == 35.0

    def test_gate_deterministic_fallback_compliance_check(self, auditor_compliance_state):
        """Gate still passes when Claude is unavailable (deterministic fallback)."""
        with patch("agents.auditor.Anthropic") as MockClass:
            mock_client = MagicMock()
            MockClass.return_value = mock_client
            mock_client.messages.create.side_effect = Exception("No API")
            result = auditor_node(auditor_compliance_state)
            assert len(result["esrs_coverage"]) == 3
            assert "estimated_range_low_eur" in result["compliance_cost_estimate"]


# ═══════════════════════════════════════════════════════════════════════════
# V. End-to-End Graph Integration (with stub extractor + fetcher)
# ═══════════════════════════════════════════════════════════════════════════

class TestGraphIntegration:
    """Verify auditor integrates correctly into the LangGraph pipeline."""

    def test_full_audit_graph_with_real_auditor(self):
        """v5.0 structured pipeline runs end-to-end (extractor→scorer→advisor)."""
        from graph import graph
        from schemas import ComplianceResult, CompanyInputs

        state = {
            "audit_id": "graph-test-full",
            "mode": "structured_document",
            "report_json": {"report_info": {}, "facts": []},
            "esrs_data": {"facts": []},
            "taxonomy_data": {"facts": []},
            "entity_id": "GraphTestCorp",
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

        assert "final_result" in result
        fr = result["final_result"]
        assert isinstance(fr, ComplianceResult)
        assert fr.schema_version == "3.0"

    def test_compliance_check_graph_with_real_auditor(self):
        """v5.0 free_text pipeline runs end-to-end (extractor→scorer→advisor)."""
        from graph import graph
        from schemas import ComplianceResult, CompanyInputs

        state = {
            "audit_id": "graph-test-compliance",
            "mode": "free_text",
            "free_text_input": "We target net-zero by 2040.",
            "entity_id": "GraphTestCorp",
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

        assert "final_result" in result
        fr = result["final_result"]
        assert isinstance(fr, ComplianceResult)
        assert fr.schema_version == "3.0"
