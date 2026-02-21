"""
Shared test fixtures for unit tests.
"""

import sys
import os

# Ensure the backend directory is on the path so imports resolve correctly
# when pytest is run from the repo root or the backend directory.
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

import pytest
from state import AuditState


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
# Full Audit mode fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def minimal_state() -> AuditState:
    """Minimal valid AuditState for testing — only INIT keys set (full_audit mode)."""
    return {
        "audit_id": "test-audit-001",
        "mode": "full_audit",
        "report_json": _SAMPLE_REPORT_JSON,
        "esrs_data": _SAMPLE_ESRS_FACTS,
        "taxonomy_data": _SAMPLE_TAXONOMY_FACTS,
        "entity_id": "TestCorp SA",
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
def state_after_fetcher(state_after_extractor) -> AuditState:
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
# Compliance Check mode fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def compliance_check_state() -> AuditState:
    """Minimal valid AuditState for compliance_check mode."""
    return {
        "audit_id": "test-compliance-001",
        "mode": "compliance_check",
        "free_text_input": (
            "We are an AI infrastructure company based in France. "
            "We have set a net-zero target for 2040. "
            "Our data centers consume approximately 120 GWh annually with 29% renewable energy."
        ),
        "entity_id": "Lumiere Systemes SA",
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
