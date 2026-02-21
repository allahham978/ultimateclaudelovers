"""
Node 2 — Financial Extractor (Fetcher) — Real Claude API implementation.

Reads: state["taxonomy_data"] (Taxonomy-tagged iXBRL sections from report JSON)
Writes: state["taxonomy_financials"], state["document_source"]

Uses Claude claude-sonnet-4-6 with SYSTEM_PROMPT_FETCHER and prompt caching on taxonomy data.
Only runs in full_audit mode — skipped entirely in compliance_check mode.
"""

import json
import re
import time
from typing import Any

import anthropic

from schemas import RegistrySource, TaxonomyFinancials
from state import AuditState
from tools.prompts import SYSTEM_PROMPT_FETCHER

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 4096

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


def _build_taxonomy_financials(raw: dict) -> TaxonomyFinancials:
    """Construct a TaxonomyFinancials from Claude's parsed JSON response.

    Handles missing fields gracefully with None defaults.
    """
    return TaxonomyFinancials(
        capex_total_eur=raw.get("capex_total_eur"),
        capex_green_eur=raw.get("capex_green_eur"),
        opex_total_eur=raw.get("opex_total_eur"),
        opex_green_eur=raw.get("opex_green_eur"),
        revenue_eur=raw.get("revenue_eur"),
        fiscal_year=str(raw.get("fiscal_year", "Unknown")),
        taxonomy_activities=raw.get("taxonomy_activities", []),
        source_document=raw.get("source_document", "Annual Management Report — Taxonomy Section"),
        confidence=float(raw.get("confidence", 0.0)),
    )


def _safe_defaults() -> TaxonomyFinancials:
    """Return safe fallback TaxonomyFinancials when the API call or parsing fails."""
    return TaxonomyFinancials(
        capex_total_eur=None,
        capex_green_eur=None,
        opex_total_eur=None,
        opex_green_eur=None,
        revenue_eur=None,
        fiscal_year="Unknown",
        taxonomy_activities=[],
        source_document="Annual Management Report — Taxonomy Section",
        confidence=0.0,
    )


# ---------------------------------------------------------------------------
# Node function
# ---------------------------------------------------------------------------


def fetcher_node(state: AuditState) -> dict[str, Any]:
    """Real Fetcher node: calls Claude API to extract Taxonomy financials from iXBRL data.

    Reads state["taxonomy_data"] and sends it to Claude with SYSTEM_PROMPT_FETCHER.
    Parses the JSON response into a TaxonomyFinancials Pydantic model.
    On error, logs the failure and returns safe defaults — never halts the graph.
    """
    started_at = time.time()

    logs: list[dict] = list(state.get("logs") or [])
    pipeline_trace: list[dict] = list(state.get("pipeline_trace") or [])

    ts = lambda: int(time.time() * 1000)  # noqa: E731

    logs.append({"agent": "fetcher", "msg": "Reading Taxonomy sections from management report JSON...", "ts": ts()})

    taxonomy_data = state.get("taxonomy_data", {})
    logs.append({"agent": "fetcher", "msg": f"Taxonomy data contains {len(json.dumps(taxonomy_data))} chars of structured iXBRL JSON", "ts": ts()})

    # ── Call Claude API ───────────────────────────────────────────────────
    logs.append({"agent": "fetcher", "msg": "Sending Taxonomy data to Claude for CapEx/OpEx/Revenue extraction...", "ts": ts()})

    try:
        client = anthropic.Anthropic()

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "TAXONOMY SECTIONS FROM ANNUAL MANAGEMENT REPORT (iXBRL JSON):\n\n"},
                    {
                        "type": "text",
                        "text": json.dumps(taxonomy_data, indent=2),
                        "cache_control": {"type": "ephemeral"},
                    },
                    {"type": "text", "text": "\n\nExtract all CapEx, OpEx, and Revenue alignment data."},
                ],
            }
        ]

        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT_FETCHER,
            messages=messages,
        )

        raw_text = response.content[0].text
        logs.append({"agent": "fetcher", "msg": "Claude response received, parsing JSON...", "ts": ts()})

        # ── Parse response ────────────────────────────────────────────────
        parsed = _parse_llm_json(raw_text)

        # Claude may nest the result under "taxonomy_financials" or return flat
        financials_data = parsed.get("taxonomy_financials", parsed)
        taxonomy_financials = _build_taxonomy_financials(financials_data)

        logs.append({
            "agent": "fetcher",
            "msg": f"Extracted: CapEx total={taxonomy_financials.capex_total_eur}, "
                   f"CapEx green={taxonomy_financials.capex_green_eur}, "
                   f"Revenue={taxonomy_financials.revenue_eur}, "
                   f"confidence={taxonomy_financials.confidence}",
            "ts": ts(),
        })

    except Exception as exc:
        logs.append({"agent": "fetcher", "msg": f"Error calling Claude API: {exc}", "ts": ts()})
        taxonomy_financials = _safe_defaults()

    # ── Build document source ─────────────────────────────────────────────
    document_source = RegistrySource(
        name="Annual Management Report",
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
