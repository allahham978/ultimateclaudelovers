"""
Node 3 — Compliance Advisor — Claude API-powered recommendation generation.

Reads: state["compliance_score"], state["coverage_gaps"], state["applicable_reqs"],
       state["financial_context"], state["company_meta"], state["company_inputs"]
Writes: state["recommendations"], state["final_result"]

For each gap where status != "disclosed": calls Claude to generate a specific,
actionable Recommendation with title, description, and regulatory_reference.
Priority assignment is deterministic (not LLM-driven):
  - missing + mandatory → "critical"
  - missing + not mandatory, OR partial + significant gap → "high"
  - partial with minor gap → "moderate"
  - disclosed but improvable → "low"

If financial_context is available, it's passed to Claude to enrich descriptions
with specific financial figures (CapEx/revenue references).

Assembles the unified ComplianceResult with schema_version="3.0".
"""

import json
import re
import time
from datetime import datetime, timezone
from typing import Any, Optional

import anthropic

from schemas import (
    AgentTiming,
    CompanyInputs,
    CompanyMeta,
    ComplianceResult,
    ComplianceScore,
    FinancialContext,
    PipelineTrace,
    Recommendation,
)
from events import emit_log
from state import AuditState
from tools.prompts import SYSTEM_PROMPT_ADVISOR

# Priority sort order for output grouping
_PRIORITY_ORDER = {"critical": 0, "high": 1, "moderate": 2, "low": 3}

# Core mandatory ESRS standard prefixes — these get "critical" when missing
_CORE_MANDATORY_PREFIXES = (
    "GOV-", "SBM-", "IRO-",   # ESRS 2 general disclosures
    "E1-",                      # Climate Change
    "S1-",                      # Own Workforce
)

# Map ESRS ID prefixes to human-readable categories
_CATEGORY_MAP = {
    "E1-": "Climate & Energy",
    "E2-": "Pollution & Resources",
    "E3-": "Pollution & Resources",
    "E4-": "Biodiversity & Ecosystems",
    "E5-": "Pollution & Resources",
    "S1-": "Workforce & Social",
    "S2-": "Workforce & Social",
    "S3-": "Communities & Consumers",
    "S4-": "Communities & Consumers",
    "G1-": "Governance",
    "GOV-": "Governance",
    "SBM-": "General Disclosures",
    "IRO-": "General Disclosures",
}


def _infer_category(esrs_id: str) -> str:
    """Infer a human-readable category from the ESRS ID prefix."""
    for prefix, category in _CATEGORY_MAP.items():
        if esrs_id.startswith(prefix):
            return category
    return "General"


# ---------------------------------------------------------------------------
# Priority assignment (deterministic — no LLM)
# ---------------------------------------------------------------------------


def _assign_priority(
    status: str,
    esrs_id: str,
    mandatory: bool,
    mandatory_if_material: bool,
) -> str:
    """Assign priority tier based on gap status and regulatory importance.

    Rules (per PRD Section 6 — Node 3):
      "critical" = missing AND mandatory (core standards)
      "high"     = missing but lower urgency, OR partial with significant gaps
      "moderate" = partial with minor gaps
      "low"      = disclosed but could be improved
    """
    if status == "missing":
        # Core mandatory standards get critical
        if mandatory or esrs_id.startswith(_CORE_MANDATORY_PREFIXES):
            return "critical"
        return "high"

    if status == "partial":
        # Mandatory partials are high; others are moderate
        if mandatory or esrs_id.startswith(_CORE_MANDATORY_PREFIXES):
            return "high"
        return "moderate"

    # disclosed — only improvable
    return "low"


# ---------------------------------------------------------------------------
# Claude API call for recommendation text generation
# ---------------------------------------------------------------------------


def _build_user_message(
    coverage_gaps: list[dict],
    applicable_reqs: list[dict],
    company_meta: CompanyMeta,
    financial_context: Optional[FinancialContext],
    compliance_score: ComplianceScore,
) -> str:
    """Build the user message for Claude with all advisor context."""
    # Build gap context
    gaps_for_recs = [g for g in coverage_gaps if g.get("status") != "disclosed"]

    # Build applicable_reqs lookup for mandatory info
    req_lookup = {}
    for req in applicable_reqs:
        req_lookup[req["esrs_id"]] = req

    gap_descriptions = []
    for gap in gaps_for_recs:
        esrs_id = gap.get("esrs_id", "UNKNOWN")
        status = gap.get("status", "missing")
        details = gap.get("details", "")
        req_info = req_lookup.get(esrs_id, {})
        mandatory = req_info.get("mandatory", False)
        standard_name = req_info.get("standard_name", esrs_id)

        priority = _assign_priority(status, esrs_id, mandatory, req_info.get("mandatory_if_material", False))

        gap_descriptions.append(
            f"- {esrs_id} ({standard_name}): status={status}, priority={priority}, "
            f"mandatory={mandatory}, details: {details}"
        )

    parts = [
        f"COMPANY: {company_meta.name} | Sector: {company_meta.sector} | "
        f"Jurisdiction: {company_meta.jurisdiction} | FY: {company_meta.fiscal_year}",
        f"\nCOMPLIANCE SCORE: {compliance_score.overall}/100 "
        f"({compliance_score.disclosed_count} disclosed, {compliance_score.partial_count} partial, "
        f"{compliance_score.missing_count} missing out of {compliance_score.applicable_standards_count})",
        f"\nCOVERAGE GAPS REQUIRING RECOMMENDATIONS ({len(gaps_for_recs)}):",
        "\n".join(gap_descriptions),
    ]

    if financial_context is not None:
        fin_lines = ["\nFINANCIAL CONTEXT (use to enrich recommendation descriptions):"]
        if financial_context.capex_total_eur is not None:
            fin_lines.append(f"  CapEx total: €{financial_context.capex_total_eur:,.0f}")
        if financial_context.capex_green_eur is not None:
            fin_lines.append(f"  CapEx green (Taxonomy-aligned): €{financial_context.capex_green_eur:,.0f}")
            if financial_context.capex_total_eur and financial_context.capex_total_eur > 0:
                pct = (financial_context.capex_green_eur / financial_context.capex_total_eur) * 100
                fin_lines.append(f"  Green CapEx %: {pct:.1f}%")
        if financial_context.opex_total_eur is not None:
            fin_lines.append(f"  OpEx total: €{financial_context.opex_total_eur:,.0f}")
        if financial_context.opex_green_eur is not None:
            fin_lines.append(f"  OpEx green: €{financial_context.opex_green_eur:,.0f}")
        if financial_context.revenue_eur is not None:
            fin_lines.append(f"  Revenue: €{financial_context.revenue_eur:,.0f}")
        if financial_context.taxonomy_activities:
            fin_lines.append(f"  Taxonomy activities: {', '.join(financial_context.taxonomy_activities)}")
        parts.append("\n".join(fin_lines))
    else:
        parts.append("\nFINANCIAL CONTEXT: Not available (free-text input mode).")

    parts.append(
        "\nGenerate exactly 1 recommendation per gap listed above. "
        "Use the pre-assigned priority for each. Return valid JSON only."
    )

    return "\n".join(parts)


def _parse_llm_json(raw_text: str) -> dict:
    """Extract JSON from Claude's response, handling markdown fences."""
    text = raw_text.strip()
    # Strip markdown code fences
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
    return json.loads(text)


def _call_claude(
    coverage_gaps: list[dict],
    applicable_reqs: list[dict],
    company_meta: CompanyMeta,
    financial_context: Optional[FinancialContext],
    compliance_score: ComplianceScore,
) -> list[dict]:
    """Call Claude API to generate recommendation text for each gap.

    Returns a list of raw recommendation dicts from Claude's response.
    Raises on API/parse failure (caller handles fallback).
    """
    user_message = _build_user_message(
        coverage_gaps, applicable_reqs, company_meta,
        financial_context, compliance_score,
    )

    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        system=SYSTEM_PROMPT_ADVISOR,
        messages=[{"role": "user", "content": user_message}],
    )

    raw_text = response.content[0].text
    parsed = _parse_llm_json(raw_text)

    return parsed.get("recommendations", [])


# ---------------------------------------------------------------------------
# Fallback: deterministic recommendations (no LLM)
# ---------------------------------------------------------------------------


def _generate_fallback_recommendations(
    coverage_gaps: list[dict],
    applicable_reqs: list[dict],
    financial_context: Optional[FinancialContext],
) -> list[Recommendation]:
    """Generate deterministic recommendations when Claude API fails."""
    req_lookup = {r["esrs_id"]: r for r in applicable_reqs}
    recommendations: list[Recommendation] = []
    rec_idx = 1

    for gap in coverage_gaps:
        status = gap.get("status", "missing")
        if status == "disclosed":
            continue

        esrs_id = gap.get("esrs_id", "UNKNOWN")
        req_info = req_lookup.get(esrs_id, {})
        mandatory = req_info.get("mandatory", False)
        mandatory_if_material = req_info.get("mandatory_if_material", False)
        standard_name = req_info.get("standard_name", esrs_id)

        priority = _assign_priority(status, esrs_id, mandatory, mandatory_if_material)

        category = _infer_category(esrs_id)

        if status == "missing":
            title = f"Start Reporting on {standard_name}"
            description = (
                f"Your report does not include information on {standard_name}. "
                f"This is a {'mandatory' if mandatory else 'material-dependent'} CSRD requirement. "
                f"Begin by conducting a baseline assessment and collecting relevant data."
            )
            impact = (
                f"Missing {standard_name} disclosure may result in non-compliance with EU reporting requirements."
            )
        else:  # partial
            title = f"Complete Your {standard_name} Disclosure"
            description = (
                f"Some {standard_name} information was found but key metrics are missing. "
                f"Review what data points are required and fill the remaining gaps."
            )
            impact = (
                f"Incomplete {standard_name} data reduces your compliance score and may not satisfy auditor requirements."
            )

        # Enrich with financial context if available
        if financial_context is not None and esrs_id.startswith("E1-"):
            if financial_context.capex_total_eur and financial_context.capex_green_eur:
                pct = (financial_context.capex_green_eur / financial_context.capex_total_eur) * 100
                description += (
                    f" Your green CapEx of €{financial_context.capex_green_eur:,.0f} "
                    f"({pct:.0f}% of total) provides a starting baseline for alignment targets."
                )

        recommendations.append(Recommendation(
            id=f"rec-{rec_idx}",
            priority=priority,
            esrs_id=esrs_id,
            title=title,
            description=description,
            regulatory_reference=f"{standard_name} (ESRS {esrs_id})",
            category=category,
            impact=impact,
        ))
        rec_idx += 1

    return recommendations


# ---------------------------------------------------------------------------
# Build recommendations from Claude response
# ---------------------------------------------------------------------------


def _build_recommendations(
    raw_recs: list[dict],
    coverage_gaps: list[dict],
    applicable_reqs: list[dict],
) -> list[Recommendation]:
    """Build validated Recommendation objects from Claude's raw JSON output.

    Priority is overridden deterministically to ensure consistency.
    """
    req_lookup = {r["esrs_id"]: r for r in applicable_reqs}
    gap_lookup = {g["esrs_id"]: g for g in coverage_gaps}
    recommendations: list[Recommendation] = []

    for idx, raw in enumerate(raw_recs, start=1):
        esrs_id = raw.get("esrs_id", "UNKNOWN")
        gap = gap_lookup.get(esrs_id, {})
        req_info = req_lookup.get(esrs_id, {})

        status = gap.get("status", "missing")
        mandatory = req_info.get("mandatory", False)
        mandatory_if_material = req_info.get("mandatory_if_material", False)

        # Override priority deterministically
        priority = _assign_priority(status, esrs_id, mandatory, mandatory_if_material)

        recommendations.append(Recommendation(
            id=raw.get("id", f"rec-{idx}"),
            priority=priority,
            esrs_id=esrs_id,
            title=raw.get("title", f"Address {esrs_id} disclosure gap"),
            description=raw.get("description", f"Review and complete {esrs_id} disclosure requirements."),
            regulatory_reference=raw.get(
                "regulatory_reference",
                f"ESRS {esrs_id}, Commission Delegated Regulation (EU) 2023/2772",
            ),
            category=raw.get("category", _infer_category(esrs_id)),
            impact=raw.get("impact", ""),
        ))

    return recommendations


# ---------------------------------------------------------------------------
# Main advisor node
# ---------------------------------------------------------------------------


def advisor_node(state: AuditState) -> dict[str, Any]:
    """Real advisor: calls Claude to generate recommendations, assembles ComplianceResult."""
    started_at = time.time()

    logs: list[dict] = list(state.get("logs") or [])
    pipeline_trace: list[dict] = list(state.get("pipeline_trace") or [])

    ts = lambda: int(time.time() * 1000)  # noqa: E731
    audit_id = state.get("audit_id", "")

    def log(msg: str) -> None:
        logs.append({"agent": "advisor", "msg": msg, "ts": ts()})
        emit_log(audit_id, "advisor", msg)

    log("Generating recommendations from coverage gaps...")

    # Read inputs from state
    coverage_gaps: list[dict] = state.get("coverage_gaps") or []
    applicable_reqs: list[dict] = state.get("applicable_reqs") or []
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
    financial_context: Optional[FinancialContext] = state.get("financial_context")

    gaps_needing_recs = [g for g in coverage_gaps if g.get("status") != "disclosed"]
    log(
        f"Found {len(gaps_needing_recs)} gaps requiring recommendations "
        f"(financial context: {'available' if financial_context else 'not available'})"
    )

    # Generate recommendations via Claude (with fallback)
    recommendations: list[Recommendation]
    try:
        log("Calling Claude for recommendation generation...")

        raw_recs = _call_claude(
            coverage_gaps, applicable_reqs, company_meta,
            financial_context, compliance_score,
        )

        recommendations = _build_recommendations(raw_recs, coverage_gaps, applicable_reqs)

        log(f"Claude generated {len(recommendations)} recommendations")

    except Exception as exc:
        log(f"Claude API failed ({type(exc).__name__}: {exc}), using deterministic fallback")
        recommendations = _generate_fallback_recommendations(
            coverage_gaps, applicable_reqs, financial_context,
        )

    # Sort by priority tier (critical → high → moderate → low)
    recommendations.sort(key=lambda r: _PRIORITY_ORDER.get(r.priority, 99))

    log(
        f"Final: {len(recommendations)} recommendations "
        f"({sum(1 for r in recommendations if r.priority == 'critical')} critical, "
        f"{sum(1 for r in recommendations if r.priority == 'high')} high, "
        f"{sum(1 for r in recommendations if r.priority == 'moderate')} moderate, "
        f"{sum(1 for r in recommendations if r.priority == 'low')} low)"
    )

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

    log(f"ComplianceResult assembled in {duration_ms}ms")

    return {
        "recommendations": recommendations,
        "final_result": final_result,
        "logs": logs,
        "pipeline_trace": pipeline_trace,
    }
