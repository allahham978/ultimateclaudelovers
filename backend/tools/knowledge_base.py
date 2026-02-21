"""
Knowledge base loader and query helpers for CSRD / ESRS requirements.

Provides three core functions used by the Scorer agent:
  - load_requirements()  — parse + cache master_requirements.json
  - determine_size_category(employees, revenue, assets)  — match against CSRD thresholds
  - get_applicable_requirements(size_category, reporting_year)  — return filtered ESRS list
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

from data.schema import (
    CSRDPhase,
    CSRDReportingRequirements,
    CompanyApplicability,
    CSRDDocument,
)

_KB_PATH = Path(__file__).resolve().parent.parent / "data" / "master_requirements.json"

# Map human-readable size category → CSRD phase
_SIZE_TO_PHASE: dict[str, CSRDPhase] = {
    "large_pie": CSRDPhase.PHASE_1,
    "large": CSRDPhase.PHASE_2,
    "sme": CSRDPhase.PHASE_3,
    "non_eu": CSRDPhase.PHASE_4,
}

# Regex to extract disclosure ID prefix from "E1-1: Some description..." strings
_DISCLOSURE_ID_RE = re.compile(r"^([A-Za-z0-9]+-\d+)")


# ---------------------------------------------------------------------------
# 1. Load + cache
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def load_requirements() -> CSRDReportingRequirements:
    """Parse and cache master_requirements.json using Pydantic validation."""
    with open(_KB_PATH) as f:
        raw = json.load(f)
    return CSRDReportingRequirements.model_validate(raw)


# ---------------------------------------------------------------------------
# 2. Size category determination
# ---------------------------------------------------------------------------


def determine_size_category(
    employees: int,
    revenue_eur: float,
    total_assets_eur: float,
) -> str:
    """
    Match company dimensions against CSRD thresholds from the knowledge base.

    Uses the Sustainability Report (SR-001) applicability entries as the
    canonical reference for phase classification.

    Returns one of: "large_pie" (Phase 1), "large" (Phase 2), "sme" (Phase 3).
    Phase 4 (non-EU parent) cannot be determined from size alone.
    """
    kb = load_requirements()
    sr = kb.get_document("SR-001")

    int_revenue = int(revenue_eur)
    int_assets = int(total_assets_eur)

    # Try Phase 1 first (most restrictive: ≥500 employees + 2-of-3)
    for app in sr.company_applicability:
        if app.csrd_phase == CSRDPhase.PHASE_1:
            if app.company_qualifies(employees, int_revenue, int_assets):
                return "large_pie"

    # Try Phase 2 (≥250 employees + 2-of-3)
    for app in sr.company_applicability:
        if app.csrd_phase == CSRDPhase.PHASE_2:
            if app.company_qualifies(employees, int_revenue, int_assets):
                return "large"

    # Default: SME
    return "sme"


# ---------------------------------------------------------------------------
# 3. Applicable requirements
# ---------------------------------------------------------------------------


def _extract_disclosure_id(disclosure_text: str) -> str:
    """Extract the disclosure ID from a 'E1-1: description...' string."""
    m = _DISCLOSURE_ID_RE.match(disclosure_text.strip())
    if m:
        return m.group(1)
    return disclosure_text.strip()


def get_applicable_requirements(
    size_category: str,
    reporting_year: int,
    employees: int = 0,
    revenue_eur: float = 0.0,
    total_assets_eur: float = 0.0,
) -> list[dict]:
    """
    Return filtered ESRS disclosure requirements for the given size category
    and reporting year.

    Each returned dict contains:
      - document_id:  e.g. "E1-001"
      - standard:     governing ESRS standard name
      - disclosure_id: e.g. "E1-1"
      - disclosure_name: human-readable name
      - mandatory:    True if unconditionally mandatory
      - mandatory_if_material: True if only required when topic is material

    Only documents whose content includes key_disclosures are included
    (procedural documents like ASS-001, DCL-001, QA-001 are excluded).
    """
    kb = load_requirements()
    phase = _SIZE_TO_PHASE.get(size_category, CSRDPhase.PHASE_3)

    # Get all documents with phase-specific applicability
    phase_docs = kb.get_documents_for_phase(phase)

    # Check if reporting year has started for this phase
    # Use SR-001 as the timing reference
    sr_app: Optional[CompanyApplicability] = None
    for doc, app in phase_docs:
        if doc.document_id == "SR-001":
            sr_app = app
            break

    if sr_app and sr_app.first_data_collection_year:
        if reporting_year < sr_app.first_data_collection_year:
            return []  # Phase hasn't started yet

    results: list[dict] = []

    for doc, app in phase_docs:
        # Only include documents with key_disclosures
        if not doc.content.key_disclosures:
            continue

        # For SMEs with mandatory_kpis, use those instead of full disclosures
        if app.simplified_disclosure_required and app.mandatory_kpis:
            for kpi in app.mandatory_kpis:
                results.append({
                    "document_id": doc.document_id,
                    "standard": doc.governing_standards[0] if doc.governing_standards else "",
                    "disclosure_id": _extract_disclosure_id(kpi),
                    "disclosure_name": kpi,
                    "mandatory": doc.mandatory or False,
                    "mandatory_if_material": doc.mandatory_if_material or False,
                    "simplified": True,
                })
            continue

        # Full disclosures
        for disclosure_text in doc.content.key_disclosures:
            disc_id = _extract_disclosure_id(disclosure_text)
            disc_name = disclosure_text.split(":", 1)[1].strip() if ":" in disclosure_text else disclosure_text

            results.append({
                "document_id": doc.document_id,
                "standard": doc.governing_standards[0] if doc.governing_standards else "",
                "disclosure_id": disc_id,
                "disclosure_name": disc_name,
                "mandatory": doc.mandatory or False,
                "mandatory_if_material": doc.mandatory_if_material or False,
                "simplified": False,
            })

    return results
