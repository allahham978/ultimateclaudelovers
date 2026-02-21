"""
Shared test fixtures for Iteration 1 unit tests.
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


@pytest.fixture
def minimal_state() -> AuditState:
    """Minimal valid AuditState for testing — only INIT keys set."""
    return {
        "audit_id": "test-audit-001",
        "report_json": {"facts": []},
        "esrs_data": {
            "esrs_e1-1_01": {"concept": "esrs_e1-1_01", "value": "Net-zero by 2050", "unit": None, "context": "2024"},
            "esrs_e1-5_01": {"concept": "esrs_e1-5_01", "value": "45000", "unit": "MWh", "context": "2024"},
            "esrs_e1-6_01": {"concept": "esrs_e1-6_01", "value": "1200", "unit": "tCO2eq", "context": "2024"},
        },
        "taxonomy_data": {
            "eutaxonomy:CapExTotal": {"concept": "eutaxonomy:CapExTotal", "value": "50000000", "unit": "iso4217:EUR", "context": "2024"},
            "eutaxonomy:CapExAligned": {"concept": "eutaxonomy:CapExAligned", "value": "17500000", "unit": "iso4217:EUR", "context": "2024"},
        },
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
