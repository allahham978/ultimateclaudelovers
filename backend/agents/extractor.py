"""
Node 1 — ESRS Reader (Extractor) — Iteration 0.5 stub.

Reads: state["esrs_data"] (ESRS-tagged iXBRL sections from report JSON)
Writes: state["esrs_claims"], state["company_meta"]

Iteration 3 will replace the dummy values with a real Claude API call using
SYSTEM_PROMPT_EXTRACTOR and prompt caching on the ESRS data.
"""

import time
from typing import Any

from schemas import CompanyMeta, ESRSClaim
from state import AuditState


def extractor_node(state: AuditState) -> dict[str, Any]:
    """Pass-through stub: logs progress, writes dummy ESRS claims + company meta."""
    started_at = time.time()

    logs: list[dict] = list(state.get("logs") or [])
    pipeline_trace: list[dict] = list(state.get("pipeline_trace") or [])

    ts = lambda: int(time.time() * 1000)  # noqa: E731
    logs.append({"agent": "extractor", "msg": "Reading ESRS sections from management report JSON...", "ts": ts()})
    logs.append({"agent": "extractor", "msg": "Scanning iXBRL tags for E1-1, E1-5, E1-6 data points...", "ts": ts()})
    logs.append({"agent": "extractor", "msg": "Extracting company metadata from entity concepts...", "ts": ts()})

    company_meta = CompanyMeta(
        name=state.get("entity_id") or "Unknown Entity",
        lei=None,
        sector="AI Infrastructure",
        fiscal_year=2024,
        jurisdiction="EU",
        report_title="Annual Management Report 2024",
    )

    esrs_claims: dict[str, ESRSClaim] = {
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

    duration_ms = int((time.time() - started_at) * 1000)
    pipeline_trace.append({"agent": "extractor", "started_at": started_at, "ms": duration_ms})
    logs.append({"agent": "extractor", "msg": f"Extraction complete in {duration_ms}ms", "ts": ts()})

    return {
        "company_meta": company_meta,
        "esrs_claims": esrs_claims,
        "logs": logs,
        "pipeline_trace": pipeline_trace,
    }
