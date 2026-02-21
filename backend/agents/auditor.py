"""
Node 3 — Double Materiality Evaluator (Auditor) — real Claude API call.

Full Audit:       Reads esrs_claims + taxonomy_financials → esrs_ledger, taxonomy_alignment, compliance_cost
Compliance Check: Reads esrs_claims + extracted_goals → esrs_coverage, compliance_cost_estimate

Scoring algorithm (deterministic fallback when Claude is unavailable):
  - Impact materiality:  per-standard rubric (E1-1, E1-5, E1-6)  0–100
  - Financial materiality: CapEx green ratio from taxonomy_financials 0–100
  - Status classification: impact_score + disclosed_value + financial_score → ESRSStatus
  - Compliance cost: Art. 51 CSRD formula
"""

import json
import re
import time
import uuid
from typing import Any, Optional

from anthropic import Anthropic

from schemas import (
    ComplianceCost,
    ESRSClaim,
    ESRSLedgerItem,
    MaterialityLevel,
    TaxonomyAlignment,
    TaxonomyFinancials,
)
from state import AuditState
from tools.prompts import SYSTEM_PROMPT_AUDITOR, SYSTEM_PROMPT_AUDITOR_LITE

# ── Constants ────────────────────────────────────────────────────────────────
MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 4096

# ESRS standards we score
ESRS_STANDARDS = {
    "E1-1": "Transition Plan for Climate Change Mitigation",
    "E1-5": "Energy Consumption and Mix",
    "E1-6": "Gross Scopes 1, 2, 3 GHG Emissions",
}


# ── JSON parsing ─────────────────────────────────────────────────────────────

def _parse_llm_json(raw: str) -> dict:
    """Extract and parse JSON from a Claude response (handles markdown fences)."""
    text = raw.strip()
    # Strip ```json ... ``` or ``` ... ```
    fence = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    return json.loads(text)


# ── Deterministic scoring helpers ────────────────────────────────────────────

def _score_impact_e1_1(claim: Optional[ESRSClaim]) -> int:
    """Score impact materiality for E1-1 (Transition Plan).  0–100."""
    if claim is None:
        return 0
    score = 0
    val = claim.disclosed_value or ""
    val_lower = val.lower()

    # +35 pts: disclosed_value present AND contains a target year
    if val and re.search(r"\b20\d{2}\b", val):
        score += 35

    # +25 pts: CapEx commitment amount explicitly stated (EUR)
    if re.search(r"(?:eur|€|\bcapex\b)", val_lower) and re.search(r"\d", val):
        score += 25

    # +20 pts: 1.5°C pathway alignment explicitly referenced
    if "1.5" in val or "paris" in val_lower or "pathway" in val_lower:
        score += 20

    # -30 pts: confidence < 0.5
    if claim.confidence < 0.5:
        score -= 30

    # -20 pts: no target year found
    if not re.search(r"\b20\d{2}\b", val):
        score -= 20

    return max(0, min(100, score))


def _score_impact_e1_5(claim: Optional[ESRSClaim]) -> int:
    """Score impact materiality for E1-5 (Energy Consumption and Mix).  0–100."""
    if claim is None:
        return 0
    score = 0
    val = claim.disclosed_value or ""
    val_lower = val.lower()

    # +40 pts: total energy consumption disclosed with unit
    if claim.unit and re.search(r"\d", val):
        score += 40
    elif re.search(r"\d+.*(?:mwh|gwh|kwh)", val_lower):
        score += 40

    # +30 pts: renewable % explicitly stated
    if re.search(r"(?:renewable|green).*\d+\s*%", val_lower) or re.search(r"\d+\s*%.*(?:renewable|green)", val_lower):
        score += 30

    # +20 pts: year-on-year trend disclosed
    if any(kw in val_lower for kw in ("yoy", "year-on-year", "year over year", "trend", "reduction", "decrease", "increase")):
        score += 20

    # -25 pts: only estimated/approximated values
    if any(kw in val_lower for kw in ("estimated", "approximately", "approx", "~")):
        score -= 25

    # -15 pts: missing unit
    if not claim.unit and not re.search(r"(?:mwh|gwh|kwh|tj|gj)", val_lower):
        score -= 15

    return max(0, min(100, score))


def _score_impact_e1_6(claim: Optional[ESRSClaim]) -> int:
    """Score impact materiality for E1-6 (GHG Emissions).  0–100."""
    if claim is None:
        return 0
    score = 0
    val = claim.disclosed_value or ""
    val_lower = val.lower()

    # +30 pts: Scope 1 AND Scope 2 market-based both disclosed
    has_scope1 = "scope 1" in val_lower or "scope1" in val_lower
    has_scope2 = "scope 2" in val_lower or "scope2" in val_lower
    if has_scope1 and has_scope2:
        score += 30

    # +30 pts: Scope 3 total or category breakdown disclosed
    has_scope3 = "scope 3" in val_lower or "scope3" in val_lower
    if has_scope3:
        score += 30

    # +20 pts: GHG intensity metric present
    if "intensity" in val_lower or ("per" in val_lower and ("eur" in val_lower or "mwh" in val_lower or "revenue" in val_lower)):
        score += 20

    # -20 pts: Scope 3 missing entirely
    if not has_scope3:
        score -= 20

    # -15 pts: No methodology or base year disclosed
    if not any(kw in val_lower for kw in ("methodology", "base year", "ghg protocol", "iso 14064")):
        score -= 15

    return max(0, min(100, score))


def _score_financial_materiality(tf: Optional[TaxonomyFinancials]) -> int:
    """Score financial materiality from taxonomy financials.  0–100.

    Applied identically to all ledger rows.
    """
    if tf is None or tf.capex_total_eur is None:
        return max(0, 0 - 20)  # -20 pts for null capex_total_eur

    if tf.capex_total_eur <= 0:
        return 0

    score = 0

    # +20 pts: capex_total_eur is present and non-zero (always true if we reach here)
    score += 20

    if tf.capex_green_eur is not None:
        ratio = tf.capex_green_eur / tf.capex_total_eur
        if ratio > 0.30:
            score += 40       # +40 pts green CapEx > 30%
        elif ratio > 0.15:
            score += 30       # +30 pts green CapEx > 15%

        if ratio < 0.10:
            score -= 30       # -30 pts < 10% green investment
    else:
        score -= 20           # effectively null capex_green

    return max(0, min(100, score))


def _materiality_level(score: int) -> MaterialityLevel:
    """Map a 0–100 numeric score to a MaterialityLevel label."""
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    if score >= 20:
        return "low"
    return "not_material"


def _esrs_status(impact_score: int, financial_score: int, disclosed_value: Optional[str]) -> str:
    """Determine ESRS status from scores and whether a value was disclosed.

    Rules (from PRD):
      impact_score >= 70 AND disclosed_value not null → "disclosed"
      impact_score >= 40                              → "partial"
      disclosed_value is null                         → "missing"
      financial_score < 20                            → "non_compliant" (override)
    """
    # financial override first (lowest priority in the chain but tested last)
    if financial_score < 20:
        return "non_compliant"
    if disclosed_value is None:
        return "missing"
    if impact_score >= 70 and disclosed_value is not None:
        return "disclosed"
    if impact_score >= 40:
        return "partial"
    return "missing"


def _compute_taxonomy_alignment(tf: Optional[TaxonomyFinancials]) -> tuple[float, str, str]:
    """Return (capex_aligned_pct, status, label) from TaxonomyFinancials."""
    if tf and tf.capex_total_eur and tf.capex_green_eur and tf.capex_total_eur > 0:
        pct = min(100.0, max(0.0, (tf.capex_green_eur / tf.capex_total_eur) * 100))
    else:
        pct = 0.0

    if pct >= 60:
        status = "aligned"
    elif pct >= 20:
        status = "partially_aligned"
    else:
        status = "non_compliant"

    label = f"{pct:.1f}% EU Taxonomy-aligned CapEx"
    return round(pct, 2), status, label


def _compute_compliance_cost(
    esrs_ledger: list[ESRSLedgerItem],
    revenue_eur: float,
) -> ComplianceCost:
    """Art. 51 CSRD: projected_fine = revenue × (non_compliant_count / total) × 0.05."""
    non_compliant_count = sum(
        1 for item in esrs_ledger if item.status in ("missing", "non_compliant")
    )
    total = len(esrs_ledger) if esrs_ledger else 1
    base_rate = non_compliant_count / total
    projected_fine_eur = revenue_eur * base_rate * 0.05

    return ComplianceCost(
        projected_fine_eur=round(projected_fine_eur, 2),
        basis="Art. 51 CSRD Directive (EU) 2022/2464 — up to EUR 10M or 5% of net worldwide turnover",
    )


def _build_ledger_deterministic(
    esrs_claims: dict[str, ESRSClaim],
    tf: Optional[TaxonomyFinancials],
) -> list[ESRSLedgerItem]:
    """Build esrs_ledger using deterministic scoring (fallback path)."""
    financial_score = _score_financial_materiality(tf)

    scorers = {
        "E1-1": _score_impact_e1_1,
        "E1-5": _score_impact_e1_5,
        "E1-6": _score_impact_e1_6,
    }

    ledger: list[ESRSLedgerItem] = []
    for esrs_id, data_point in ESRS_STANDARDS.items():
        claim = esrs_claims.get(esrs_id)
        impact_score = scorers[esrs_id](claim)
        disclosed_value = claim.disclosed_value if claim else None

        status = _esrs_status(impact_score, financial_score, disclosed_value)

        evidence = ""
        if claim and claim.disclosed_value:
            evidence = f"Extracted from management report: {claim.disclosed_value}"
            if claim.xbrl_concept:
                evidence += f" (iXBRL: {claim.xbrl_concept})"
        else:
            evidence = f"No disclosure found for {data_point}"

        ledger.append(ESRSLedgerItem(
            id=str(uuid.uuid4()),
            esrs_id=esrs_id,
            data_point=data_point,
            impact_materiality=_materiality_level(impact_score),
            financial_materiality=_materiality_level(financial_score),
            status=status,
            evidence_source="management_report",
            registry_evidence=evidence,
        ))

    return ledger


def _build_ledger_from_llm(parsed: dict, financial_score: int) -> list[ESRSLedgerItem]:
    """Build esrs_ledger from Claude's parsed JSON response."""
    raw_ledger = parsed.get("esrs_ledger", [])
    ledger: list[ESRSLedgerItem] = []

    for item in raw_ledger:
        ledger.append(ESRSLedgerItem(
            id=item.get("id", str(uuid.uuid4())),
            esrs_id=item.get("esrs_id", ""),
            data_point=item.get("data_point", ""),
            impact_materiality=item.get("impact_materiality", "not_material"),
            financial_materiality=item.get("financial_materiality", _materiality_level(financial_score)),
            status=item.get("status", "missing"),
            evidence_source=item.get("evidence_source", "management_report"),
            registry_evidence=item.get("registry_evidence", ""),
        ))

    return ledger


def _build_coverage_deterministic(
    esrs_claims: dict[str, ESRSClaim],
) -> list[dict]:
    """Build esrs_coverage using deterministic rules (fallback path)."""
    coverage_items = []
    for esrs_id, standard_name in ESRS_STANDARDS.items():
        claim = esrs_claims.get(esrs_id)
        if claim and claim.confidence >= 0.7 and claim.disclosed_value is not None:
            coverage = "covered"
            details = f"{standard_name}: adequately addressed in the provided description."
        elif claim and claim.confidence >= 0.3:
            coverage = "partial"
            details = f"{standard_name}: partially mentioned but key metrics or figures are missing."
        else:
            coverage = "not_covered"
            details = f"{standard_name}: no relevant information found in the provided text."

        coverage_items.append({
            "esrs_id": esrs_id,
            "standard_name": standard_name,
            "coverage": coverage,
            "details": details,
        })
    return coverage_items


def _compute_cost_estimate(esrs_coverage: list[dict]) -> dict:
    """Compute compliance cost estimate range for compliance check mode."""
    not_covered_count = sum(1 for c in esrs_coverage if c["coverage"] == "not_covered")
    partial_count = sum(1 for c in esrs_coverage if c["coverage"] == "partial")
    total = len(esrs_coverage) if esrs_coverage else 1
    severity = (not_covered_count * 1.0 + partial_count * 0.5) / total
    industry_multiplier = 2.0  # tech/infrastructure default

    return {
        "estimated_range_low_eur": round(500_000 * severity * industry_multiplier, 2),
        "estimated_range_high_eur": round(2_000_000 * severity * industry_multiplier, 2),
        "basis": "Art. 51 CSRD Directive (EU) 2022/2464 — indicative range based on disclosure gaps",
        "caveat": (
            "This estimate is based on incomplete, unstructured data and should "
            "not be used for financial planning. A full audit with structured XHTML/iXBRL "
            "management report data is required for accurate compliance cost assessment."
        ),
    }


# ── Main node function ───────────────────────────────────────────────────────

def auditor_node(state: AuditState) -> dict[str, Any]:
    """Real auditor: Claude API call with double materiality scoring (both modes).

    Full audit:       esrs_claims + taxonomy_financials → esrs_ledger, taxonomy_alignment, compliance_cost
    Compliance check: esrs_claims + extracted_goals → esrs_coverage, compliance_cost_estimate
    """
    started_at = time.time()
    mode = state.get("mode", "full_audit")

    logs: list[dict] = list(state.get("logs") or [])
    pipeline_trace: list[dict] = list(state.get("pipeline_trace") or [])

    ts = lambda: int(time.time() * 1000)  # noqa: E731

    if mode == "compliance_check":
        return _run_compliance_check(state, logs, pipeline_trace, ts, started_at)

    return _run_full_audit(state, logs, pipeline_trace, ts, started_at)


def _run_full_audit(
    state: AuditState,
    logs: list[dict],
    pipeline_trace: list[dict],
    ts,
    started_at: float,
) -> dict[str, Any]:
    """Full audit path: Claude scores materiality, falls back to deterministic."""
    logs.append({"agent": "auditor", "msg": "Applying double materiality scoring framework...", "ts": ts()})

    esrs_claims: dict[str, ESRSClaim] = state.get("esrs_claims") or {}
    tf: Optional[TaxonomyFinancials] = state.get("taxonomy_financials")

    # Always compute taxonomy alignment deterministically (it's a formula, not LLM judgment)
    capex_aligned_pct, taxonomy_status, taxonomy_label = _compute_taxonomy_alignment(tf)
    taxonomy_alignment = TaxonomyAlignment(
        capex_aligned_pct=capex_aligned_pct,
        status=taxonomy_status,
        label=taxonomy_label,
    )

    financial_score = _score_financial_materiality(tf)

    # Try Claude API for nuanced scoring + evidence generation
    esrs_ledger = None
    try:
        logs.append({"agent": "auditor", "msg": "Calling Claude for double materiality assessment...", "ts": ts()})
        client = Anthropic()

        # Build input payload
        claims_payload = {}
        for esrs_id, claim in esrs_claims.items():
            claims_payload[esrs_id] = claim.model_dump() if hasattr(claim, "model_dump") else {
                "standard": claim.standard,
                "data_point": claim.data_point,
                "disclosed_value": claim.disclosed_value,
                "unit": claim.unit,
                "confidence": claim.confidence,
                "xbrl_concept": claim.xbrl_concept,
            }

        tf_payload = tf.model_dump() if tf and hasattr(tf, "model_dump") else (
            {"capex_total_eur": None, "capex_green_eur": None, "revenue_eur": None}
        )

        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT_AUDITOR,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": f"ESRS Claims:\n{json.dumps(claims_payload, indent=2)}"},
                    {
                        "type": "text",
                        "text": f"Taxonomy Financials:\n{json.dumps(tf_payload, indent=2)}",
                        "cache_control": {"type": "ephemeral"},
                    },
                    {"type": "text", "text": "Score each standard and output the JSON."},
                ],
            }],
        )

        raw_text = response.content[0].text
        parsed = _parse_llm_json(raw_text)
        esrs_ledger = _build_ledger_from_llm(parsed, financial_score)

        # Validate: must have exactly 3 items
        if len(esrs_ledger) != 3:
            logs.append({"agent": "auditor", "msg": f"LLM returned {len(esrs_ledger)} ledger items, expected 3. Falling back to deterministic.", "ts": ts()})
            esrs_ledger = None

        logs.append({"agent": "auditor", "msg": "Claude materiality assessment received.", "ts": ts()})

    except Exception as exc:
        logs.append({"agent": "auditor", "msg": f"Error calling Claude API: {exc}. Using deterministic scoring.", "ts": ts()})
        esrs_ledger = None

    # Fallback: deterministic scoring
    if esrs_ledger is None:
        logs.append({"agent": "auditor", "msg": "Computing deterministic double materiality scores...", "ts": ts()})
        esrs_ledger = _build_ledger_deterministic(esrs_claims, tf)

    logs.append({"agent": "auditor", "msg": "Computing EU Taxonomy alignment percentage...", "ts": ts()})

    # Compliance cost
    revenue_eur = (tf.revenue_eur if tf and tf.revenue_eur else 250_000_000.0)
    compliance_cost = _compute_compliance_cost(esrs_ledger, revenue_eur)

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


def _run_compliance_check(
    state: AuditState,
    logs: list[dict],
    pipeline_trace: list[dict],
    ts,
    started_at: float,
) -> dict[str, Any]:
    """Compliance check path: Claude assesses coverage, falls back to deterministic."""
    logs.append({"agent": "auditor", "msg": "Assessing ESRS E1 coverage from free-text claims...", "ts": ts()})

    esrs_claims: dict[str, ESRSClaim] = state.get("esrs_claims") or {}
    extracted_goals = state.get("extracted_goals") or []

    esrs_coverage = None
    compliance_cost_estimate = None

    try:
        logs.append({"agent": "auditor", "msg": "Calling Claude for coverage assessment...", "ts": ts()})
        client = Anthropic()

        claims_payload = {}
        for esrs_id, claim in esrs_claims.items():
            claims_payload[esrs_id] = claim.model_dump() if hasattr(claim, "model_dump") else {
                "standard": claim.standard,
                "data_point": claim.data_point,
                "disclosed_value": claim.disclosed_value,
                "unit": claim.unit,
                "confidence": claim.confidence,
            }

        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT_AUDITOR_LITE,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": f"ESRS Claims:\n{json.dumps(claims_payload, indent=2)}"},
                    {
                        "type": "text",
                        "text": f"Extracted Goals:\n{json.dumps(extracted_goals, indent=2)}",
                        "cache_control": {"type": "ephemeral"},
                    },
                    {"type": "text", "text": "Assess coverage and output the JSON."},
                ],
            }],
        )

        raw_text = response.content[0].text
        parsed = _parse_llm_json(raw_text)

        esrs_coverage = parsed.get("esrs_coverage")
        raw_cost = parsed.get("compliance_cost_estimate")

        # Validate coverage: must have 3 items with valid fields
        if not esrs_coverage or len(esrs_coverage) != 3:
            esrs_coverage = None
        else:
            valid_coverage_levels = {"covered", "partial", "not_covered"}
            for item in esrs_coverage:
                if item.get("coverage") not in valid_coverage_levels:
                    esrs_coverage = None
                    break

        if raw_cost and all(k in raw_cost for k in ("estimated_range_low_eur", "estimated_range_high_eur", "basis", "caveat")):
            compliance_cost_estimate = raw_cost
        else:
            compliance_cost_estimate = None

        logs.append({"agent": "auditor", "msg": "Claude coverage assessment received.", "ts": ts()})

    except Exception as exc:
        logs.append({"agent": "auditor", "msg": f"Error calling Claude API: {exc}. Using deterministic assessment.", "ts": ts()})

    # Fallback: deterministic
    if esrs_coverage is None:
        logs.append({"agent": "auditor", "msg": "Classifying coverage: covered / partial / not_covered...", "ts": ts()})
        esrs_coverage = _build_coverage_deterministic(esrs_claims)

    if compliance_cost_estimate is None:
        logs.append({"agent": "auditor", "msg": "Estimating compliance cost range...", "ts": ts()})
        compliance_cost_estimate = _compute_cost_estimate(esrs_coverage)

    duration_ms = int((time.time() - started_at) * 1000)
    pipeline_trace.append({"agent": "auditor", "started_at": started_at, "ms": duration_ms})
    logs.append({"agent": "auditor", "msg": f"Coverage assessment complete in {duration_ms}ms", "ts": ts()})

    return {
        "esrs_coverage": esrs_coverage,
        "compliance_cost_estimate": compliance_cost_estimate,
        "logs": logs,
        "pipeline_trace": pipeline_trace,
    }
