"""
AuditState TypedDict — shared memory for all LangGraph nodes (v5.0 unified pipeline).

Each node reads from this dict and writes only to its own output keys.
Input keys (audit_id, mode, report_json, esrs_data, taxonomy_data, entity_id,
company_inputs, free_text_input) are set once by FastAPI and never modified.

Pipeline: extractor → scorer → advisor (both modes)
  - mode="structured_document": iXBRL report input, financial_context extracted
  - mode="free_text":           raw text input, financial_context=None
"""

from __future__ import annotations

from typing import TypedDict, Optional

from schemas import (
    CompanyMeta,
    CompanyInputs,
    ComplianceResult,
    ComplianceScore,
    ESRSClaim,
    FinancialContext,
    Recommendation,
)


class AuditState(TypedDict, total=False):
    # ── INIT — set by FastAPI before graph.invoke() ──────────────────────────
    audit_id: str               # UUID for this audit run
    mode: str                   # "structured_document" | "free_text"
    report_json: dict           # Full cleaned JSON from XHTML management report
    esrs_data: dict             # ESRS-tagged iXBRL sections (for Extractor)
    taxonomy_data: dict         # Taxonomy-tagged iXBRL sections (for Extractor financial_context)
    entity_id: str              # Company name / LEI from user input
    company_inputs: CompanyInputs  # User-provided company parameters
    free_text_input: str        # Raw user text (free_text mode only)
    logs: list[dict]            # Accumulates { agent, msg, ts } entries
    pipeline_trace: list[dict]  # Accumulates { agent, started_at, ms }

    # ── NODE 1 OUTPUT — Extractor writes ─────────────────────────────────────
    esrs_claims: dict[str, ESRSClaim]        # keyed by ESRS ID, e.g. "E1-1"
    company_meta: CompanyMeta
    financial_context: Optional[FinancialContext]  # structured_document only; None for free_text

    # ── NODE 2 OUTPUT — Scorer writes ────────────────────────────────────────
    compliance_score: ComplianceScore
    applicable_reqs: list[dict]              # matched requirements per standard
    coverage_gaps: list[dict]                # {esrs_id, status, details} per standard

    # ── NODE 3 OUTPUT — Advisor writes ───────────────────────────────────────
    recommendations: list[Recommendation]
    final_result: ComplianceResult
