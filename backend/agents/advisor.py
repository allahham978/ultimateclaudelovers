"""
Node 3 — Compliance Advisor — deterministic (no Claude API call).

Reads: state["compliance_score"], state["coverage_gaps"], state["financial_context"],
       state["company_meta"], state["company_inputs"], state["esrs_claims"]
Writes: state["recommendations"], state["final_result"]

For each gap where status != "disclosed": generates 1 Recommendation.
Priority: missing → "critical", partial → "high".
Assembles the unified ComplianceResult with schema_version="3.0".
"""

import time
from datetime import datetime, timezone
from typing import Any

from schemas import (
    AgentTiming,
    CompanyInputs,
    CompanyMeta,
    ComplianceResult,
    ComplianceScore,
    PipelineTrace,
    Recommendation,
)
from state import AuditState


def advisor_node(state: AuditState) -> dict[str, Any]:
    """Deterministic advisor: generates recommendations from coverage gaps and assembles final result."""
    started_at = time.time()

    logs: list[dict] = list(state.get("logs") or [])
    pipeline_trace: list[dict] = list(state.get("pipeline_trace") or [])

    ts = lambda: int(time.time() * 1000)  # noqa: E731

    logs.append({"agent": "advisor", "msg": "Generating recommendations from coverage gaps...", "ts": ts()})

    coverage_gaps: list[dict] = state.get("coverage_gaps") or []
    compliance_score: ComplianceScore = state.get("compliance_score") or ComplianceScore(
        overall=0, size_category="unknown", applicable_standards_count=0,
        disclosed_count=0, partial_count=0, missing_count=0,
    )
    company_meta: CompanyMeta = state.get("company_meta") or CompanyMeta(
        name=state.get("entity_id") or "Unknown Entity",
        lei=None, sector="Unknown", fiscal_year=2025,
        jurisdiction="EU", report_title="Unknown Report",
    )
    company_inputs: CompanyInputs = state.get("company_inputs") or CompanyInputs(
        number_of_employees=0, revenue_eur=0.0, total_assets_eur=0.0, reporting_year=2025,
    )

    # Generate recommendations for non-disclosed gaps
    recommendations: list[Recommendation] = []
    rec_idx = 1

    for gap in coverage_gaps:
        status = gap.get("status", "missing")
        if status == "disclosed":
            continue

        esrs_id = gap.get("esrs_id", "UNKNOWN")

        if status == "missing":
            priority = "critical"
            title = f"Establish {esrs_id} disclosure — currently missing"
            description = (
                f"No adequate {esrs_id} disclosure was found. "
                f"This is a mandatory CSRD disclosure requirement. "
                f"Begin by conducting a baseline assessment and data collection exercise."
            )
        else:  # partial
            priority = "high"
            title = f"Complete {esrs_id} disclosure — key metrics missing"
            description = (
                f"Partial {esrs_id} information was found but critical metrics are absent. "
                f"Review the ESRS {esrs_id} disclosure requirements and fill the identified gaps."
            )

        recommendations.append(Recommendation(
            id=f"rec-{rec_idx}",
            priority=priority,
            esrs_id=esrs_id,
            title=title,
            description=description,
            regulatory_reference=f"ESRS {esrs_id}, Commission Delegated Regulation (EU) 2023/2772",
        ))
        rec_idx += 1

    logs.append({
        "agent": "advisor",
        "msg": f"Generated {len(recommendations)} recommendations",
        "ts": ts(),
    })

    # Finalise pipeline trace
    duration_ms = int((time.time() - started_at) * 1000)
    pipeline_trace.append({"agent": "advisor", "started_at": started_at, "ms": duration_ms})

    # Build agent timings from accumulated pipeline_trace (3 agents)
    agent_timings: list[AgentTiming] = []
    valid_agents = {"extractor", "scorer", "advisor"}
    for entry in pipeline_trace:
        if entry.get("agent") in valid_agents:
            agent_timings.append(
                AgentTiming(
                    agent=entry["agent"],
                    duration_ms=entry["ms"],
                    status="completed",
                )
            )
    total_ms = sum(t.duration_ms for t in agent_timings)

    final_result = ComplianceResult(
        audit_id=state.get("audit_id") or "unknown",
        generated_at=datetime.now(timezone.utc).isoformat(),
        schema_version="3.0",
        mode=state.get("mode") or "structured_document",
        company=company_meta,
        company_inputs=company_inputs,
        score=compliance_score,
        recommendations=recommendations,
        pipeline=PipelineTrace(total_duration_ms=total_ms, agents=agent_timings),
    )

    logs.append({"agent": "advisor", "msg": f"Final ComplianceResult assembled in {duration_ms}ms", "ts": ts()})

    return {
        "recommendations": recommendations,
        "final_result": final_result,
        "logs": logs,
        "pipeline_trace": pipeline_trace,
    }
