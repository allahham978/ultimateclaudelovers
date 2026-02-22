"""
Integration test — Real Fetcher Node with live Claude API + real ASML XHTML report.

Run manually (NOT part of pytest suite):
    cd backend && source .venv/bin/activate
    python tests/integration_test_fetcher.py

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

from agents.fetcher import fetcher_node
from tools.report_parser import extract_xhtml_to_json, clean_report_json, extract_taxonomy_sections
from schemas import TaxonomyFinancials

REPORT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "docs", "asml-2024-12-31-en.xhtml",
)


def main():
    print("=" * 70)
    print("INTEGRATION TEST: Real Fetcher + ASML 2024 Annual Report")
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

    # ── Stage 3: Route Taxonomy sections ──────────────────────────────────
    print("\n--- Stage 3: Routing Taxonomy sections ---")
    taxonomy_data = extract_taxonomy_sections(cleaned)
    tax_count = len(taxonomy_data.get("facts", []))
    print(f"    Found {tax_count} Taxonomy-relevant iXBRL facts")

    # Show sample concepts
    if tax_count > 0:
        concepts = set()
        for f in taxonomy_data["facts"][:50]:
            c = f.get("concept", "")
            if c:
                concepts.add(c)
        print(f"    Sample concepts ({min(len(concepts), 15)} of {len(concepts)}):")
        for c in sorted(concepts)[:15]:
            print(f"      - {c}")

    # ── Stage 4: Call real fetcher node ────────────────────────────────────
    print("\n--- Stage 4: Calling fetcher_node (real Claude API) ---")
    print("    Sending Taxonomy data to Claude claude-sonnet-4-6... (this may take 10-30s)")

    state = {
        "audit_id": "integration-asml-2024-fetcher",
        "mode": "full_audit",
        "report_json": cleaned,
        "esrs_data": {},
        "taxonomy_data": taxonomy_data,
        "entity_id": "ASML Holding N.V.",
        "logs": [],
        "pipeline_trace": [],
    }

    t0 = time.time()
    result = fetcher_node(state)
    api_ms = int((time.time() - t0) * 1000)
    print(f"    Claude responded in {api_ms}ms")

    # ── Display results ───────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)

    fin = result["taxonomy_financials"]
    print(f"\nTaxonomy Financials:")
    print(f"  CapEx Total EUR:    {fin.capex_total_eur}")
    print(f"  CapEx Green EUR:    {fin.capex_green_eur}")
    print(f"  OpEx Total EUR:     {fin.opex_total_eur}")
    print(f"  OpEx Green EUR:     {fin.opex_green_eur}")
    print(f"  Revenue EUR:        {fin.revenue_eur}")
    print(f"  Fiscal Year:        {fin.fiscal_year}")
    print(f"  Confidence:         {fin.confidence}")
    print(f"  Source Document:    {fin.source_document}")
    print(f"  Taxonomy Activities ({len(fin.taxonomy_activities)}):")
    for act in fin.taxonomy_activities:
        print(f"    - {act}")

    if fin.capex_total_eur and fin.capex_green_eur:
        pct = (fin.capex_green_eur / fin.capex_total_eur) * 100
        print(f"\n  Computed CapEx Alignment: {pct:.1f}%")

    doc = result["document_source"]
    print(f"\nDocument Source:")
    print(f"  Name:           {doc.name}")
    print(f"  Registry Type:  {doc.registry_type}")
    print(f"  Jurisdiction:   {doc.jurisdiction}")

    print(f"\nFetcher Logs:")
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
    print("PRD GATE CHECK: taxonomy_financials.capex_total_eur and capex_green_eur populated")
    print("=" * 70)

    gate_passed = True

    status = "PASS" if fin.capex_total_eur is not None else "FAIL"
    print(f"  [{status}] capex_total_eur populated: {fin.capex_total_eur}")
    if fin.capex_total_eur is None:
        gate_passed = False

    status = "PASS" if fin.capex_green_eur is not None else "FAIL"
    print(f"  [{status}] capex_green_eur populated: {fin.capex_green_eur}")
    if fin.capex_green_eur is None:
        gate_passed = False

    status = "PASS" if fin.confidence > 0.5 else "FAIL"
    print(f"  [{status}] confidence > 0.5: {fin.confidence}")
    if fin.confidence <= 0.5:
        gate_passed = False

    status = "PASS" if fin.fiscal_year != "Unknown" else "FAIL"
    print(f"  [{status}] fiscal_year populated: {fin.fiscal_year}")
    if fin.fiscal_year == "Unknown":
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
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "integration_output_fetcher.json")
    output = {
        "taxonomy_financials": fin.model_dump(),
        "document_source": doc.model_dump(),
        "logs": result["logs"],
        "pipeline_trace": result["pipeline_trace"],
    }
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nFull output saved to: {out_path}")

    sys.exit(0 if gate_passed else 1)


if __name__ == "__main__":
    main()
