"""
Shared test fixtures for unit tests — v5.0 unified 3-agent pipeline.
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
from schemas import ESRSClaim, CompanyInputs, FinancialContext


# Sample iXBRL facts for testing — mimics the engineer's XHTML->JSON output
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
# Mock Claude API helpers
# ---------------------------------------------------------------------------


def _make_mock_claude_response(text: str) -> MagicMock:
    """Create a mock Anthropic Messages API response with the given text content."""
    mock_content_block = MagicMock()
    mock_content_block.text = text
    mock_response = MagicMock()
    mock_response.content = [mock_content_block]
    return mock_response


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

MOCK_EXTRACTOR_LITE_RESPONSE_JSON = json.dumps({
    "company_meta": {
        "name": "Lumiere Systemes SA",
        "lei": None,
        "sector": "AI Infrastructure",
        "fiscal_year": None,
        "jurisdiction": "FR",
        "report_title": "User-Provided Sustainability Description",
    },
    "esrs_claims": {
        "E1-1": {
            "data_point": "Transition Plan for Climate Change Mitigation",
            "disclosed_value": "Net-zero target mentioned",
            "unit": None,
            "confidence": 0.5,
            "xbrl_concept": None,
        },
        "E1-5": {
            "data_point": "Energy Consumption and Mix",
            "disclosed_value": None,
            "unit": None,
            "confidence": 0.0,
            "xbrl_concept": None,
        },
        "E1-6": {
            "data_point": "Gross Scopes 1, 2, 3 GHG Emissions",
            "disclosed_value": None,
            "unit": None,
            "confidence": 0.0,
            "xbrl_concept": None,
        },
    },
    "financial_context": None,
})

# Stub ESRSClaims matching extractor output
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
def minimal_state() -> AuditState:
    """Minimal valid AuditState for testing — structured_document mode."""
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
def mock_anthropic_client():
    """Patch Anthropic client for extractor and advisor agents."""

    mock_client = MagicMock()
    mock_client.messages.create.return_value = _make_mock_claude_response(MOCK_EXTRACTOR_RESPONSE_JSON)

    with patch("agents.extractor.anthropic.Anthropic", return_value=mock_client), \
         patch("agents.advisor.anthropic.Anthropic", return_value=mock_client):
        yield mock_client


@pytest.fixture
def state_after_extractor(minimal_state, mock_anthropic_client) -> AuditState:
    """State after extractor node has run."""
    from agents.extractor import extractor_node

    result = extractor_node(minimal_state)
    return {**minimal_state, **result}


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


@pytest.fixture
def compliance_check_state() -> AuditState:
    """AuditState for free_text mode with realistic text."""
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
    """Free text state after extractor node has run."""
    from agents.extractor import extractor_node

    mock_client = MagicMock()
    mock_client.messages.create.return_value = _make_mock_claude_response(MOCK_EXTRACTOR_LITE_RESPONSE_JSON)

    with patch("agents.extractor.anthropic.Anthropic", return_value=mock_client):
        result = extractor_node(compliance_check_state)
    return {**compliance_check_state, **result}
