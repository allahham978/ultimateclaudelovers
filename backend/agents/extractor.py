"""
Node 1 — ESRS Reader (Extractor) — dual-mode stub (v5.0).

structured_document: Reads state["esrs_data"] + state["taxonomy_data"] → esrs_claims + company_meta + financial_context
free_text:           Reads state["free_text_input"] → esrs_claims + company_meta (no financial_context)
"""

import time
from typing import Any

from schemas import CompanyMeta, ESRSClaim, FinancialContext
from state import AuditState


def extractor_node(state: AuditState) -> dict[str, Any]:
    """Dual-mode stub: logs progress, writes dummy ESRS claims + company meta.

    In structured_document mode, also writes financial_context (stub values).
    In free_text mode, financial_context is omitted (None).
    """
    started_at = time.time()
    mode = state.get("mode", "structured_document")

    logs: list[dict] = list(state.get("logs") or [])
    pipeline_trace: list[dict] = list(state.get("pipeline_trace") or [])

    ts = lambda: int(time.time() * 1000)  # noqa: E731

    if mode == "free_text":
        logs.append({"agent": "extractor", "msg": "Reading free-text sustainability description...", "ts": ts()})
        logs.append({"agent": "extractor", "msg": "Scanning for ESRS sustainability claims...", "ts": ts()})
        logs.append({"agent": "extractor", "msg": "Extracting company metadata from text...", "ts": ts()})

        company_meta = CompanyMeta(
            name=state.get("entity_id") or "Unknown Entity",
            lei=None,
            sector="Unknown",
            fiscal_year=2024,
            jurisdiction="EU",
            report_title="User-Provided Sustainability Description",
        )

        esrs_claims: dict[str, ESRSClaim] = {
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

        duration_ms = int((time.time() - started_at) * 1000)
        pipeline_trace.append({"agent": "extractor", "started_at": started_at, "ms": duration_ms})
        logs.append({"agent": "extractor", "msg": f"Extraction complete in {duration_ms}ms", "ts": ts()})

        return {
            "company_meta": company_meta,
            "esrs_claims": esrs_claims,
            "logs": logs,
            "pipeline_trace": pipeline_trace,
        }

    # ── structured_document mode (default) ────────────────────────────────
    logs.append({"agent": "extractor", "msg": "Reading ESRS sections from management report JSON...", "ts": ts()})
    logs.append({"agent": "extractor", "msg": "Scanning iXBRL tags for all ESRS data points...", "ts": ts()})
    logs.append({"agent": "extractor", "msg": "Extracting company metadata from entity concepts...", "ts": ts()})
    logs.append({"agent": "extractor", "msg": "Extracting financial context from Taxonomy sections...", "ts": ts()})

    company_meta = CompanyMeta(
        name=state.get("entity_id") or "Unknown Entity",
        lei=None,
        sector="AI Infrastructure",
        fiscal_year=2024,
        jurisdiction="EU",
        report_title="Annual Management Report 2024",
    )

    esrs_claims = {
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

    financial_context = FinancialContext(
        capex_total_eur=50_000_000.0,
        capex_green_eur=17_500_000.0,
        opex_total_eur=120_000_000.0,
        opex_green_eur=24_000_000.0,
        revenue_eur=250_000_000.0,
        taxonomy_activities=[
            "8.1 Data processing, hosting and related activities",
            "4.1 Electricity generation using solar photovoltaic technology",
        ],
        confidence=0.92,
    )

    duration_ms = int((time.time() - started_at) * 1000)
    pipeline_trace.append({"agent": "extractor", "started_at": started_at, "ms": duration_ms})
    logs.append({"agent": "extractor", "msg": f"Extraction complete in {duration_ms}ms", "ts": ts()})

    return {
        "company_meta": company_meta,
        "esrs_claims": esrs_claims,
        "financial_context": financial_context,
        "logs": logs,
        "pipeline_trace": pipeline_trace,
    }
