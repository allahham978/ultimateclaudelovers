"""
Tests for backend/tools/knowledge_base.py — Iteration 9.

Covers:
  - load_requirements(): parsing + caching + validation
  - determine_size_category(): threshold matching for all size categories
  - get_applicable_requirements(): requirement filtering, phase-in logic, SME simplification
"""

import sys
import os

_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

import pytest
from tools.knowledge_base import (
    load_requirements,
    determine_size_category,
    get_applicable_requirements,
)
from data.schema import CSRDPhase, CSRDReportingRequirements


# ---------------------------------------------------------------------------
# load_requirements()
# ---------------------------------------------------------------------------


class TestLoadRequirements:
    """Tests for loading and validating master_requirements.json."""

    def test_returns_valid_model(self):
        kb = load_requirements()
        assert isinstance(kb, CSRDReportingRequirements)

    def test_schema_version(self):
        kb = load_requirements()
        assert kb.schema_version == "2.0"

    def test_has_documents(self):
        kb = load_requirements()
        assert len(kb.csrd_reporting_requirements) > 0

    def test_contains_all_esrs_standards(self):
        """KB must contain E1-E5, S1-S4, G1 topical documents."""
        kb = load_requirements()
        doc_ids = {doc.document_id for doc in kb.csrd_reporting_requirements}
        expected = {"E1-001", "E2-001", "E3-001", "E4-001", "E5-001",
                    "S1-001", "S2-001", "S3-001", "S4-001", "G1-001"}
        assert expected.issubset(doc_ids), f"Missing: {expected - doc_ids}"

    def test_contains_mandatory_documents(self):
        """KB must contain SR-001, TAX-001, GOV-001."""
        kb = load_requirements()
        doc_ids = {doc.document_id for doc in kb.csrd_reporting_requirements}
        assert {"SR-001", "TAX-001", "GOV-001"}.issubset(doc_ids)

    def test_all_documents_have_four_phases(self):
        """Every document must have company_applicability for all 4 phases."""
        kb = load_requirements()
        for doc in kb.csrd_reporting_requirements:
            phases = {app.csrd_phase for app in doc.company_applicability}
            assert phases == {1, 2, 3, 4}, (
                f"{doc.document_id} missing phases: {set(CSRDPhase) - phases}"
            )

    def test_caching(self):
        """load_requirements() should return the same cached instance."""
        kb1 = load_requirements()
        kb2 = load_requirements()
        assert kb1 is kb2

    def test_get_document_by_id(self):
        kb = load_requirements()
        doc = kb.get_document("E1-001")
        assert doc.document_id == "E1-001"
        assert "Climate" in doc.document_type

    def test_get_document_not_found(self):
        kb = load_requirements()
        with pytest.raises(KeyError):
            kb.get_document("NONEXISTENT-999")

    def test_mandatory_documents(self):
        kb = load_requirements()
        mandatory = kb.get_mandatory_documents()
        mandatory_ids = {d.document_id for d in mandatory}
        assert "SR-001" in mandatory_ids
        assert "TAX-001" in mandatory_ids
        assert "GOV-001" in mandatory_ids

    def test_material_dependent_documents(self):
        kb = load_requirements()
        material = kb.get_material_dependent_documents()
        material_ids = {d.document_id for d in material}
        assert "E1-001" in material_ids
        assert "S1-001" in material_ids
        assert "G1-001" in material_ids


# ---------------------------------------------------------------------------
# determine_size_category()
# ---------------------------------------------------------------------------


class TestDetermineSizeCategory:
    """Tests for CSRD phase/size classification."""

    def test_large_pie_phase1(self):
        """≥500 employees + ≥€40M revenue + ≥€20M assets → large_pie (Phase 1)."""
        result = determine_size_category(
            employees=600,
            revenue_eur=50_000_000,
            total_assets_eur=25_000_000,
        )
        assert result == "large_pie"

    def test_large_pie_two_of_three(self):
        """500 employees + €40M revenue (assets below threshold) → large_pie."""
        result = determine_size_category(
            employees=500,
            revenue_eur=40_000_000,
            total_assets_eur=10_000_000,  # below €20M
        )
        assert result == "large_pie"

    def test_large_phase2(self):
        """≥250 employees + 1 financial threshold met but NOT 2-of-3 for Phase 1 → large."""
        # 300 emp (< 500), €50M revenue (≥ 40M), €15M assets (< 20M)
        # Phase 1: emp NO, rev YES, assets NO → 1 < 2 → NOT Phase 1
        # Phase 2: emp YES (≥250), rev YES → 2 ≥ 2 → Phase 2
        result = determine_size_category(
            employees=300,
            revenue_eur=50_000_000,
            total_assets_eur=15_000_000,
        )
        assert result == "large"

    def test_large_phase2_employee_and_revenue(self):
        """250+ employees + revenue threshold met, low assets → large."""
        result = determine_size_category(
            employees=260,
            revenue_eur=45_000_000,
            total_assets_eur=10_000_000,
        )
        assert result == "large"

    def test_sme_below_all_thresholds(self):
        """Small company below all thresholds → sme."""
        result = determine_size_category(
            employees=50,
            revenue_eur=5_000_000,
            total_assets_eur=2_000_000,
        )
        assert result == "sme"

    def test_sme_one_threshold_only(self):
        """Meets only 1 of 3 criteria → sme (need 2-of-3 for large)."""
        result = determine_size_category(
            employees=300,
            revenue_eur=10_000_000,
            total_assets_eur=5_000_000,
        )
        assert result == "sme"

    def test_boundary_exactly_500(self):
        """Exactly 500 employees + €40M revenue → large_pie."""
        result = determine_size_category(
            employees=500,
            revenue_eur=40_000_000,
            total_assets_eur=20_000_000,
        )
        assert result == "large_pie"

    def test_boundary_exactly_250(self):
        """Exactly 250 employees + €40M revenue but low assets → large (Phase 2)."""
        # Phase 1: emp < 500, rev YES, assets NO → 1 < 2 → NOT Phase 1
        # Phase 2: emp YES (≥250), rev YES → 2 ≥ 2 → Phase 2
        result = determine_size_category(
            employees=250,
            revenue_eur=40_000_000,
            total_assets_eur=10_000_000,
        )
        assert result == "large"

    def test_249_employees_with_both_financial(self):
        """249 employees with high revenue and assets → large_pie (rev+assets = 2-of-3 for Phase 1)."""
        # Phase 1: emp NO, rev YES, assets YES → 2 ≥ 2 → Phase 1!
        result = determine_size_category(
            employees=249,
            revenue_eur=50_000_000,
            total_assets_eur=25_000_000,
        )
        assert result == "large_pie"

    def test_249_employees_one_financial(self):
        """249 employees + revenue only → sme (only 1-of-3 for both phases)."""
        # Phase 1: emp NO, rev YES, assets NO → 1 < 2 → NOT Phase 1
        # Phase 2: emp NO (249 < 250), rev YES, assets NO → 1 < 2 → NOT Phase 2
        result = determine_size_category(
            employees=249,
            revenue_eur=50_000_000,
            total_assets_eur=10_000_000,
        )
        assert result == "sme"

    def test_zero_employees(self):
        """Edge case: 0 employees, 0 revenue → sme."""
        result = determine_size_category(
            employees=0,
            revenue_eur=0,
            total_assets_eur=0,
        )
        assert result == "sme"

    def test_prd_example_large_pie(self):
        """PRD example: 500 employees, €85M revenue, €42M assets → large_pie."""
        result = determine_size_category(
            employees=500,
            revenue_eur=85_000_000,
            total_assets_eur=42_000_000,
        )
        assert result == "large_pie"

    def test_prd_example_small(self):
        """PRD example: 50 employees, €5M revenue, €2M assets → sme."""
        result = determine_size_category(
            employees=50,
            revenue_eur=5_000_000,
            total_assets_eur=2_000_000,
        )
        assert result == "sme"


# ---------------------------------------------------------------------------
# get_applicable_requirements()
# ---------------------------------------------------------------------------


class TestGetApplicableRequirements:
    """Tests for requirement filtering by size category and reporting year."""

    def test_large_pie_returns_requirements(self):
        """Phase 1 large PIE should get full disclosure requirements."""
        reqs = get_applicable_requirements("large_pie", 2024)
        assert len(reqs) > 0

    def test_large_returns_requirements(self):
        """Phase 2 large company should get full disclosure requirements."""
        reqs = get_applicable_requirements("large", 2025)
        assert len(reqs) > 0

    def test_sme_returns_requirements(self):
        """Phase 3 SME should get requirements (may be simplified)."""
        reqs = get_applicable_requirements("sme", 2026)
        assert len(reqs) > 0

    def test_large_pie_has_e1_disclosures(self):
        """Phase 1 should include E1 climate change disclosures."""
        reqs = get_applicable_requirements("large_pie", 2024)
        e1_ids = [r["disclosure_id"] for r in reqs if r["document_id"] == "E1-001"]
        assert "E1-1" in e1_ids
        assert "E1-5" in e1_ids
        assert "E1-6" in e1_ids

    def test_large_pie_has_governance_disclosures(self):
        """Phase 1 should include ESRS 2 governance disclosures from SR-001."""
        reqs = get_applicable_requirements("large_pie", 2024)
        sr_ids = [r["disclosure_id"] for r in reqs if r["document_id"] == "SR-001"]
        assert "GOV-1" in sr_ids
        assert "SBM-1" in sr_ids
        assert "IRO-1" in sr_ids

    def test_requirements_have_expected_fields(self):
        """Each requirement dict should have all expected fields."""
        reqs = get_applicable_requirements("large_pie", 2024)
        assert len(reqs) > 0
        req = reqs[0]
        assert "document_id" in req
        assert "standard" in req
        assert "disclosure_id" in req
        assert "disclosure_name" in req
        assert "mandatory" in req
        assert "mandatory_if_material" in req

    def test_sr001_is_mandatory(self):
        """SR-001 disclosures should be marked as mandatory."""
        reqs = get_applicable_requirements("large_pie", 2024)
        sr_reqs = [r for r in reqs if r["document_id"] == "SR-001"]
        assert len(sr_reqs) > 0
        for r in sr_reqs:
            assert r["mandatory"] is True

    def test_e1_is_mandatory_if_material(self):
        """E1-001 disclosures should be marked as mandatory_if_material."""
        reqs = get_applicable_requirements("large_pie", 2024)
        e1_reqs = [r for r in reqs if r["document_id"] == "E1-001"]
        assert len(e1_reqs) > 0
        for r in e1_reqs:
            assert r["mandatory_if_material"] is True

    def test_sme_gets_simplified_kpis(self):
        """Phase 3 SMEs with mandatory_kpis should get simplified set."""
        reqs = get_applicable_requirements("sme", 2026)
        # E1 for SMEs has mandatory_kpis instead of full disclosures
        e1_reqs = [r for r in reqs if r["document_id"] == "E1-001"]
        assert len(e1_reqs) > 0
        # Should be the simplified KPIs (3 for E1)
        assert len(e1_reqs) == 3
        assert all(r.get("simplified") for r in e1_reqs)

    def test_procedural_docs_excluded(self):
        """Documents without key_disclosures (ASS, DCL, QA, HIS) should be excluded."""
        reqs = get_applicable_requirements("large_pie", 2024)
        doc_ids = {r["document_id"] for r in reqs}
        assert "ASS-001" not in doc_ids
        assert "DCL-001" not in doc_ids
        assert "QA-001" not in doc_ids
        assert "HIS-001" not in doc_ids

    def test_taxonomy_excluded(self):
        """TAX-001 uses key_kpis not key_disclosures, so excluded from standard filtering."""
        reqs = get_applicable_requirements("large_pie", 2024)
        doc_ids = {r["document_id"] for r in reqs}
        assert "TAX-001" not in doc_ids

    def test_dma_excluded(self):
        """SR-002 (DMA) uses topics_assessed not key_disclosures, so excluded."""
        reqs = get_applicable_requirements("large_pie", 2024)
        doc_ids = {r["document_id"] for r in reqs}
        assert "SR-002" not in doc_ids

    def test_phase1_before_start_year(self):
        """Phase 1 with reporting_year before 2024 should return empty."""
        reqs = get_applicable_requirements("large_pie", 2023)
        assert len(reqs) == 0

    def test_phase2_before_start_year(self):
        """Phase 2 with reporting_year before 2025 should return empty."""
        reqs = get_applicable_requirements("large", 2024)
        assert len(reqs) == 0

    def test_phase2_at_start_year(self):
        """Phase 2 with reporting_year 2025 should return requirements."""
        reqs = get_applicable_requirements("large", 2025)
        assert len(reqs) > 0

    def test_total_disclosures_large_pie_reasonable(self):
        """A Phase 1 company should have a reasonable number of disclosures (50-100+)."""
        reqs = get_applicable_requirements("large_pie", 2024)
        # SR-001 (10) + E1 (9) + E2 (6) + E3 (5) + E4 (6) + E5 (6) +
        # S1 (16) + S2 (5) + S3 (5) + S4 (5) + G1 (6) = ~79
        assert len(reqs) >= 50
        assert len(reqs) <= 120

    def test_sme_fewer_requirements_than_large(self):
        """SMEs should generally have fewer requirements than large companies."""
        large_reqs = get_applicable_requirements("large_pie", 2024)
        sme_reqs = get_applicable_requirements("sme", 2026)
        assert len(sme_reqs) < len(large_reqs)

    def test_all_disclosures_have_nonempty_id(self):
        """All disclosure IDs should be non-empty strings."""
        reqs = get_applicable_requirements("large_pie", 2024)
        for r in reqs:
            assert r["disclosure_id"], f"Empty disclosure_id in {r}"
            assert isinstance(r["disclosure_id"], str)
