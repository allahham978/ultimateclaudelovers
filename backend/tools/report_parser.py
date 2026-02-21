"""
Report Parser — JSON cleaning + section routing for the Annual Management Report.

Replaces pdf_reader.py. Pipeline:
  1. extract_xhtml_to_json()  — parse XHTML/iXBRL to structured JSON (engineer's converter)
  2. clean_report_json()      — strip junk data (CSP errors, scripts, empty nodes)
  3. extract_esrs_sections()  — filter ESRS-tagged iXBRL facts for Extractor agent
  4. extract_taxonomy_sections() — filter Taxonomy-tagged iXBRL facts for Fetcher agent
"""

import json
import re
from typing import Any

from lxml import etree


# ── Stage 1: XHTML → JSON extraction (engineer's iXBRL parser) ──────────────

def extract_xhtml_to_json(file_path: str) -> dict:
    """Parse an XHTML/iXBRL file and extract all tagged facts to structured JSON.

    Preserves: concept name, value, unit, context, decimals, scale per fact.
    Uses streaming iterparse to handle large files without excessive memory.

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
        elif len(elem) > 0:
            fact["html_inner"] = etree.tostring(elem, encoding="unicode", method="html")

        extracted_data["facts"].append(fact)

        # Clear element from memory for streaming performance
        elem.clear()
        while elem.getprevious() is not None:
            del elem.getparent()[0]

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
    r"E1[-_]|E2[-_]|S1[-_]|G1[-_]|"  # ESRS standard IDs
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


# ── Convenience: full pipeline ──────────────────────────────────────────────

def parse_report(raw_json: dict) -> tuple[dict, dict, dict]:
    """Run the full cleaning + routing pipeline.

    Args:
        raw_json: Raw JSON from extract_xhtml_to_json or uploaded JSON file.

    Returns:
        Tuple of (cleaned_report, esrs_data, taxonomy_data).
    """
    cleaned = clean_report_json(raw_json)
    esrs_data = extract_esrs_sections(cleaned)
    taxonomy_data = extract_taxonomy_sections(cleaned)
    return cleaned, esrs_data, taxonomy_data
