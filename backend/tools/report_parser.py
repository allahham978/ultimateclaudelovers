"""
Report Parser — JSON cleaning + section routing.

Replaces pdf_reader.py. Receives the pre-parsed JSON from the XHTML→JSON converter
(built by Data Lead B), cleans junk data, and routes sections to the appropriate agents.

Called once during POST /audit/run before the graph is invoked.
The router splits iXBRL concept names to separate ESRS vs. Taxonomy sections.
"""

from typing import Any

# ---------------------------------------------------------------------------
# Junk patterns — artifacts of XHTML→JSON conversion that are not iXBRL content
# ---------------------------------------------------------------------------

JUNK_PATTERNS = [
    "Content-Security-Policy",
    "script-src",
    "unsafe-eval",
    "text/javascript",
    "text/css",
    "<style",
    "<script",
    "noscript",
]

# ---------------------------------------------------------------------------
# iXBRL concept name prefixes used to identify ESRS E1 sections
# ---------------------------------------------------------------------------

ESRS_E1_PREFIXES = (
    "esrs_e1-1",
    "esrs_e1-5",
    "esrs_e1-6",
    "esrs:e1-1",
    "esrs:e1-5",
    "esrs:e1-6",
    # Entity identification concepts present in the sustainability statement
    "esrs_generalinformation",
    "esrs:generalinformation",
    "lei",
    "ifrs-full:nameofreportingentity",
    "ifrs-full:addressofregisteredoffice",
    "ifrs-full:descriptionofnatureofentitysmainactivities",
    "ifrs-full:jurisdictionofincorporation",
)

# ---------------------------------------------------------------------------
# iXBRL concept name prefixes used to identify EU Taxonomy (Art. 8) sections
# ---------------------------------------------------------------------------

TAXONOMY_PREFIXES = (
    "eutaxonomy",
    "eu-taxonomy",
    "taxonomyeligibility",
    "taxonomyalignment",
    # Standard financial tags that appear in the Taxonomy Table
    "ifrs-full:capitalexpenditures",
    "ifrs-full:revenue",
    "ifrs-full:operatingexpense",
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def clean_report_json(raw_json: dict) -> dict:
    """Strip non-content junk from XHTML→JSON output.

    Removes:
    - Script/style elements and CSP metadata
    - Empty text nodes and whitespace-only entries
    - Browser rendering artifacts (DOM inspector output, console errors)
    - Navigation/header chrome elements

    Args:
        raw_json: Raw JSON from the XHTML→JSON converter.

    Returns:
        Cleaned JSON with only iXBRL content nodes preserved.
    """
    if not isinstance(raw_json, dict):
        return {}

    cleaned: dict = {}

    for key, value in raw_json.items():
        # Skip keys whose names contain junk patterns
        if _contains_junk(str(key)):
            continue

        if isinstance(value, dict):
            # Recurse into nested dicts
            cleaned_child = clean_report_json(value)
            if cleaned_child:  # drop empty dicts produced by full junk subtrees
                cleaned[key] = cleaned_child
        elif isinstance(value, list):
            cleaned_list = _clean_list(value)
            if cleaned_list is not None:
                cleaned[key] = cleaned_list
        elif isinstance(value, str):
            # Drop whitespace-only strings and junk string values
            stripped = value.strip()
            if stripped and not _contains_junk(stripped):
                cleaned[key] = stripped
        else:
            # int, float, bool, None — keep as-is
            cleaned[key] = value

    return cleaned


def extract_esrs_sections(report: dict) -> dict:
    """Extract iXBRL nodes tagged with ESRS taxonomy concepts.

    Filters for concept names matching ESRS E1 patterns:
    - esrs_e1-1_* (Transition Plan)
    - esrs_e1-5_* (Energy)
    - esrs_e1-6_* (GHG Emissions)
    Plus entity identification concepts (LEI, company name, jurisdiction).

    Args:
        report: Cleaned report JSON.

    Returns:
        Dict of ESRS-tagged iXBRL nodes for the Extractor agent.
    """
    return _filter_by_concept(report, ESRS_E1_PREFIXES)


def extract_taxonomy_sections(report: dict) -> dict:
    """Extract iXBRL nodes tagged with EU Taxonomy concepts.

    Filters for Taxonomy Regulation financial data:
    - CapEx alignment tags (total, aligned, eligible)
    - OpEx alignment tags
    - Revenue/turnover tags
    - Activity code classification tags (NACE references)

    Args:
        report: Cleaned report JSON.

    Returns:
        Dict of Taxonomy-tagged iXBRL nodes for the Fetcher agent.
    """
    return _filter_by_concept(report, TAXONOMY_PREFIXES)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _contains_junk(text: str) -> bool:
    """Return True if *text* matches any known junk pattern."""
    lower = text.lower()
    return any(pattern.lower() in lower for pattern in JUNK_PATTERNS)


def _clean_list(items: list) -> list | None:
    """Recursively clean a list value. Returns None if all items were junk."""
    result = []
    for item in items:
        if isinstance(item, dict):
            cleaned = clean_report_json(item)
            if cleaned:
                result.append(cleaned)
        elif isinstance(item, list):
            cleaned_sub = _clean_list(item)
            if cleaned_sub is not None:
                result.append(cleaned_sub)
        elif isinstance(item, str):
            stripped = item.strip()
            if stripped and not _contains_junk(stripped):
                result.append(stripped)
        else:
            result.append(item)
    return result if result else None


def _filter_by_concept(report: dict, prefixes: tuple[str, ...]) -> dict:
    """Walk the report JSON and collect nodes whose 'concept' key matches any prefix.

    Handles two common shapes produced by the XHTML→JSON converter:

    Shape A — flat dict of concept-keyed records:
        { "esrs_e1-1_01": { "value": "...", "unit": "...", ... }, ... }

    Shape B — list of tagged nodes under a top-level key:
        { "facts": [ { "concept": "esrs_e1-1_01", "value": "...", ... }, ... ] }

    Returns a flat dict keyed by concept name for easy consumption by agents.
    """
    result: dict[str, Any] = {}

    _collect_matching_nodes(report, prefixes, result)

    return result


def _collect_matching_nodes(
    node: Any,
    prefixes: tuple[str, ...],
    accumulator: dict[str, Any],
) -> None:
    """Recursively traverse *node* and collect matching iXBRL entries into *accumulator*."""
    if isinstance(node, dict):
        # Shape A: the dict key IS the concept name
        concept = str(node.get("concept", "")).lower()
        if concept and _matches_prefix(concept, prefixes):
            # Store under the concept key, merging if duplicate concepts appear
            accumulator[node["concept"]] = node
            return  # don't recurse deeper into a matched node

        for key, value in node.items():
            key_lower = key.lower()
            # Shape A (flat): the dict key itself is the concept
            if _matches_prefix(key_lower, prefixes) and isinstance(value, dict):
                accumulator[key] = value
            else:
                _collect_matching_nodes(value, prefixes, accumulator)

    elif isinstance(node, list):
        for item in node:
            _collect_matching_nodes(item, prefixes, accumulator)


def _matches_prefix(concept: str, prefixes: tuple[str, ...]) -> bool:
    """Return True if *concept* starts with any of the given prefixes (case-insensitive)."""
    return any(concept.startswith(prefix.lower()) for prefix in prefixes)
