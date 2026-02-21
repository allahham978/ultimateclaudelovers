"""
Node 2 — Financial Extractor (Fetcher) — Iteration 0.5 stub.

Reads: state["taxonomy_data"] (Taxonomy-tagged iXBRL sections from report JSON)
Writes: state["taxonomy_financials"], state["document_source"]

Iteration 4 will replace the dummy values with a real Claude API call using
SYSTEM_PROMPT_FETCHER and prompt caching on the taxonomy data.
"""

import time
from typing import Any

from schemas import RegistrySource, TaxonomyFinancials
from state import AuditState


def fetcher_node(state: AuditState) -> dict[str, Any]:
    """Pass-through stub: logs progress, writes dummy TaxonomyFinancials + RegistrySource."""
    started_at = time.time()

    logs: list[dict] = list(state.get("logs") or [])
    pipeline_trace: list[dict] = list(state.get("pipeline_trace") or [])

    ts = lambda: int(time.time() * 1000)  # noqa: E731
    logs.append({"agent": "fetcher", "msg": "Reading Taxonomy sections from management report JSON...", "ts": ts()})
    logs.append({"agent": "fetcher", "msg": "Extracting CapEx and OpEx alignment from iXBRL tags...", "ts": ts()})
    logs.append({"agent": "fetcher", "msg": "Calculating taxonomy-aligned CapEx percentage...", "ts": ts()})

    taxonomy_financials = TaxonomyFinancials(
        capex_total_eur=50_000_000.0,
        capex_green_eur=17_500_000.0,        # 35% aligned
        opex_total_eur=120_000_000.0,
        opex_green_eur=24_000_000.0,         # 20% aligned
        revenue_eur=250_000_000.0,
        fiscal_year="2024",
        taxonomy_activities=[
            "8.1 Data processing, hosting and related activities",
            "4.1 Electricity generation using solar photovoltaic technology",
        ],
        source_document="Annual Management Report — Taxonomy Section",
        confidence=0.92,
    )

    document_source = RegistrySource(
        name="Annual Management Report 2024",
        registry_type="eu_bris",
        jurisdiction="EU",
    )

    duration_ms = int((time.time() - started_at) * 1000)
    pipeline_trace.append({"agent": "fetcher", "started_at": started_at, "ms": duration_ms})
    logs.append({"agent": "fetcher", "msg": f"Financial extraction complete in {duration_ms}ms", "ts": ts()})

    return {
        "taxonomy_financials": taxonomy_financials,
        "document_source": document_source,
        "logs": logs,
        "pipeline_trace": pipeline_trace,
    }
