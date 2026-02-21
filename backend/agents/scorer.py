"""
Node 2 — Compliance Scorer — knowledge-base-driven (no Claude API call).

Reads:  state["esrs_claims"], state["company_inputs"]
Writes: state["compliance_score"], state["applicable_reqs"], state["coverage_gaps"]

Scoring algorithm (PRD Section 6 / Iteration 9):
  1. Load knowledge base via knowledge_base.load_requirements()
  2. determine_size_category() from company_inputs
  3. get_applicable_requirements() → mandatory ESRS disclosure list
  4. For each applicable requirement, check matching esrs_claim:
     - confidence >= 0.7 AND disclosed_value is not None → "disclosed"
     - 0.3 <= confidence < 0.7 → "partial"
     - else (or no matching claim) → "missing"
  5. overall = round(((disclosed * 1.0 + partial * 0.5) / total) * 100)
"""

import time
from typing import Any

from schemas import CompanyInputs, ComplianceScore, ESRSClaim
from state import AuditState
from tools.knowledge_base import (
    determine_size_category,
    get_applicable_requirements,
)


def _classify_claim(claim: ESRSClaim) -> str:
    """Classify a single ESRS claim as disclosed / partial / missing."""
    if claim.confidence >= 0.7 and claim.disclosed_value is not None:
        return "disclosed"
    if 0.3 <= claim.confidence < 0.7:
        return "partial"
    return "missing"


def scorer_node(state: AuditState) -> dict[str, Any]:
    """Knowledge-base-driven compliance scorer.

    Compares extracted ESRS claims against all applicable disclosure
    requirements from the CSRD knowledge base and computes an overall
    compliance score.
    """
    started_at = time.time()

    logs: list[dict] = list(state.get("logs") or [])
    pipeline_trace: list[dict] = list(state.get("pipeline_trace") or [])

    ts = lambda: int(time.time() * 1000)  # noqa: E731

    logs.append({"agent": "scorer", "msg": "Starting compliance scoring...", "ts": ts()})

    esrs_claims: dict[str, ESRSClaim] = state.get("esrs_claims") or {}
    company_inputs: CompanyInputs = state.get("company_inputs") or CompanyInputs(
        number_of_employees=0, revenue_eur=0.0, total_assets_eur=0.0, reporting_year=2025,
    )

    # Step 1-2: Determine size category from knowledge base thresholds
    size_category = determine_size_category(
        employees=company_inputs.number_of_employees,
        revenue_eur=company_inputs.revenue_eur,
        total_assets_eur=company_inputs.total_assets_eur,
    )

    logs.append({
        "agent": "scorer",
        "msg": f"Company classified as '{size_category}' (employees={company_inputs.number_of_employees}, "
               f"revenue=€{company_inputs.revenue_eur:,.0f}, assets=€{company_inputs.total_assets_eur:,.0f})",
        "ts": ts(),
    })

    # Step 3: Get applicable requirements from knowledge base
    applicable = get_applicable_requirements(
        size_category=size_category,
        reporting_year=company_inputs.reporting_year,
        employees=company_inputs.number_of_employees,
        revenue_eur=company_inputs.revenue_eur,
        total_assets_eur=company_inputs.total_assets_eur,
    )

    logs.append({
        "agent": "scorer",
        "msg": f"Knowledge base returned {len(applicable)} applicable disclosure requirements",
        "ts": ts(),
    })

    # Step 4: Compare claims against requirements
    disclosed_count = 0
    partial_count = 0
    missing_count = 0

    coverage_gaps: list[dict] = []
    applicable_reqs: list[dict] = []

    for req in applicable:
        disc_id = req["disclosure_id"]
        disc_name = req["disclosure_name"]
        standard = req["standard"]

        # Look for a matching claim
        claim = esrs_claims.get(disc_id)

        if claim is not None:
            status = _classify_claim(claim)
            confidence = claim.confidence
            disclosed_value = claim.disclosed_value
        else:
            # No claim found for this requirement → missing
            status = "missing"
            confidence = 0.0
            disclosed_value = None

        if status == "disclosed":
            disclosed_count += 1
            details = f"{disc_name}: adequately disclosed (confidence={confidence:.2f})."
        elif status == "partial":
            partial_count += 1
            details = f"{disc_name}: partially disclosed but key metrics missing (confidence={confidence:.2f})."
        else:
            missing_count += 1
            details = f"{disc_name}: no adequate disclosure found."

        coverage_gaps.append({
            "esrs_id": disc_id,
            "status": status,
            "details": details,
            "document_id": req["document_id"],
        })

        applicable_reqs.append({
            "esrs_id": disc_id,
            "standard_name": disc_name,
            "standard": standard,
            "status": status,
            "confidence": confidence,
            "disclosed_value": disclosed_value,
            "mandatory": req["mandatory"],
            "mandatory_if_material": req["mandatory_if_material"],
        })

    # Step 5: Compute overall score
    total = disclosed_count + partial_count + missing_count
    if total > 0:
        overall = round(((disclosed_count * 1.0 + partial_count * 0.5) / total) * 100)
    else:
        overall = 0

    compliance_score = ComplianceScore(
        overall=overall,
        size_category=size_category,
        applicable_standards_count=total,
        disclosed_count=disclosed_count,
        partial_count=partial_count,
        missing_count=missing_count,
    )

    logs.append({
        "agent": "scorer",
        "msg": f"Score: {overall}/100 — {disclosed_count} disclosed, {partial_count} partial, "
               f"{missing_count} missing out of {total} requirements (size: {size_category})",
        "ts": ts(),
    })

    duration_ms = int((time.time() - started_at) * 1000)
    pipeline_trace.append({"agent": "scorer", "started_at": started_at, "ms": duration_ms})
    logs.append({"agent": "scorer", "msg": f"Scoring complete in {duration_ms}ms", "ts": ts()})

    return {
        "compliance_score": compliance_score,
        "applicable_reqs": applicable_reqs,
        "coverage_gaps": coverage_gaps,
        "logs": logs,
        "pipeline_trace": pipeline_trace,
    }
