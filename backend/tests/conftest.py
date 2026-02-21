"""
Shared test fixtures for unit tests.
"""

import json
import sys
import os
from unittest.mock import MagicMock, patch

# Ensure the backend directory is on the path so imports resolve correctly
# when pytest is run from the repo root or the backend directory.
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

import pytest
from state import AuditState
from schemas import ESRSClaim, TaxonomyFinancials, CompanyInputs, FinancialContext


# Sample iXBRL facts for testing — mimics the engineer's XHTML→JSON output
_SAMPLE_ESRS_FACTS = {
    "facts": [
        {"ix_type": "ix:nonNumeric", "concept": "esrs_E1-1_01_TransitionPlan", "context_ref": "FY2024", "value": "Net-zero by 2040"},
        {"ix_type": "ix:nonFraction", "concept": "esrs_E1-5_04_TotalEnergyConsumption", "context_ref": "FY2024", "value": "45000", "unit_ref": "utr:MWh", "decimals": "0", "scale": None},
        {"ix_type": "ix:nonFraction", "concept": "esrs_E1-6_01_GrossScope1GHGEmissions", "context_ref": "FY2024", "value": "1200", "unit_ref": "utr:tCO2eq", "decimals": "0", "scale": None},
        {"ix_type": "ix:nonNumeric", "concept": "ifrs-full:NameOfReportingEntity", "context_ref": "FY2024", "value": "TestCorp SA"},
    ]
}

_SAMPLE_TAXONOMY_FACTS = {
    "facts": [
        {"ix_type": "ix:nonFraction", "concept": "eutaxonomy:CapExTotal", "context_ref": "FY2024", "value": "50000000", "unit_ref": "iso4217:EUR", "decimals": "0", "scale": None},
        {"ix_type": "ix:nonFraction", "concept": "eutaxonomy:CapExAligned", "context_ref": "FY2024", "value": "17500000", "unit_ref": "iso4217:EUR", "decimals": "0", "scale": None},
        {"ix_type": "ix:nonFraction", "concept": "ifrs-full:Revenue", "context_ref": "FY2024", "value": "250000000", "unit_ref": "iso4217:EUR", "decimals": "0", "scale": None},
    ]
}

_SAMPLE_REPORT_JSON = {
    "report_info": {"source": "test-report.xhtml"},
    "facts": _SAMPLE_ESRS_FACTS["facts"] + _SAMPLE_TAXONOMY_FACTS["facts"],
}


# ---------------------------------------------------------------------------
# Mock Claude API helpers (shared across iteration 3, 6, 7, etc.)
# ---------------------------------------------------------------------------


def _make_mock_claude_response(text: str) -> MagicMock:
    """Create a mock Anthropic Messages API response with the given text content."""
    mock_content_block = MagicMock()
    mock_content_block.text = text
    mock_response = MagicMock()
    mock_response.content = [mock_content_block]
    return mock_response


# Realistic mock responses for each agent

MOCK_EXTRACTOR_RESPONSE_JSON = json.dumps({
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
            "disclosed_value": "Net-zero by 2040; 50% reduction by 2030 vs 2019 baseline",
            "unit": None,
            "confidence": 0.85,
            "xbrl_concept": "esrs_E1-1_01_TransitionPlan",
        },
        "E1-5": {
            "data_point": "Energy Consumption and Mix",
            "disclosed_value": "Total energy: 45,000 MWh; Renewable mix: 38%",
            "unit": "MWh",
            "confidence": 0.90,
            "xbrl_concept": "esrs_E1-5_04_TotalEnergyConsumption",
        },
        "E1-6": {
            "data_point": "Gross Scopes 1, 2, 3 GHG Emissions",
            "disclosed_value": "Scope 1: 1,200 tCO2eq; Scope 2 (market-based): 8,500 tCO2eq",
            "unit": "tCO2eq",
            "confidence": 0.80,
            "xbrl_concept": "esrs_E1-6_01_GrossScope1GHGEmissions",
        },
    },
})

MOCK_FETCHER_RESPONSE_JSON = json.dumps({
    "taxonomy_financials": {
        "capex_total_eur": 50000000.0,
        "capex_green_eur": 17500000.0,
        "opex_total_eur": 120000000.0,
        "opex_green_eur": 24000000.0,
        "revenue_eur": 250000000.0,
        "fiscal_year": "2024",
        "taxonomy_activities": [
            "8.1 Data processing, hosting and related activities",
            "4.1 Electricity generation using solar photovoltaic technology",
        ],
        "source_document": "Annual Management Report — Taxonomy Section",
        "confidence": 0.92,
    }
})

# Reference JSON for auditor full audit (iteration 7)
MOCK_AUDITOR_RESPONSE_JSON = {
    "esrs_ledger": [
        {
            "id": "mock-ledger-e1-1",
            "esrs_id": "E1-1",
            "data_point": "Transition Plan for Climate Change Mitigation",
            "impact_materiality": "medium",
            "financial_materiality": "medium",
            "status": "partial",
            "evidence_source": "management_report",
            "registry_evidence": "Net-zero 2040 target found; CapEx commitment not fully quantified against Taxonomy activities",
        },
        {
            "id": "mock-ledger-e1-5",
            "esrs_id": "E1-5",
            "data_point": "Energy Consumption and Mix",
            "impact_materiality": "high",
            "financial_materiality": "medium",
            "status": "disclosed",
            "evidence_source": "management_report",
            "registry_evidence": "Total energy 45,000 MWh disclosed; 38% renewable mix below 70% Taxonomy threshold",
        },
        {
            "id": "mock-ledger-e1-6",
            "esrs_id": "E1-6",
            "data_point": "Gross Scopes 1, 2, 3 GHG Emissions",
            "impact_materiality": "low",
            "financial_materiality": "medium",
            "status": "partial",
            "evidence_source": "management_report",
            "registry_evidence": "Scope 1 and Scope 2 (market-based) disclosed; Scope 3 categories not consolidated",
        },
    ],
    "taxonomy_alignment": {"capex_aligned_pct": 35.0, "status": "partially_aligned", "label": "35.0% EU Taxonomy-aligned CapEx"},
    "compliance_cost": {"projected_fine_eur": 0.0, "basis": "Art. 51 CSRD Directive (EU) 2022/2464"},
    "taxonomy_alignment_score": 35.0,
}

# Reference JSON for auditor compliance check mode (iteration 7)
MOCK_AUDITOR_LITE_RESPONSE_JSON = {
    "esrs_coverage": [
        {"esrs_id": "E1-1", "standard_name": "Transition Plan for Climate Change Mitigation", "coverage": "partial", "details": "Net-zero target mentioned but CapEx commitment missing."},
        {"esrs_id": "E1-5", "standard_name": "Energy Consumption and Mix", "coverage": "not_covered", "details": "No energy data found in the provided text."},
        {"esrs_id": "E1-6", "standard_name": "Gross Scopes 1, 2, 3 GHG Emissions", "coverage": "not_covered", "details": "No GHG emissions data found."},
    ],
    "compliance_cost_estimate": {
        "estimated_range_low_eur": 833333.33,
        "estimated_range_high_eur": 3333333.33,
        "basis": "Art. 51 CSRD Directive (EU) 2022/2464 — indicative range based on disclosure gaps",
        "caveat": "This estimate is based on incomplete, unstructured data.",
    },
}

# Stub TaxonomyFinancials matching fetcher output (35% CapEx aligned)
STUB_TAXONOMY_FINANCIALS = TaxonomyFinancials(
    capex_total_eur=50_000_000.0,
    capex_green_eur=17_500_000.0,
    opex_total_eur=120_000_000.0,
    opex_green_eur=24_000_000.0,
    revenue_eur=250_000_000.0,
    fiscal_year="2024",
    taxonomy_activities=[
        "8.1 Data processing, hosting and related activities",
        "4.1 Electricity generation using solar photovoltaic technology",
    ],
    source_document="Annual Management Report — Taxonomy Section",
    confidence=0.92,
)

# Stub ESRSClaims matching extractor output (full audit)
STUB_ESRS_CLAIMS = {
    "E1-1": ESRSClaim(
        standard="E1-1",
        data_point="Transition Plan for Climate Change Mitigation",
        disclosed_value="Net-zero by 2040; 50% reduction by 2030 vs 2019 baseline",
        unit=None,
        confidence=0.85,
        xbrl_concept="esrs_E1-1_01_TransitionPlan",
    ),
    "E1-5": ESRSClaim(
        standard="E1-5",
        data_point="Energy Consumption and Mix",
        disclosed_value="Total energy: 45,000 MWh; Renewable mix: 38%",
        unit="MWh",
        confidence=0.90,
        xbrl_concept="esrs_E1-5_04_TotalEnergyConsumption",
    ),
    "E1-6": ESRSClaim(
        standard="E1-6",
        data_point="Gross Scopes 1, 2, 3 GHG Emissions",
        disclosed_value="Scope 1: 1,200 tCO2eq; Scope 2 (market-based): 8,500 tCO2eq",
        unit="tCO2eq",
        confidence=0.80,
        xbrl_concept="esrs_E1-6_01_GrossScope1GHGEmissions",
    ),
}

# Stub ESRSClaims for compliance check mode (lower confidence)
STUB_COMPLIANCE_ESRS_CLAIMS = {
    "E1-1": ESRSClaim(
        standard="E1-1",
        data_point="Transition Plan for Climate Change Mitigation",
        disclosed_value="Net-zero target mentioned",
        unit=None,
        confidence=0.5,
        xbrl_concept=None,
    ),
    "E1-5": ESRSClaim(
        standard="E1-5",
        data_point="Energy Consumption and Mix",
        disclosed_value=None,
        unit=None,
        confidence=0.0,
        xbrl_concept=None,
    ),
    "E1-6": ESRSClaim(
        standard="E1-6",
        data_point="Gross Scopes 1, 2, 3 GHG Emissions",
        disclosed_value=None,
        unit=None,
        confidence=0.0,
        xbrl_concept=None,
    ),
}


# ---------------------------------------------------------------------------
# Full Audit mode fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def minimal_state() -> AuditState:
    """Minimal valid AuditState for testing — only INIT keys set (structured_document mode)."""
    return {
        "audit_id": "test-audit-001",
        "mode": "structured_document",
        "report_json": _SAMPLE_REPORT_JSON,
        "esrs_data": _SAMPLE_ESRS_FACTS,
        "taxonomy_data": _SAMPLE_TAXONOMY_FACTS,
        "entity_id": "TestCorp SA",
        "company_inputs": STUB_COMPANY_INPUTS,
        "logs": [],
        "pipeline_trace": [],
    }


@pytest.fixture
def state_after_extractor(minimal_state) -> AuditState:
    """State after extractor node has run — includes company_meta and esrs_claims."""
    from agents.extractor import extractor_node

    result = extractor_node(minimal_state)
    return {**minimal_state, **result}


@pytest.fixture
def state_after_fetcher(state_after_extractor, mock_anthropic_client) -> AuditState:
    """State after fetcher node has run — includes taxonomy_financials and document_source."""
    from agents.fetcher import fetcher_node

    result = fetcher_node(state_after_extractor)
    return {**state_after_extractor, **result}


@pytest.fixture
def state_after_auditor(state_after_fetcher) -> AuditState:
    """State after auditor node has run — includes esrs_ledger, taxonomy_alignment, etc."""
    from agents.auditor import auditor_node

    result = auditor_node(state_after_fetcher)
    return {**state_after_fetcher, **result}


# ---------------------------------------------------------------------------
# Mock Anthropic client fixture — patches BOTH fetcher and auditor
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_anthropic_client():
    """Patch Anthropic client for both fetcher and auditor, return mock."""
    mock_client = MagicMock()
    # Default response works for fetcher (iteration 6 tests)
    mock_client.messages.create.return_value = _make_mock_claude_response(MOCK_FETCHER_RESPONSE_JSON)

    with patch("agents.fetcher.anthropic.Anthropic", return_value=mock_client), \
         patch("agents.auditor.Anthropic", return_value=mock_client):
        yield mock_client


# ---------------------------------------------------------------------------
# Compliance Check mode fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def compliance_check_state() -> AuditState:
    """Minimal valid AuditState for free_text mode."""
    return {
        "audit_id": "test-compliance-001",
        "mode": "free_text",
        "free_text_input": (
            "We are an AI infrastructure company based in France. "
            "We have set a net-zero target for 2040. "
            "Our data centers consume approximately 120 GWh annually with 29% renewable energy."
        ),
        "entity_id": "Lumiere Systemes SA",
        "company_inputs": STUB_COMPANY_INPUTS_SMALL,
        "report_json": {},
        "esrs_data": {},
        "taxonomy_data": {},
        "logs": [],
        "pipeline_trace": [],
    }


@pytest.fixture
def compliance_state_after_extractor(compliance_check_state) -> AuditState:
    """Compliance check state after extractor node has run."""
    from agents.extractor import extractor_node

    result = extractor_node(compliance_check_state)
    return {**compliance_check_state, **result}


@pytest.fixture
def compliance_state_after_auditor(compliance_state_after_extractor) -> AuditState:
    """Compliance check state after auditor node has run (fetcher skipped)."""
    from agents.auditor import auditor_node

    result = auditor_node(compliance_state_after_extractor)
    return {**compliance_state_after_extractor, **result}


# ---------------------------------------------------------------------------
# Iteration 7 — Auditor-specific fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def stub_taxonomy_financials() -> TaxonomyFinancials:
    """Stub TaxonomyFinancials matching the fetcher stub output (35% CapEx aligned)."""
    return STUB_TAXONOMY_FINANCIALS


@pytest.fixture
def auditor_full_audit_state() -> AuditState:
    """State ready for auditor in full_audit mode (after extractor + fetcher stubs).

    NOTE: Uses legacy "full_audit" mode for testing the deprecated auditor module.
    The v5.0 pipeline uses "structured_document" mode instead.
    """
    return {
        "audit_id": "test-auditor-full-001",
        "mode": "full_audit",
        "report_json": _SAMPLE_REPORT_JSON,
        "esrs_data": _SAMPLE_ESRS_FACTS,
        "taxonomy_data": _SAMPLE_TAXONOMY_FACTS,
        "entity_id": "TestCorp SA",
        "esrs_claims": STUB_ESRS_CLAIMS,
        "taxonomy_financials": STUB_TAXONOMY_FINANCIALS,
        "company_meta": None,
        "logs": [],
        "pipeline_trace": [],
    }


@pytest.fixture
def auditor_compliance_state() -> AuditState:
    """State ready for auditor in compliance_check mode (after extractor stub)."""
    return {
        "audit_id": "test-auditor-compliance-001",
        "mode": "compliance_check",
        "free_text_input": "We are an AI company targeting net-zero by 2040.",
        "entity_id": "Lumiere Systemes SA",
        "report_json": {},
        "esrs_data": {},
        "taxonomy_data": {},
        "esrs_claims": STUB_COMPLIANCE_ESRS_CLAIMS,
        "extracted_goals": [
            {"id": "goal-1", "description": "Net-zero target mentioned", "esrs_relevance": "E1-1", "confidence": 0.5},
        ],
        "logs": [],
        "pipeline_trace": [],
    }


# ---------------------------------------------------------------------------
# v5.0 Fixtures — Unified 3-agent pipeline
# ---------------------------------------------------------------------------

STUB_COMPANY_INPUTS = CompanyInputs(
    number_of_employees=500,
    revenue_eur=85_000_000.0,
    total_assets_eur=42_000_000.0,
    reporting_year=2025,
)

STUB_COMPANY_INPUTS_SMALL = CompanyInputs(
    number_of_employees=50,
    revenue_eur=5_000_000.0,
    total_assets_eur=2_000_000.0,
    reporting_year=2025,
)


@pytest.fixture
def v5_structured_state() -> AuditState:
    """v5.0 AuditState for structured_document mode."""
    return {
        "audit_id": "test-v5-structured-001",
        "mode": "structured_document",
        "report_json": _SAMPLE_REPORT_JSON,
        "esrs_data": _SAMPLE_ESRS_FACTS,
        "taxonomy_data": _SAMPLE_TAXONOMY_FACTS,
        "entity_id": "TestCorp SA",
        "company_inputs": STUB_COMPANY_INPUTS,
        "logs": [],
        "pipeline_trace": [],
    }


@pytest.fixture
def v5_free_text_state() -> AuditState:
    """v5.0 AuditState for free_text mode."""
    return {
        "audit_id": "test-v5-freetext-001",
        "mode": "free_text",
        "free_text_input": "Net-zero by 2040.",
        "entity_id": "GateCorp",
        "company_inputs": STUB_COMPANY_INPUTS_SMALL,
        "report_json": {},
        "esrs_data": {},
        "taxonomy_data": {},
        "logs": [],
        "pipeline_trace": [],
    }
