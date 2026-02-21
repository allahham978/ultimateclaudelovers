"""
AuditState TypedDict — shared memory for all LangGraph nodes.

Each node reads from this dict and writes only to its own output keys.
Input keys (audit_id, report_json, esrs_data, taxonomy_data, entity_id)
are set once by FastAPI and never modified.
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

    # ── NODE 1 OUTPUT — Extractor writes ─────────────────────────────────────
    esrs_claims: dict[str, ESRSClaim]   # keyed by ESRS ID, e.g. "E1-1"
    company_meta: CompanyMeta

    # ── NODE 2 OUTPUT — Fetcher writes ───────────────────────────────────────
    taxonomy_financials: TaxonomyFinancials
    document_source: RegistrySource

    # ── NODE 3 OUTPUT — Auditor writes ───────────────────────────────────────
    esrs_ledger: list[ESRSLedgerItem]
    taxonomy_alignment: TaxonomyAlignment
    compliance_cost: ComplianceCost
    taxonomy_alignment_score: float     # raw 0–100 before thresholding

    # ── NODE 4 OUTPUT — Consultant writes (also assembles final CSRDAudit) ───
    roadmap: TaxonomyRoadmap
    final_audit: CSRDAudit
