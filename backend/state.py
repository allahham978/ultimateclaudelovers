"""
AuditState TypedDict — shared memory for all LangGraph nodes (dual-mode).

Each node reads from this dict and writes only to its own output keys.
Input keys (audit_id, report_json, esrs_data, taxonomy_data, entity_id, mode,
free_text_input) are set once by FastAPI and never modified.

Dual-mode support:
  - mode="full_audit":       Extractor → Fetcher → Auditor → Consultant
  - mode="compliance_check": Extractor → Auditor → Consultant (Fetcher skipped)
"""

from __future__ import annotations

from typing import TypedDict, Optional

from schemas import (
    CompanyMeta,
    TaxonomyFinancials,
    ESRSClaim,
    ESRSLedgerItem,
    TaxonomyAlignment,
    ComplianceCost,
    TaxonomyRoadmap,
    CSRDAudit,
    RegistrySource,
    ComplianceCheckResult,
)


class AuditState(TypedDict, total=False):
    # ── INIT — set by FastAPI before graph.invoke() ──────────────────────────
    audit_id: str               # UUID for this audit run
    report_json: dict           # Full cleaned JSON from XHTML management report
    esrs_data: dict             # ESRS-tagged iXBRL sections (for Extractor)
    taxonomy_data: dict         # Taxonomy-tagged iXBRL sections (for Fetcher)
    entity_id: str              # Company name / LEI from user input
    logs: list[dict]            # Accumulates { agent, msg, ts } entries
    pipeline_trace: list[dict]  # Accumulates { agent, started_at, ms }
    mode: str                   # "full_audit" | "compliance_check"
    free_text_input: str        # Raw user text (compliance_check only)

    # ── NODE 1 OUTPUT — Extractor writes ─────────────────────────────────────
    esrs_claims: dict[str, ESRSClaim]   # keyed by ESRS ID, e.g. "E1-1"
    company_meta: CompanyMeta
    extracted_goals: list[dict]          # ExtractedGoal dicts (compliance_check only)

    # ── NODE 2 OUTPUT — Fetcher writes (SKIPPED in compliance_check) ─────────
    taxonomy_financials: TaxonomyFinancials
    document_source: RegistrySource

    # ── NODE 3 OUTPUT — Auditor writes ───────────────────────────────────────
    esrs_ledger: list[ESRSLedgerItem]            # full_audit only
    taxonomy_alignment: TaxonomyAlignment         # full_audit only
    compliance_cost: ComplianceCost               # full_audit only
    taxonomy_alignment_score: float               # full_audit only (raw 0–100)
    esrs_coverage: list[dict]                     # ESRSCoverageItem dicts (compliance_check)
    compliance_cost_estimate: dict                # ComplianceCostEstimate dict (compliance_check)

    # ── NODE 4 OUTPUT — Consultant writes ────────────────────────────────────
    roadmap: TaxonomyRoadmap                      # full_audit only
    final_audit: CSRDAudit                        # full_audit only
    todo_list: list[dict]                         # ComplianceTodo dicts (compliance_check)
    final_compliance_check: ComplianceCheckResult  # compliance_check only
