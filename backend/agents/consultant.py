"""
LEGACY v2.0 — This module is deprecated. The consultant node has been replaced by
the advisor node in the v5.0 unified 3-agent pipeline (extractor → scorer → advisor).

Node 4 — Taxonomy Consultant + Final Assembly — dual-mode stub.

Full Audit:       Reads esrs_ledger + taxonomy_alignment → roadmap + final_audit (CSRDAudit)
Compliance Check: Reads esrs_coverage + company_meta → todo_list + final_compliance_check (ComplianceCheckResult)
"""

import time
from datetime import datetime, timezone
from typing import Any

from schemas import (
    AgentTiming,
    CSRDAudit,
    CompanyMeta,
    ComplianceCost,
    ComplianceCheckResult,
    ComplianceCostEstimate,
    ComplianceTodo,
    ESRSCoverageItem,
    ExtractedGoal,
    PipelineTrace,
    RegistrySource,
    RoadmapPillar,
    Source,
    TaxonomyAlignment,
    TaxonomyRoadmap,
)
from state import AuditState


def consultant_node(state: AuditState) -> dict[str, Any]:
    """Dual-mode stub: full audit generates roadmap; compliance check generates to-do list."""
    started_at = time.time()
    mode = state.get("mode", "full_audit")

    logs: list[dict] = list(state.get("logs") or [])
    pipeline_trace: list[dict] = list(state.get("pipeline_trace") or [])

    ts = lambda: int(time.time() * 1000)  # noqa: E731

    if mode == "compliance_check":
        logs.append({"agent": "consultant", "msg": "Analysing ESRS coverage gaps for to-do list...", "ts": ts()})
        logs.append({"agent": "consultant", "msg": "Generating prioritised compliance action items...", "ts": ts()})
        logs.append({"agent": "consultant", "msg": "Assembling final ComplianceCheckResult...", "ts": ts()})

        # Generate to-do list from coverage assessment
        esrs_coverage_raw = state.get("esrs_coverage") or []
        todo_list: list[dict] = []
        todo_idx = 1

        for item in esrs_coverage_raw:
            coverage = item.get("coverage", "not_covered")
            esrs_id = item.get("esrs_id", "E1-1")

            if coverage == "not_covered":
                priority = "critical"
                effort = "high"
                title = f"Establish {esrs_id} disclosure — currently missing"
                description = (
                    f"No relevant {item.get('standard_name', '')} data was found in your description. "
                    f"This is a mandatory CSRD disclosure under ESRS {esrs_id}. "
                    f"Begin by conducting a baseline assessment and data collection exercise."
                )
            elif coverage == "partial":
                priority = "high"
                effort = "medium"
                title = f"Complete {esrs_id} disclosure — key metrics missing"
                description = (
                    f"Some {item.get('standard_name', '')} information was found but critical metrics are absent. "
                    f"Review ESRS {esrs_id} disclosure requirements and fill the identified gaps."
                )
            else:
                continue  # covered — no action needed

            todo_list.append({
                "id": f"todo-{todo_idx}",
                "priority": priority,
                "esrs_id": esrs_id,
                "title": title,
                "description": description,
                "regulatory_reference": f"ESRS {esrs_id}, Commission Delegated Regulation (EU) 2023/2772",
                "estimated_effort": effort,
            })
            todo_idx += 1

        # Always include foundational to-do items
        todo_list.append({
            "id": f"todo-{todo_idx}",
            "priority": "critical",
            "esrs_id": "CSRD",
            "title": "Prepare XHTML/iXBRL Annual Management Report",
            "description": (
                "Your company currently lacks a properly formatted Annual Management Report in XHTML/iXBRL format. "
                "This is the legally mandated filing format under CSRD. Engage a qualified XBRL tagging service "
                "provider to prepare the report."
            ),
            "regulatory_reference": "CSRD Art. 29d, ESEF Regulation (EU) 2019/815",
            "estimated_effort": "high",
        })
        todo_idx += 1

        todo_list.append({
            "id": f"todo-{todo_idx}",
            "priority": "critical",
            "esrs_id": "CSRD",
            "title": "Engage CSRD-qualified auditor for limited assurance",
            "description": (
                "CSRD requires limited assurance on sustainability reporting from a qualified auditor. "
                "Begin the engagement process early to ensure timely filing. "
                "Select an auditor with ESRS and EU Taxonomy expertise."
            ),
            "regulatory_reference": "CSRD Art. 34, Directive (EU) 2022/2464",
            "estimated_effort": "high",
        })

        # Finalise pipeline trace
        duration_ms = int((time.time() - started_at) * 1000)
        pipeline_trace.append({"agent": "consultant", "started_at": started_at, "ms": duration_ms})

        # Build agent timings (3 agents — fetcher skipped)
        agent_timings: list[AgentTiming] = []
        valid_agents = {"extractor", "auditor", "consultant"}
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

        company_meta: CompanyMeta = state.get("company_meta") or CompanyMeta(
            name=state.get("entity_id") or "Unknown Entity",
            lei=None,
            sector="Unknown",
            fiscal_year=2024,
            jurisdiction="EU",
            report_title="User-Provided Sustainability Description",
        )

        # Build typed models for the final result
        extracted_goals_raw = state.get("extracted_goals") or []
        extracted_goals_typed = [
            ExtractedGoal(**g) if isinstance(g, dict) else g
            for g in extracted_goals_raw
        ]

        esrs_coverage_typed = [
            ESRSCoverageItem(**c) if isinstance(c, dict) else c
            for c in esrs_coverage_raw
        ]

        todo_list_typed = [
            ComplianceTodo(**t) if isinstance(t, dict) else t
            for t in todo_list
        ]

        cost_est_raw = state.get("compliance_cost_estimate") or {
            "estimated_range_low_eur": 0.0,
            "estimated_range_high_eur": 0.0,
            "basis": "Art. 51 CSRD Directive (EU) 2022/2464 — indicative range based on disclosure gaps",
            "caveat": "Insufficient data for cost estimation.",
        }
        cost_estimate_typed = (
            ComplianceCostEstimate(**cost_est_raw)
            if isinstance(cost_est_raw, dict) else cost_est_raw
        )

        final_compliance_check = ComplianceCheckResult(
            audit_id=state.get("audit_id") or "unknown",
            generated_at=datetime.now(timezone.utc).isoformat(),
            schema_version="2.0",
            mode="compliance_check",
            company=company_meta,
            extracted_goals=extracted_goals_typed,
            esrs_coverage=esrs_coverage_typed,
            todo_list=todo_list_typed,
            estimated_compliance_cost=cost_estimate_typed,
            pipeline=PipelineTrace(total_duration_ms=total_ms, agents=agent_timings),
        )

        logs.append({"agent": "consultant", "msg": f"Compliance check assembled in {duration_ms}ms", "ts": ts()})

        return {
            "todo_list": todo_list,
            "final_compliance_check": final_compliance_check,
            "logs": logs,
            "pipeline_trace": pipeline_trace,
        }

    # ── Full Audit mode (default) ────────────────────────────────────────
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
    company_meta = state.get("company_meta") or CompanyMeta(
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
        name="Annual Management Report 2024",
        registry_type="eu_bris",
        jurisdiction="EU",
    )

    sources = [
        Source(id="src-1", document_name="Annual Management Report 2024 (XHTML/iXBRL)", document_type="csrd_report"),
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
