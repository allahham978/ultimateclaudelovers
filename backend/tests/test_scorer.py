"""
Tests for backend/agents/scorer.py — Iteration 9.

Covers:
  - Scoring algorithm with knowledge-base-driven requirements
  - Edge cases: 0 applicable, all disclosed, all missing, mixed
  - ComplianceScore validation
  - Coverage gaps correctness
  - Score formula: (disclosed + partial*0.5) / total * 100
"""

import sys
import os

_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

import pytest
from schemas import CompanyInputs, ComplianceScore, ESRSClaim
from agents.scorer import scorer_node, _classify_claim
from tools.knowledge_base import get_applicable_requirements


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(
    esrs_claims: dict[str, ESRSClaim],
    company_inputs: CompanyInputs,
    mode: str = "structured_document",
) -> dict:
    """Build a minimal AuditState for scorer testing."""
    return {
        "audit_id": "test-scorer-001",
        "mode": mode,
        "esrs_claims": esrs_claims,
        "company_inputs": company_inputs,
        "logs": [],
        "pipeline_trace": [],
    }


LARGE_PIE_INPUTS = CompanyInputs(
    number_of_employees=600,
    revenue_eur=80_000_000,
    total_assets_eur=40_000_000,
    reporting_year=2024,
)

LARGE_INPUTS = CompanyInputs(
    number_of_employees=300,
    revenue_eur=50_000_000,
    total_assets_eur=15_000_000,  # below €20M so only emp+rev = 1 Phase1 criteria → Phase 2
    reporting_year=2025,
)

SME_INPUTS = CompanyInputs(
    number_of_employees=50,
    revenue_eur=5_000_000,
    total_assets_eur=2_000_000,
    reporting_year=2026,
)


# ---------------------------------------------------------------------------
# _classify_claim()
# ---------------------------------------------------------------------------


class TestClassifyClaim:
    """Unit tests for the claim classification function."""

    def test_disclosed_high_confidence_with_value(self):
        claim = ESRSClaim(standard="E1-1", data_point="test", disclosed_value="Net-zero", confidence=0.85)
        assert _classify_claim(claim) == "disclosed"

    def test_disclosed_at_threshold(self):
        claim = ESRSClaim(standard="E1-1", data_point="test", disclosed_value="Data", confidence=0.7)
        assert _classify_claim(claim) == "disclosed"

    def test_partial_mid_confidence(self):
        claim = ESRSClaim(standard="E1-1", data_point="test", disclosed_value="Partial", confidence=0.5)
        assert _classify_claim(claim) == "partial"

    def test_partial_at_lower_threshold(self):
        claim = ESRSClaim(standard="E1-1", data_point="test", disclosed_value="Partial", confidence=0.3)
        assert _classify_claim(claim) == "partial"

    def test_missing_low_confidence(self):
        claim = ESRSClaim(standard="E1-1", data_point="test", disclosed_value=None, confidence=0.1)
        assert _classify_claim(claim) == "missing"

    def test_missing_zero_confidence(self):
        claim = ESRSClaim(standard="E1-1", data_point="test", disclosed_value=None, confidence=0.0)
        assert _classify_claim(claim) == "missing"

    def test_missing_high_confidence_but_no_value(self):
        """High confidence but no disclosed value → missing (need both)."""
        claim = ESRSClaim(standard="E1-1", data_point="test", disclosed_value=None, confidence=0.9)
        assert _classify_claim(claim) == "missing"

    def test_missing_below_partial_threshold(self):
        claim = ESRSClaim(standard="E1-1", data_point="test", disclosed_value="Data", confidence=0.29)
        assert _classify_claim(claim) == "missing"


# ---------------------------------------------------------------------------
# scorer_node() — full integration
# ---------------------------------------------------------------------------


class TestScorerNode:
    """Integration tests for the scorer node with knowledge base."""

    def test_produces_compliance_score(self):
        """Scorer should always produce a valid ComplianceScore."""
        state = _make_state({}, LARGE_PIE_INPUTS)
        result = scorer_node(state)
        assert "compliance_score" in result
        score = result["compliance_score"]
        assert isinstance(score, ComplianceScore)
        assert 0 <= score.overall <= 100

    def test_produces_applicable_reqs(self):
        state = _make_state({}, LARGE_PIE_INPUTS)
        result = scorer_node(state)
        assert "applicable_reqs" in result
        assert isinstance(result["applicable_reqs"], list)

    def test_produces_coverage_gaps(self):
        state = _make_state({}, LARGE_PIE_INPUTS)
        result = scorer_node(state)
        assert "coverage_gaps" in result
        assert isinstance(result["coverage_gaps"], list)

    def test_produces_logs(self):
        state = _make_state({}, LARGE_PIE_INPUTS)
        result = scorer_node(state)
        assert "logs" in result
        assert len(result["logs"]) > 0

    def test_produces_pipeline_trace(self):
        state = _make_state({}, LARGE_PIE_INPUTS)
        result = scorer_node(state)
        assert "pipeline_trace" in result
        scorer_entries = [t for t in result["pipeline_trace"] if t["agent"] == "scorer"]
        assert len(scorer_entries) == 1
        assert scorer_entries[0]["ms"] >= 0

    # -- Score formula tests --

    def test_all_missing_score_zero(self):
        """No claims at all → all requirements missing → score 0."""
        state = _make_state({}, LARGE_PIE_INPUTS)
        result = scorer_node(state)
        score = result["compliance_score"]
        assert score.overall == 0
        assert score.disclosed_count == 0
        assert score.partial_count == 0
        assert score.missing_count > 0

    def test_three_disclosed_claims(self):
        """3 disclosed claims out of many requirements → low but non-zero score."""
        claims = {
            "E1-1": ESRSClaim(standard="E1-1", data_point="Transition Plan", disclosed_value="Net-zero by 2040", confidence=0.85),
            "E1-5": ESRSClaim(standard="E1-5", data_point="Energy", disclosed_value="45000 MWh", confidence=0.90),
            "E1-6": ESRSClaim(standard="E1-6", data_point="GHG", disclosed_value="1200 tCO2", confidence=0.80),
        }
        state = _make_state(claims, LARGE_PIE_INPUTS)
        result = scorer_node(state)
        score = result["compliance_score"]
        assert score.overall > 0
        assert score.overall < 50  # 3 out of 70+ requirements
        assert score.disclosed_count == 3

    def test_mixed_claims(self):
        """Mix of disclosed, partial, and claims that don't cover all requirements."""
        claims = {
            "E1-1": ESRSClaim(standard="E1-1", data_point="Transition Plan", disclosed_value="Plan", confidence=0.85),
            "E1-5": ESRSClaim(standard="E1-5", data_point="Energy", disclosed_value="Partial", confidence=0.5),
            "E1-6": ESRSClaim(standard="E1-6", data_point="GHG", disclosed_value=None, confidence=0.1),
        }
        state = _make_state(claims, LARGE_PIE_INPUTS)
        result = scorer_node(state)
        score = result["compliance_score"]
        assert score.disclosed_count == 1
        assert score.partial_count == 1
        # E1-6 is missing + all uncovered requirements are missing
        assert score.missing_count >= 1

    def test_score_formula_exact(self):
        """Verify: overall = round(((disclosed + partial*0.5) / total) * 100)."""
        claims = {
            "E1-1": ESRSClaim(standard="E1-1", data_point="Transition Plan", disclosed_value="Plan", confidence=0.85),
            "E1-5": ESRSClaim(standard="E1-5", data_point="Energy", disclosed_value="Partial", confidence=0.5),
        }
        state = _make_state(claims, LARGE_PIE_INPUTS)
        result = scorer_node(state)
        score = result["compliance_score"]
        total = score.disclosed_count + score.partial_count + score.missing_count
        expected = round(((score.disclosed_count + score.partial_count * 0.5) / total) * 100)
        assert score.overall == expected

    # -- Size category tests --

    def test_large_pie_size_category(self):
        state = _make_state({}, LARGE_PIE_INPUTS)
        result = scorer_node(state)
        assert result["compliance_score"].size_category == "large_pie"

    def test_large_size_category(self):
        state = _make_state({}, LARGE_INPUTS)
        result = scorer_node(state)
        assert result["compliance_score"].size_category == "large"

    def test_sme_size_category(self):
        state = _make_state({}, SME_INPUTS)
        result = scorer_node(state)
        assert result["compliance_score"].size_category == "sme"

    # -- Coverage gaps tests --

    def test_coverage_gaps_match_applicable_count(self):
        """Number of coverage_gaps should equal number of applicable requirements."""
        state = _make_state({}, LARGE_PIE_INPUTS)
        result = scorer_node(state)
        assert len(result["coverage_gaps"]) == result["compliance_score"].applicable_standards_count

    def test_coverage_gaps_have_required_fields(self):
        state = _make_state({}, LARGE_PIE_INPUTS)
        result = scorer_node(state)
        for gap in result["coverage_gaps"]:
            assert "esrs_id" in gap
            assert "status" in gap
            assert gap["status"] in ("disclosed", "partial", "missing")
            assert "details" in gap

    def test_applicable_reqs_have_required_fields(self):
        state = _make_state({}, LARGE_PIE_INPUTS)
        result = scorer_node(state)
        for req in result["applicable_reqs"]:
            assert "esrs_id" in req
            assert "standard_name" in req
            assert "status" in req
            assert "confidence" in req
            assert "mandatory" in req or "mandatory_if_material" in req

    def test_uncovered_requirement_is_missing(self):
        """Requirements with no matching claim should be 'missing'."""
        # Provide only E1-1 claim, check that E1-2 through E1-9 are missing
        claims = {
            "E1-1": ESRSClaim(standard="E1-1", data_point="Transition Plan", disclosed_value="Plan", confidence=0.85),
        }
        state = _make_state(claims, LARGE_PIE_INPUTS)
        result = scorer_node(state)
        e1_gaps = [g for g in result["coverage_gaps"] if g["esrs_id"].startswith("E1-") and g["esrs_id"] != "E1-1"]
        assert len(e1_gaps) > 0
        assert all(g["status"] == "missing" for g in e1_gaps)

    # -- Edge cases --

    def test_no_company_inputs_defaults(self):
        """Missing company_inputs should use defaults (0 employees → sme)."""
        state = {
            "audit_id": "test-edge-001",
            "mode": "free_text",
            "esrs_claims": {},
            "logs": [],
            "pipeline_trace": [],
        }
        result = scorer_node(state)
        score = result["compliance_score"]
        assert score.size_category == "sme"
        assert score.overall == 0

    def test_sme_has_fewer_requirements_than_large(self):
        """SME should have fewer applicable requirements than large_pie."""
        large_state = _make_state({}, LARGE_PIE_INPUTS)
        sme_state = _make_state({}, SME_INPUTS)
        large_result = scorer_node(large_state)
        sme_result = scorer_node(sme_state)
        assert (
            sme_result["compliance_score"].applicable_standards_count
            < large_result["compliance_score"].applicable_standards_count
        )

    def test_free_text_mode_works(self):
        """Scorer should work in free_text mode."""
        claims = {
            "E1-1": ESRSClaim(standard="E1-1", data_point="Transition Plan", disclosed_value="Net-zero", confidence=0.5),
        }
        state = _make_state(claims, SME_INPUTS, mode="free_text")
        result = scorer_node(state)
        score = result["compliance_score"]
        assert isinstance(score, ComplianceScore)
        assert 0 <= score.overall <= 100

    def test_counts_are_consistent(self):
        """disclosed + partial + missing = applicable_standards_count."""
        claims = {
            "E1-1": ESRSClaim(standard="E1-1", data_point="Transition Plan", disclosed_value="Plan", confidence=0.85),
            "E1-5": ESRSClaim(standard="E1-5", data_point="Energy", disclosed_value="Data", confidence=0.5),
        }
        state = _make_state(claims, LARGE_PIE_INPUTS)
        result = scorer_node(state)
        score = result["compliance_score"]
        assert score.disclosed_count + score.partial_count + score.missing_count == score.applicable_standards_count
