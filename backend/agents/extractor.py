"""
Node 1 — ESRS Reader (Extractor) — Real Claude API implementation (v5.0 unified).

structured_document: Sends esrs_data + taxonomy_data to Claude in one call →
                     esrs_claims (ALL ESRS standards) + company_meta + financial_context
free_text:           Sends free_text_input to Claude →
                     esrs_claims (ALL identifiable ESRS standards) + company_meta (financial_context=None)

Uses Claude claude-sonnet-4-6 with prompt caching on iXBRL data.
"""

import json
import re
import time
from typing import Any, Optional

import anthropic

from schemas import CompanyMeta, ESRSClaim, FinancialContext
from state import AuditState
from tools.prompts import SYSTEM_PROMPT_EXTRACTOR, SYSTEM_PROMPT_EXTRACTOR_LITE

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 8192


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_llm_json(raw_text: str) -> dict:
    """Parse JSON from Claude's response, handling markdown fences and whitespace.

    Raises json.JSONDecodeError if no valid JSON can be extracted.
    """
    text = raw_text.strip()

    # Strip markdown code fences: ```json ... ``` or ``` ... ```
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    return json.loads(text)


def _build_esrs_claims(raw_claims: dict) -> dict[str, ESRSClaim]:
    """Construct ESRSClaim dict from Claude's parsed JSON response.

    Handles missing fields gracefully with defaults.
    """
    claims: dict[str, ESRSClaim] = {}
    for esrs_id, claim_data in raw_claims.items():
        claims[esrs_id] = ESRSClaim(
            standard=esrs_id,
            data_point=claim_data.get("data_point", ""),
            disclosed_value=claim_data.get("disclosed_value"),
            unit=claim_data.get("unit"),
            confidence=float(claim_data.get("confidence", 0.0)),
            xbrl_concept=claim_data.get("xbrl_concept"),
        )
    return claims


def _build_company_meta(raw_meta: dict, fallback_entity: str) -> CompanyMeta:
    """Construct CompanyMeta from Claude's parsed JSON response."""
    return CompanyMeta(
        name=raw_meta.get("name") or fallback_entity,
        lei=raw_meta.get("lei"),
        sector=raw_meta.get("sector") or "Unknown",
        fiscal_year=int(raw_meta.get("fiscal_year") or 2024),
        jurisdiction=raw_meta.get("jurisdiction") or "EU",
        report_title=raw_meta.get("report_title") or "Unknown Report",
    )


def _build_financial_context(raw_fc: Optional[dict]) -> Optional[FinancialContext]:
    """Construct FinancialContext from Claude's parsed JSON response.

    Returns None if raw_fc is None or empty.
    """
    if not raw_fc:
        return None
    return FinancialContext(
        capex_total_eur=raw_fc.get("capex_total_eur"),
        capex_green_eur=raw_fc.get("capex_green_eur"),
        opex_total_eur=raw_fc.get("opex_total_eur"),
        opex_green_eur=raw_fc.get("opex_green_eur"),
        revenue_eur=raw_fc.get("revenue_eur"),
        taxonomy_activities=raw_fc.get("taxonomy_activities", []),
        confidence=float(raw_fc.get("confidence", 0.0)),
    )


def _safe_defaults(entity_id: str, mode: str) -> dict[str, Any]:
    """Return safe fallback extractor output when API call or parsing fails."""
    return {
        "company_meta": CompanyMeta(
            name=entity_id or "Unknown Entity",
            lei=None,
            sector="Unknown",
            fiscal_year=2024,
            jurisdiction="EU",
            report_title="User-Provided Sustainability Description"
            if mode == "free_text"
            else "Annual Management Report",
        ),
        "esrs_claims": {},
        "financial_context": None,
    }


# ---------------------------------------------------------------------------
# Node function
# ---------------------------------------------------------------------------


def extractor_node(state: AuditState) -> dict[str, Any]:
    """Real Extractor node: calls Claude API to extract ESRS claims from input.

    Structured document mode:
      - Sends BOTH esrs_data + taxonomy_data to Claude in one call
      - Extracts claims for ALL ESRS standards found (E1-E5, S1-S4, G1, ESRS 2)
      - Extracts financial_context (CapEx/OpEx/Revenue) from taxonomy data

    Free text mode:
      - Sends free_text_input to Claude
      - Extracts all identifiable ESRS claims from prose
      - financial_context is always None

    On error, logs the failure and returns safe defaults — never halts the graph.
    """
    started_at = time.time()
    mode = state.get("mode", "structured_document")
    entity_id = state.get("entity_id") or "Unknown Entity"

    logs: list[dict] = list(state.get("logs") or [])
    pipeline_trace: list[dict] = list(state.get("pipeline_trace") or [])

    ts = lambda: int(time.time() * 1000)  # noqa: E731

    if mode == "free_text":
        # ── Free text mode ────────────────────────────────────────────────
        free_text = state.get("free_text_input", "")
        logs.append({"agent": "extractor", "msg": "Reading free-text sustainability description...", "ts": ts()})
        logs.append({"agent": "extractor", "msg": f"Input text: {len(free_text)} characters", "ts": ts()})
        logs.append({"agent": "extractor", "msg": "Sending text to Claude for ESRS claim extraction...", "ts": ts()})

        try:
            client = anthropic.Anthropic()

            messages = [
                {
                    "role": "user",
                    "content": (
                        f"COMPANY SUSTAINABILITY DESCRIPTION:\n\n{free_text}\n\n"
                        "Extract all identifiable ESRS claims and company metadata as specified."
                    ),
                }
            ]

            response = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT_EXTRACTOR_LITE,
                messages=messages,
            )

            raw_text = response.content[0].text
            logs.append({"agent": "extractor", "msg": "Claude response received, parsing JSON...", "ts": ts()})

            parsed = _parse_llm_json(raw_text)

            company_meta = _build_company_meta(parsed.get("company_meta", {}), entity_id)
            esrs_claims = _build_esrs_claims(parsed.get("esrs_claims", {}))

            logs.append({
                "agent": "extractor",
                "msg": f"Extracted {len(esrs_claims)} ESRS claims from free text",
                "ts": ts(),
            })

        except Exception as exc:
            logs.append({"agent": "extractor", "msg": f"Error calling Claude API: {exc}", "ts": ts()})
            defaults = _safe_defaults(entity_id, mode)
            company_meta = defaults["company_meta"]
            esrs_claims = defaults["esrs_claims"]

        duration_ms = int((time.time() - started_at) * 1000)
        pipeline_trace.append({"agent": "extractor", "started_at": started_at, "ms": duration_ms})
        logs.append({"agent": "extractor", "msg": f"Extraction complete in {duration_ms}ms", "ts": ts()})

        return {
            "company_meta": company_meta,
            "esrs_claims": esrs_claims,
            "logs": logs,
            "pipeline_trace": pipeline_trace,
        }

    # ── Structured document mode (default) ────────────────────────────────
    esrs_data = state.get("esrs_data", {})
    taxonomy_data = state.get("taxonomy_data", {})

    logs.append({"agent": "extractor", "msg": "Reading ESRS + Taxonomy sections from management report JSON...", "ts": ts()})
    logs.append({
        "agent": "extractor",
        "msg": f"ESRS data: {len(json.dumps(esrs_data))} chars, Taxonomy data: {len(json.dumps(taxonomy_data))} chars",
        "ts": ts(),
    })
    logs.append({"agent": "extractor", "msg": "Sending iXBRL data to Claude for all ESRS standards + financial context...", "ts": ts()})

    try:
        client = anthropic.Anthropic()

        # Send BOTH ESRS and Taxonomy data in one call with prompt caching
        content_parts = [
            {"type": "text", "text": "ESRS SECTIONS FROM ANNUAL MANAGEMENT REPORT (iXBRL JSON):\n\n"},
            {
                "type": "text",
                "text": json.dumps(esrs_data, indent=2),
                "cache_control": {"type": "ephemeral"},
            },
            {"type": "text", "text": "\n\nTAXONOMY SECTIONS (iXBRL JSON):\n\n"},
            {
                "type": "text",
                "text": json.dumps(taxonomy_data, indent=2),
                "cache_control": {"type": "ephemeral"},
            },
            {"type": "text", "text": "\n\nExtract all ESRS data points and financial context as specified."},
        ]

        messages = [{"role": "user", "content": content_parts}]

        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT_EXTRACTOR,
            messages=messages,
        )

        raw_text = response.content[0].text
        logs.append({"agent": "extractor", "msg": "Claude response received, parsing JSON...", "ts": ts()})

        parsed = _parse_llm_json(raw_text)

        company_meta = _build_company_meta(parsed.get("company_meta", {}), entity_id)
        esrs_claims = _build_esrs_claims(parsed.get("esrs_claims", {}))
        financial_context = _build_financial_context(parsed.get("financial_context"))

        logs.append({
            "agent": "extractor",
            "msg": f"Extracted {len(esrs_claims)} ESRS claims + financial context "
                   f"(CapEx={financial_context.capex_total_eur if financial_context else 'N/A'}, "
                   f"Revenue={financial_context.revenue_eur if financial_context else 'N/A'})",
            "ts": ts(),
        })

    except Exception as exc:
        logs.append({"agent": "extractor", "msg": f"Error calling Claude API: {exc}", "ts": ts()})
        defaults = _safe_defaults(entity_id, mode)
        company_meta = defaults["company_meta"]
        esrs_claims = defaults["esrs_claims"]
        financial_context = defaults["financial_context"]

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
