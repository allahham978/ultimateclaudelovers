"""
Node 4 — Taxonomy Consultant + Final Assembly — Iteration 1 stub.

Reads: state["esrs_ledger"] + state["taxonomy_alignment"] + state["company_meta"]
Writes: state["roadmap"], state["final_audit"]

Iteration 6 will replace the dummy roadmap with a real Claude API call using
SYSTEM_PROMPT_CONSULTANT and assemble a fully live CSRDAudit from real data.
"""

import time
from datetime import datetime, timezone
from typing import Any

from schemas import (
    AgentTiming,
    CSRDAudit,
    CompanyMeta,
    ComplianceCost,
    PipelineTrace,
    RegistrySource,
    RoadmapPillar,
    Source,
    TaxonomyAlignment,
    TaxonomyRoadmap,
)
from state import AuditState


def consultant_node(state: AuditState) -> dict[str, Any]:
    """Pass-through stub: generates dummy roadmap, assembles final CSRDAudit."""
    started_at = time.time()

    logs: list[dict] = list(state.get("logs") or [])
    pipeline_trace: list[dict] = list(state.get("pipeline_trace") or [])

    ts = lambda: int(time.time() * 1000)  # noqa: E731
    logs.append({"agent": "consultant", "msg": "Analysing ESRS gaps for roadmap generation...", "ts": ts()})
    logs.append({"agent": "consultant", "msg": "Generating three-pillar EU Taxonomy roadmap...", "ts": ts()})
    logs.append({"agent": "consultant", "msg": "Assembling final CSRDAudit contract...", "ts": ts()})

    # Derive roadmap priorities from ledger statuses
    esrs_ledger = state.get("esrs_ledger") or []
    has_non_compliant = any(item.status == "non_compliant" for item in esrs_ledger)
    has_missing = any(item.status == "missing" for item in esrs_ledger)

    hw_priority = "critical" if has_non_compliant else ("high" if has_missing else "moderate")
    pw_priority = "critical" if has_non_compliant else ("high" if has_missing else "moderate")
    wl_priority = "moderate"

    roadmap = TaxonomyRoadmap(
        hardware=RoadmapPillar(
            title="GPU Infrastructure Refresh — Activity 8.1 Compliance",
            summary=(
                "Current data centre infrastructure does not meet the EU Taxonomy PUE ≤ 1.3 threshold "
                "required under Activity 8.1. Transition to liquid-cooled B200/GB300 GPU racks with "
                "end-of-life circularity contracts to unlock CapEx alignment."
            ),
            priority=hw_priority,
            alignment_increase_pct=12.0,
        ),
        power=RoadmapPillar(
            title="Renewable Energy Procurement — EU GO Scheme",
            summary=(
                "Current renewable mix of 38% falls below the 70% EU Taxonomy threshold for Activity 8.1. "
                "Procure corporate PPAs with EU generators and on-site solar to satisfy ESRS E1-5 and "
                "reduce Scope 2 market-based emissions."
            ),
            priority=pw_priority,
            alignment_increase_pct=18.0,
        ),
        workload=RoadmapPillar(
            title="Carbon-Aware Scheduling — GHG Intensity Reduction",
            summary=(
                "Implement carbon-aware workload scheduling and mixed-precision training to improve "
                "energy-per-FLOP ratio year-on-year, directly addressing the E1-6 GHG intensity "
                "metric gap identified in the ledger."
            ),
            priority=wl_priority,
            alignment_increase_pct=8.0,
        ),
    )

    # Finalise pipeline trace
    duration_ms = int((time.time() - started_at) * 1000)
    pipeline_trace.append({"agent": "consultant", "started_at": started_at, "ms": duration_ms})

    agent_timings: list[AgentTiming] = []
    valid_agents = {"extractor", "fetcher", "auditor", "consultant"}
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

    # Pull accumulated state — fall back to safe defaults so the stub always assembles
    company_meta: CompanyMeta = state.get("company_meta") or CompanyMeta(
        name=state.get("entity_id") or "Unknown Entity",
        lei=None,
        sector="AI Infrastructure",
        fiscal_year=2024,
        jurisdiction="EU",
        report_title="Report 2024",
    )
    taxonomy_alignment: TaxonomyAlignment = state.get("taxonomy_alignment") or TaxonomyAlignment(
        capex_aligned_pct=35.0,
        status="partially_aligned",
        label="35.0% EU Taxonomy-aligned CapEx",
    )
    compliance_cost: ComplianceCost = state.get("compliance_cost") or ComplianceCost(
        projected_fine_eur=0.0,
        basis="Art. 51 CSRD Directive (EU) 2022/2464 — up to EUR 10M or 5% of net worldwide turnover",
    )
    document_source: RegistrySource = state.get("document_source") or RegistrySource(
        name="EU Taxonomy Table",
        registry_type="eu_bris",
        jurisdiction="EU",
    )

    sources = [
        Source(id="src-1", document_name="Integrated Management Report 2024", document_type="csrd_report"),
        Source(id="src-2", document_name="EU Taxonomy Table 2024", document_type="csrd_report"),
        Source(id="src-3", document_name="Climate Transition Plan 2024", document_type="csrd_report"),
    ]

    final_audit = CSRDAudit(
        audit_id=state.get("audit_id") or "unknown",
        generated_at=datetime.now(timezone.utc).isoformat(),
        schema_version="2.0",
        company=company_meta,
        taxonomy_alignment=taxonomy_alignment,
        compliance_cost=compliance_cost,
        esrs_ledger=esrs_ledger,
        roadmap=roadmap,
        registry_source=document_source,
        sources=sources,
        pipeline=PipelineTrace(total_duration_ms=total_ms, agents=agent_timings),
    )

    logs.append({"agent": "consultant", "msg": f"Final audit assembled in {duration_ms}ms", "ts": ts()})

    return {
        "roadmap": roadmap,
        "final_audit": final_audit,
        "logs": logs,
        "pipeline_trace": pipeline_trace,
    }
