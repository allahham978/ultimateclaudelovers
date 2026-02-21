"""
Integration test — Real Extractor Node with live Claude API + real ASML XHTML report.

Run manually (NOT part of pytest suite):
    cd backend && source .venv/bin/activate
    python tests/integration_test_extractor.py

Requires:
  - ANTHROPIC_API_KEY set in backend/.env
  - docs/asml-2024-12-31-en.xhtml present in the repo root
"""

import json
import sys
import os
import time

# Ensure backend is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from agents.extractor import extractor_node
from tools.report_parser import extract_xhtml_to_json, extract_narrative_text, clean_report_json, extract_esrs_sections, extract_taxonomy_sections
from schemas import CompanyMeta, ESRSClaim

REPORT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "docs", "asml-2024-12-31-en.xhtml",
)


def main():
    print("=" * 70)
    print("INTEGRATION TEST: Real Extractor + ASML 2024 Annual Report")
    print("=" * 70)

    # ── Check prerequisites ──────────────────────────────────────────────
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key or api_key == "your-api-key-here":
        print("\nERROR: ANTHROPIC_API_KEY not set. Update backend/.env with your real key.")
        sys.exit(1)
    print(f"\n[ok] API key detected (prefix: {api_key[:12]}...)")

    if not os.path.exists(REPORT_PATH):
        print(f"\nERROR: Report not found at {REPORT_PATH}")
        sys.exit(1)
    size_mb = os.path.getsize(REPORT_PATH) / (1024 * 1024)
    print(f"[ok] Report found: {os.path.basename(REPORT_PATH)} ({size_mb:.1f} MB)")

    # ── Stage 1: Parse XHTML to JSON ─────────────────────────────────────
    print("\n--- Stage 1: Parsing XHTML to structured JSON ---")
    t0 = time.time()
    raw_json = extract_xhtml_to_json(REPORT_PATH)
    parse_ms = int((time.time() - t0) * 1000)
    total_facts = len(raw_json.get("facts", []))
    print(f"    Parsed {total_facts} iXBRL facts in {parse_ms}ms")

    # ── Stage 2: Clean junk ───────────────────────────────────────────────
    print("\n--- Stage 2: Cleaning junk data ---")
    cleaned = clean_report_json(raw_json)
    clean_facts = len(cleaned.get("facts", []))
    removed = total_facts - clean_facts
    print(f"    Kept {clean_facts} facts, removed {removed} junk entries")

    # ── Stage 2b: Extract narrative text ─────────────────────────────────
    print("\n--- Stage 2b: Extracting sustainability narrative text ---")
    t0 = time.time()
    narrative = extract_narrative_text(REPORT_PATH)
    narr_ms = int((time.time() - t0) * 1000)
    print(f"    Extracted {len(narrative):,} chars of narrative text in {narr_ms}ms")
    if narrative:
        # Show first 300 chars
        preview = narrative[:300].replace("\n", " ")
        print(f"    Preview: {preview}...")

    # ── Stage 3: Route ESRS sections ──────────────────────────────────────
    print("\n--- Stage 3: Routing ESRS sections ---")
    esrs_data = extract_esrs_sections(cleaned, narrative_text=narrative)
    esrs_count = len(esrs_data.get("facts", []))
    has_narrative = bool(esrs_data.get("narrative_text"))
    print(f"    Found {esrs_count} ESRS-relevant iXBRL facts")
    print(f"    Narrative text included: {has_narrative} ({len(esrs_data.get('narrative_text', '')):,} chars)")

    # Show sample concepts
    if esrs_count > 0:
        concepts = set()
        for f in esrs_data["facts"][:50]:
            c = f.get("concept", "")
            if c:
                concepts.add(c)
        print(f"    Sample concepts ({min(len(concepts), 15)} of {len(concepts)}):")
        for c in sorted(concepts)[:15]:
            print(f"      - {c}")

    # Also route taxonomy (for context)
    taxonomy_data = extract_taxonomy_sections(cleaned)
    tax_count = len(taxonomy_data.get("facts", []))
    print(f"    (Also found {tax_count} Taxonomy-relevant facts)")

    # ── Stage 4: Call real extractor node ──────────────────────────────────
    print("\n--- Stage 4: Calling extractor_node (real Claude API) ---")
    print("    Sending ESRS data to Claude claude-sonnet-4-6... (this may take 10-30s)")

    state = {
        "audit_id": "integration-asml-2024",
        "report_json": cleaned,
        "esrs_data": esrs_data,
        "taxonomy_data": taxonomy_data,
        "entity_id": "ASML Holding N.V.",
        "logs": [],
        "pipeline_trace": [],
    }

    t0 = time.time()
    result = extractor_node(state)
    api_ms = int((time.time() - t0) * 1000)
    print(f"    Claude responded in {api_ms}ms")

    # ── Display results ───────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)

    meta = result["company_meta"]
    print(f"\nCompany Meta:")
    print(f"  Name:         {meta.name}")
    print(f"  LEI:          {meta.lei}")
    print(f"  Sector:       {meta.sector}")
    print(f"  Fiscal Year:  {meta.fiscal_year}")
    print(f"  Jurisdiction: {meta.jurisdiction}")
    print(f"  Report Title: {meta.report_title}")

    claims = result["esrs_claims"]
    print(f"\nESRS Claims ({len(claims)} standards):")
    for std in ("E1-1", "E1-5", "E1-6"):
        claim = claims.get(std)
        if not claim:
            print(f"\n  [{std}] NOT FOUND")
            continue
        print(f"\n  [{std}] {claim.data_point}")
        print(f"    Confidence:      {claim.confidence}")
        print(f"    XBRL Concept:    {claim.xbrl_concept}")
        print(f"    Unit:            {claim.unit}")
        # Truncate long values for readability
        val = claim.disclosed_value or "(null)"
        if len(val) > 200:
            val = val[:200] + "..."
        print(f"    Disclosed Value: {val}")

    print(f"\nExtractor Logs:")
    for log in result["logs"]:
        msg = log["msg"]
        if len(msg) > 120:
            msg = msg[:120] + "..."
        print(f"  [{log['agent']}] {msg}")

    trace = result["pipeline_trace"]
    if trace:
        print(f"\nPipeline Trace:")
        for t in trace:
            print(f"  {t['agent']}: {t['ms']}ms")

    # ── PRD Gate Check ────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("PRD GATE CHECK: esrs_claims contains real values with confidence > 0.5")
    print("=" * 70)

    gate_passed = True

    for std in ("E1-1", "E1-5", "E1-6"):
        present = std in claims
        status = "PASS" if present else "FAIL"
        print(f"  [{status}] {std} present: {present}")
        if not present:
            gate_passed = False

    high_conf = [c for c in claims.values() if c.confidence > 0.5]
    status = "PASS" if high_conf else "FAIL"
    print(f"  [{status}] Claims with confidence > 0.5: {len(high_conf)}/{len(claims)}")
    for c in high_conf:
        print(f"         {c.standard}: confidence={c.confidence}")
    if not high_conf:
        gate_passed = False

    meta_ok = meta.name != "Unknown Entity" and meta.fiscal_year > 0
    status = "PASS" if meta_ok else "FAIL"
    print(f"  [{status}] Company meta populated: name='{meta.name}', fiscal_year={meta.fiscal_year}")
    if not meta_ok:
        gate_passed = False

    error_logs = [l for l in result["logs"] if "Error" in l.get("msg", "")]
    status = "PASS" if not error_logs else "FAIL"
    print(f"  [{status}] No errors: {len(error_logs)} errors")
    if error_logs:
        gate_passed = False
        for el in error_logs:
            print(f"         {el['msg']}")

    print(f"\n{'ALL GATES PASSED' if gate_passed else 'SOME GATES FAILED'}")
    print("=" * 70)

    # ── Dump full response to file for inspection ─────────────────────────
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "integration_output.json")
    output = {
        "company_meta": meta.model_dump(),
        "esrs_claims": {k: v.model_dump() for k, v in claims.items()},
        "logs": result["logs"],
        "pipeline_trace": result["pipeline_trace"],
    }
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nFull output saved to: {out_path}")

    sys.exit(0 if gate_passed else 1)


if __name__ == "__main__":
    main()
