"""
Report Parser — JSON cleaning + section routing for the Annual Management Report.

Pipeline:
  1. extract_xhtml_to_json()            — parse XHTML/iXBRL to structured JSON
  2. clean_report_json()                — strip junk data (CSP errors, scripts, empty nodes)
  3. extract_esrs_sections()            — filter ESRS-tagged iXBRL facts for Extractor agent
  4. extract_taxonomy_sections()        — filter Taxonomy-tagged iXBRL facts for Extractor
  5. extract_narrative_sustainability()  — extract untagged sustainability narrative from HTML
  6. summarize_narrative_sections()     — chunk/prioritize narrative to fit context window
"""

import json
import re
from typing import Any

from lxml import etree


# ── Stage 1: XHTML → JSON extraction (engineer's iXBRL parser) ──────────────

def extract_xhtml_to_json(file_path: str) -> dict:
    """Parse an XHTML/iXBRL file and extract all tagged facts to structured JSON.

    Preserves: concept name, value, unit, context, decimals, scale per fact.
    Stitches ix:continuation chains into their parent ix:nonNumeric facts.

    Args:
        file_path: Path to the XHTML file on disk.

    Returns:
        Dict with "report_info" metadata and "facts" list of iXBRL-tagged values.
    """
    extracted_data: dict[str, Any] = {
        "report_info": {"source": file_path},
        "facts": [],
    }

    # Parse the full tree with huge_tree=True to handle large XHTML files (e.g. 80MB+)
    parser = etree.XMLParser(huge_tree=True)
    tree = etree.parse(file_path, parser)
    root = tree.getroot()

    # Collect ix:continuation elements first (id → {text, continuedAt})
    continuation_map: dict[str, dict[str, str]] = {}
    for ns in root.nsmap.values():
        if ns:
            for cont_elem in root.iter(f"{{{ns}}}continuation"):
                cont_id = cont_elem.get("id")
                if cont_id:
                    text = etree.tostring(cont_elem, method="text", encoding="unicode").strip()
                    continuation_map[cont_id] = {
                        "text": text,
                        "continuedAt": cont_elem.get("continuedAt"),
                    }

    # Find all ix:nonFraction and ix:nonNumeric elements across any namespace
    ns_tags = []
    for ns in root.nsmap.values():
        if ns:
            ns_tags.append(f"{{{ns}}}nonFraction")
            ns_tags.append(f"{{{ns}}}nonNumeric")

    elements = []
    for tag in ns_tags:
        elements.extend(root.iter(tag))

    for elem in elements:
        is_numeric = "nonFraction" in elem.tag

        fact: dict[str, Any] = {
            "ix_type": "ix:nonFraction" if is_numeric else "ix:nonNumeric",
            "concept": elem.get("name"),
            "context_ref": elem.get("contextRef"),
            "value": elem.text.strip() if elem.text else "",
        }

        if is_numeric:
            fact.update({
                "unit_ref": elem.get("unitRef"),
                "decimals": elem.get("decimals"),
                "scale": elem.get("scale"),
            })
        else:
            if len(elem) > 0:
                fact["html_inner"] = etree.tostring(elem, encoding="unicode", method="html")

            # Stitch ix:continuation chains into nonNumeric value
            continued_at = elem.get("continuedAt")
            parts = []
            while continued_at and continued_at in continuation_map:
                entry = continuation_map[continued_at]
                if entry["text"]:
                    parts.append(entry["text"])
                continued_at = entry.get("continuedAt")
            if parts:
                fact["value"] = (fact["value"] + " " + " ".join(parts)).strip()

        extracted_data["facts"].append(fact)

    return extracted_data


# ── Stage 2: JSON cleaning ──────────────────────────────────────────────────

# Patterns that indicate browser/rendering junk, not report content
_JUNK_PATTERNS = re.compile(
    r"Content.Security.Policy|script-src|unsafe-eval|text/javascript|"
    r"text/css|<script|<style|noscript|\.js$|\.css$",
    re.IGNORECASE,
)


def clean_report_json(raw_json: dict) -> dict:
    """Strip non-content junk from XHTML→JSON output.

    Removes:
    - Facts with no concept name (untagged content)
    - Facts whose value is only whitespace or empty
    - Facts whose value matches browser artifact patterns (CSP errors, script refs)

    Args:
        raw_json: Raw JSON from extract_xhtml_to_json or the engineer's converter.

    Returns:
        Cleaned JSON with only meaningful iXBRL facts preserved.
    """
    raw_facts = raw_json.get("facts", [])

    clean_facts = []
    for fact in raw_facts:
        concept = fact.get("concept")
        if not concept:
            continue

        value = fact.get("value", "")
        if not value or not value.strip():
            # Keep numeric facts with scale/unit even if value looks empty
            if fact.get("ix_type") != "ix:nonFraction":
                continue

        if _JUNK_PATTERNS.search(value):
            continue

        clean_facts.append(fact)

    return {
        "report_info": raw_json.get("report_info", {}),
        "facts": clean_facts,
    }


# ── Stage 3: Section routing ────────────────────────────────────────────────

# ESRS concept patterns — matches ESRS taxonomy concept names
_ESRS_PATTERNS = re.compile(
    r"esrs[_:]|"                     # ESRS namespace prefix
    r"E[1-5][-_]|S[1-4][-_]|G1[-_]|"  # ALL ESRS standard IDs
    r"GOV[-_]|SBM[-_]|IRO[-_]|"     # ESRS 2 general disclosures
    r"GrossScope|Scope[123]|"         # GHG emissions concepts
    r"GHG|ghg|"                       # GHG references
    r"EnergyConsumption|RenewableEnergy|"  # Energy concepts
    r"TransitionPlan|NetZero|"        # Transition plan concepts
    r"Decarboni[sz]ation",            # Decarbonisation variants
    re.IGNORECASE,
)

# Taxonomy financial concept patterns — matches EU Taxonomy Regulation concepts
_TAXONOMY_PATTERNS = re.compile(
    r"taxonomy[_:]|eutaxonomy|"       # Taxonomy namespace
    r"CapEx|Capex|CAPEX|"             # Capital expenditure
    r"OpEx|Opex|OPEX|"               # Operating expenditure
    r"[Rr]evenue|[Tt]urnover|"       # Revenue/turnover
    r"[Aa]ligned|[Ee]ligible|"       # Alignment status
    r"Activity[_\s]?[0-9]|"          # Taxonomy activity codes
    r"NACE|nace",                     # NACE activity references
    re.IGNORECASE,
)

# Company metadata concept patterns
_ENTITY_PATTERNS = re.compile(
    r"EntityName|LegalName|LEI|"
    r"NameOfReportingEntity|"
    r"CountryOfIncorporation|Jurisdiction|"
    r"ReportingPeriod|FiscalYear|"
    r"ifrs-full:NameOf|"
    r"NameOfUltimateParent",
    re.IGNORECASE,
)


def extract_esrs_sections(report: dict) -> dict:
    """Extract iXBRL facts tagged with ESRS or entity metadata concepts.

    Args:
        report: Cleaned report JSON from clean_report_json().

    Returns:
        Dict with "facts" list filtered to ESRS-relevant and entity metadata facts.
    """
    facts = report.get("facts", [])

    esrs_facts = []
    for fact in facts:
        concept = fact.get("concept", "")
        if _ESRS_PATTERNS.search(concept) or _ENTITY_PATTERNS.search(concept):
            esrs_facts.append(fact)

    return {"facts": esrs_facts}


def extract_taxonomy_sections(report: dict) -> dict:
    """Extract iXBRL facts tagged with EU Taxonomy financial concepts.

    Args:
        report: Cleaned report JSON from clean_report_json().

    Returns:
        Dict with "facts" list filtered to Taxonomy-relevant financial facts.
    """
    facts = report.get("facts", [])

    taxonomy_facts = []
    for fact in facts:
        concept = fact.get("concept", "")
        if _TAXONOMY_PATTERNS.search(concept):
            taxonomy_facts.append(fact)

    return {"facts": taxonomy_facts}


# ── Stage 5: Narrative sustainability extraction from HTML ─────────────────

_SUSTAINABILITY_HEADING_KEYWORDS = re.compile(
    r"sustainab|ESG|ESRS|climate|environment|social\s+(?:responsib|impact|statement)|"
    r"governance|taxonomy|emission|GHG|greenhouse|workforce|diversity|"
    r"biodiversity|circular\s+economy|pollution|water|energy\s+(?:consumption|transition)|"
    r"human\s+rights|anti[- ]corruption|stakeholder|non[- ]financial",
    re.IGNORECASE,
)

_SUSTAINABILITY_CONTENT_KEYWORDS = re.compile(
    r"sustainab|ESG|ESRS|climate|emission|carbon|GHG|greenhouse|"
    r"Scope\s*[123]|biodiversity|workforce|diversity|renewable|"
    r"circular\s+economy|pollution|water\s+consumption|taxonomy|"
    r"net[- ]zero|decarboni[sz]|transition\s+plan|gender\s+pay|"
    r"human\s+rights|anti[- ]corruption|health\s+and\s+safety|"
    r"CO2|tCO2|MWh|GWh",
    re.IGNORECASE,
)


def _get_font_size_pt(style: str) -> float | None:
    """Extract font-size in pt from a CSS style string."""
    match = re.search(r"font-size:\s*([\d.]+)\s*pt", style)
    if match:
        return float(match.group(1))
    return None


def _is_bold(style: str) -> bool:
    """Check if a CSS style string indicates bold text."""
    return bool(re.search(r"font-weight:\s*(bold|[7-9]\d\d)", style))


def extract_narrative_sustainability(file_path: str) -> list[dict]:
    """Extract untagged sustainability narrative text from the XHTML HTML structure.

    Identifies sustainability-related sections by scanning for heading elements
    (h1-h6, or styled divs/spans) that match sustainability keywords, then
    extracts all text content within those sections.

    Args:
        file_path: Path to the XHTML file on disk.

    Returns:
        List of section dicts: {"heading": str, "text": str, "char_count": int, "position": int}
    """
    parser = etree.XMLParser(huge_tree=True)
    tree = etree.parse(file_path, parser)
    root = tree.getroot()
    ns = "http://www.w3.org/1999/xhtml"

    # Strategy: walk all elements in document order, identify heading-like elements
    # that match sustainability keywords, then collect text until next heading.
    #
    # A "heading" is:
    #   1. An <h1>-<h6> element
    #   2. A <div>/<span>/<p> with font-size >= 14pt or font-weight bold, AND short text (<200 chars)

    all_elements = list(root.iter())

    # First pass: identify heading elements and their positions
    headings: list[tuple[int, int, str]] = []  # (position, level, text)

    for i, elem in enumerate(all_elements):
        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        text = "".join(elem.itertext()).strip()
        if not text or len(text) > 200:
            continue

        level = 0
        # Standard HTML headings
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(tag[1])
        # Styled heading detection for <div>/<span>/<p>
        elif tag in ("div", "span", "p"):
            style = elem.get("style", "")
            font_size = _get_font_size_pt(style)
            if font_size and font_size >= 16:
                level = 1
            elif font_size and font_size >= 14:
                level = 2
            elif font_size and font_size >= 12 and _is_bold(style):
                level = 3
            elif _is_bold(style) and len(text) < 100:
                level = 4

        if level > 0 and _SUSTAINABILITY_HEADING_KEYWORDS.search(text):
            headings.append((i, level, text))

    if not headings:
        return []

    # Second pass: for each sustainability heading, collect text until next same-or-higher heading
    sections: list[dict] = []

    for idx, (pos, level, heading_text) in enumerate(headings):
        # Find the end boundary: next heading at same or higher level
        if idx + 1 < len(headings):
            end_pos = headings[idx + 1][0]
        else:
            end_pos = len(all_elements)

        # Collect text from elements in this range
        section_texts: list[str] = []
        for j in range(pos, min(end_pos, pos + 5000)):  # Cap at 5000 elements per section
            elem = all_elements[j]
            # Only collect direct text (not recursively, to avoid duplication)
            if elem.text and elem.text.strip():
                section_texts.append(elem.text.strip())
            if elem.tail and elem.tail.strip():
                section_texts.append(elem.tail.strip())

        full_text = " ".join(section_texts)
        # Collapse excessive whitespace
        full_text = re.sub(r"\s{2,}", " ", full_text).strip()

        if len(full_text) < 50:
            continue

        sections.append({
            "heading": heading_text,
            "text": full_text,
            "char_count": len(full_text),
            "position": pos,
        })

    return sections


def summarize_narrative_sections(
    sections: list[dict], max_chars: int = 150_000
) -> list[dict]:
    """Prioritize and truncate narrative sections to fit within a character budget.

    Scores sections by sustainability keyword density, includes highest-scored
    sections first, and truncates if needed.

    Args:
        sections: Raw sections from extract_narrative_sustainability().
        max_chars: Maximum total characters across all sections.

    Returns:
        Prioritized and possibly truncated list of section dicts.
    """
    if not sections:
        return []

    # Score by keyword density
    for s in sections:
        s["keyword_score"] = len(_SUSTAINABILITY_CONTENT_KEYWORDS.findall(s["text"]))

    # Sort by keyword score descending for selection
    scored = sorted(sections, key=lambda s: s["keyword_score"], reverse=True)

    result: list[dict] = []
    remaining = max_chars
    for s in scored:
        if remaining <= 0:
            break
        if s["char_count"] <= remaining:
            result.append(s)
            remaining -= s["char_count"]
        elif remaining > 1000:
            truncated = {**s, "text": s["text"][:remaining], "truncated": True}
            result.append(truncated)
            remaining = 0

    # Re-sort by document order
    result.sort(key=lambda s: s["position"])
    return result


# ── Convenience: full pipeline ──────────────────────────────────────────────

def parse_report(
    raw_json: dict, file_path: str | None = None
) -> tuple[dict, dict, dict, list[dict]]:
    """Run the full cleaning + routing pipeline.

    Args:
        raw_json: Raw JSON from extract_xhtml_to_json or uploaded JSON file.
        file_path: Optional path to the original XHTML file for narrative extraction.

    Returns:
        Tuple of (cleaned_report, esrs_data, taxonomy_data, narrative_sections).
        narrative_sections is empty if file_path is None or no sustainability headings found.
    """
    cleaned = clean_report_json(raw_json)
    esrs_data = extract_esrs_sections(cleaned)
    taxonomy_data = extract_taxonomy_sections(cleaned)

    narrative_sections: list[dict] = []
    if file_path:
        raw_sections = extract_narrative_sustainability(file_path)
        narrative_sections = summarize_narrative_sections(raw_sections)

    return cleaned, esrs_data, taxonomy_data, narrative_sections
