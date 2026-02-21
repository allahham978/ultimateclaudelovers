"""
Node 3 — Double Materiality Evaluator (Auditor) — Iteration 1 stub.

Reads: state["esrs_claims"] + state["taxonomy_financials"]
Writes: state["esrs_ledger"], state["taxonomy_alignment"],
        state["compliance_cost"], state["taxonomy_alignment_score"]

Iteration 5 will replace the dummy values with a real Claude API call using
SYSTEM_PROMPT_AUDITOR and the full double materiality scoring algorithm.
"""

import time
import uuid
from typing import Any

from schemas import ComplianceCost, ESRSLedgerItem, TaxonomyAlignment, TaxonomyFinancials
from state import AuditState


def auditor_node(state: AuditState) -> dict[str, Any]:
    """Pass-through stub: computes alignment from fetcher output, writes dummy ledger."""
    started_at = time.time()

    logs: list[dict] = list(state.get("logs") or [])
    pipeline_trace: list[dict] = list(state.get("pipeline_trace") or [])

    ts = lambda: int(time.time() * 1000)  # noqa: E731
    logs.append({"agent": "auditor", "msg": "Applying double materiality scoring framework...", "ts": ts()})
    logs.append({"agent": "auditor", "msg": "Computing impact and financial materiality per ESRS standard...", "ts": ts()})
    logs.append({"agent": "auditor", "msg": "Calculating EU Taxonomy alignment percentage...", "ts": ts()})

    # Derive taxonomy alignment from fetcher output where available
    tf: TaxonomyFinancials | None = state.get("taxonomy_financials")
    if tf and tf.capex_total_eur and tf.capex_green_eur and tf.capex_total_eur > 0:
        capex_aligned_pct = min(100.0, (tf.capex_green_eur / tf.capex_total_eur) * 100)
    else:
        capex_aligned_pct = 35.0  # safe stub default

    if capex_aligned_pct >= 60:
        taxonomy_status = "aligned"
    elif capex_aligned_pct >= 20:
        taxonomy_status = "partially_aligned"
    else:
        taxonomy_status = "non_compliant"

    taxonomy_alignment = TaxonomyAlignment(
        capex_aligned_pct=round(capex_aligned_pct, 2),
        status=taxonomy_status,
        label=f"{capex_aligned_pct:.1f}% EU Taxonomy-aligned CapEx",
    )

    esrs_ledger: list[ESRSLedgerItem] = [
        ESRSLedgerItem(
            id=str(uuid.uuid4()),
            esrs_id="E1-1",
            data_point="Transition Plan for Climate Change Mitigation",
            impact_materiality="high",
            financial_materiality="medium",
            status="partial",
            evidence_source="management_report",
            registry_evidence="Net-zero 2040 target found; CapEx commitment not fully quantified against Taxonomy activities",
        ),
        ESRSLedgerItem(
            id=str(uuid.uuid4()),
            esrs_id="E1-5",
            data_point="Energy Consumption and Mix",
            impact_materiality="high",
            financial_materiality="medium",
            status="disclosed",
            evidence_source="management_report",
            registry_evidence="Total energy 45,000 MWh disclosed; 38% renewable mix below 70% Taxonomy threshold",
        ),
        ESRSLedgerItem(
            id=str(uuid.uuid4()),
            esrs_id="E1-6",
            data_point="Gross Scopes 1, 2, 3 GHG Emissions",
            impact_materiality="high",
            financial_materiality="low",
            status="partial",
            evidence_source="management_report",
            registry_evidence="Scope 1 and Scope 2 (market-based) disclosed; Scope 3 categories not consolidated",
        ),
    ]

    revenue_eur = (tf.revenue_eur if tf and tf.revenue_eur else 250_000_000.0)
    non_compliant_count = sum(
        1 for item in esrs_ledger if item.status in ("missing", "non_compliant")
    )
    base_rate = non_compliant_count / len(esrs_ledger) if esrs_ledger else 0.0
    projected_fine_eur = revenue_eur * base_rate * 0.05

    compliance_cost = ComplianceCost(
        projected_fine_eur=round(projected_fine_eur, 2),
        basis="Art. 51 CSRD Directive (EU) 2022/2464 — up to EUR 10M or 5% of net worldwide turnover",
    )

    duration_ms = int((time.time() - started_at) * 1000)
    pipeline_trace.append({"agent": "auditor", "started_at": started_at, "ms": duration_ms})
    logs.append({"agent": "auditor", "msg": f"Materiality scoring complete in {duration_ms}ms", "ts": ts()})

    return {
        "esrs_ledger": esrs_ledger,
        "taxonomy_alignment": taxonomy_alignment,
        "compliance_cost": compliance_cost,
        "taxonomy_alignment_score": capex_aligned_pct,
        "logs": logs,
        "pipeline_trace": pipeline_trace,
    }
