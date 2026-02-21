# PRD: EU CSRD Agentic Backend
## EU AI Infrastructure Accountability Engine — Role 1 (Architect) Implementation Plan

**Product**: EU AI Infrastructure Accountability Engine
**Role**: The Architect — owns orchestration, API layer, state machine, and agent personalities
**Version**: v3.0 — Single-document XHTML/JSON input, contract-locked, SSE-streamed
**Locked Choices**: Claude `claude-sonnet-4-6` · Single XHTML→JSON upload · SSE streaming · ESRS E1 scope (v1)

---

## 1. Product Context

The frontend is production-complete and rendering a `CSRDAudit` JSON contract from
`frontend/src/lib/types.ts`. It currently runs on 100% mock data from `frontend/src/lib/mock-data.ts`.

The backend does not exist. This PRD defines everything Role 1 must ship to make the frontend live.

**The "Say-Do Gap" mission**: Cross-reference what a company *claims* in its ESRS sustainability
statement against what it *actually* spent (CapEx) — all within the same legally mandated
Annual Management Report. One document in, one audit, one number, one roadmap.

### Single Golden Source Document (user-uploaded)

The EU Annual Management Report (XHTML/iXBRL format) is the legally mandated master document
that companies file under CSRD. It contains **everything** in a single machine-readable file:

| Section within report | What it provides | Read by |
|----------------------|-----------------|---------|
| Sustainability Statement (ESRS disclosures) | E1-1 transition plan, E1-5 energy, E1-6 GHG emissions | Extractor |
| EU Taxonomy Table (Art. 8 disclosure) | Standardised CapEx/OpEx/Revenue alignment data | Fetcher |
| Audited Financial Statements | Revenue, CapEx totals, company metadata | Both |

**Input format**: The XHTML file is pre-parsed to JSON by an engineer-built converter that
preserves iXBRL tag structure (concept names, values, units, reporting contexts as key-value
pairs). The backend receives this **structured JSON**, not raw XHTML or PDF.

**No external registry APIs are called.** All data is extracted from the single uploaded report.

### Role 1 owns
- The LangGraph state machine (nodes, edges, routing logic)
- The FastAPI API layer + SSE streaming protocol
- All 4 agent system prompts ("agent personalities")
- Pydantic tool schemas (input/output contracts for each agent)
- JSON validation, cleaning, and section routing for the Annual Management Report
- The `AuditState` TypedDict

### Data Lead B owns (enhancement target)
- **Data Lead B (NLP Modeler)**: XHTML→JSON converter (iXBRL parser), scored double materiality algorithm

**Role 1's contract with Data Lead B**: The XHTML→JSON converter produces structured JSON with
iXBRL tags preserved. Role 1 consumes this JSON, cleans junk data, routes sections to agents.
When Data Lead B ships improved parsing, the JSON schema stays stable — zero API surface changes.

---

## 2. Target File Structure

```
backend/
├── main.py                        # FastAPI app + CORS + SSE endpoints
├── state.py                       # AuditState TypedDict (shared memory)
├── schemas.py                     # Pydantic v2 models (mirrors TypeScript contract)
├── graph.py                       # LangGraph state machine
│
├── agents/
│   ├── __init__.py
│   ├── extractor.py               # Node 1 — ESRS Reader (ESRS sections from report JSON → claims)
│   ├── fetcher.py                 # Node 2 — Financial Extractor (Taxonomy sections from report JSON → CapEx)
│   ├── auditor.py                 # Node 3 — Double Materiality Evaluator
│   └── consultant.py             # Node 4 — Taxonomy Consultant + final assembly
│
├── tools/
│   ├── __init__.py
│   ├── report_parser.py           # JSON validator + junk stripper + section router (replaces pdf_reader.py)
│   └── prompts.py                 # All 4 system prompt strings (const SYSTEM_PROMPT_*)
│
└── requirements.txt
```

---

## 3. Exact Contract Mapping: TypeScript → Pydantic

The `CSRDAudit` TypeScript interface in `frontend/src/lib/types.ts` is the **single source of truth**.
Every Pydantic model in `schemas.py` must map 1:1 to it. No extra fields, no renames.

| TypeScript | Pydantic Model | Key Fields |
|------------|---------------|-----------|
| `CSRDAudit` | `CSRDAudit` | Top-level return shape |
| `CompanyMeta` | `CompanyMeta` | `name, lei, sector, fiscal_year, jurisdiction, report_title` |
| `TaxonomyAlignment` | `TaxonomyAlignment` | `capex_aligned_pct (float 0-100), status, label` |
| `ComplianceCost` | `ComplianceCost` | `projected_fine_eur (float), basis (str)` |
| `ESRSLedgerItem` | `ESRSLedgerItem` | `id, esrs_id, data_point, impact_materiality, financial_materiality, status, registry_evidence` |
| `MaterialityLevel` | `MaterialityLevel` | Literal["high","medium","low","not_material"] |
| `ESRSStatus` | `ESRSStatus` | Literal["disclosed","partial","missing","non_compliant"] |
| `TaxonomyRoadmap` | `TaxonomyRoadmap` | `hardware, power, workload: RoadmapPillar` |
| `RoadmapPillar` | `RoadmapPillar` | `title, summary, priority, alignment_increase_pct` |
| `Priority` | `Priority` | Literal["critical","high","moderate","low"] |
| `RegistrySource` | `RegistrySource` | `name, registry_type, jurisdiction` |
| `Source` | `Source` | `id, document_name, document_type, url` |
| `PipelineTrace` | `PipelineTrace` | `total_duration_ms, agents: list[AgentTiming]` |
| `AgentTiming` | `AgentTiming` | `agent, duration_ms, status` |
| `AuditLog` | `AuditLog` | Internal only — streamed via SSE, not in final JSON |

### Additional internal schemas (not in TypeScript contract — used inside state machine)

```python
class ESRSClaim(BaseModel):
    """Extracted claim from ESRS sections of the management report JSON — internal to extractor node"""
    standard: str               # "E1-1" | "E1-5" | "E1-6"
    data_point: str
    disclosed_value: Optional[str]
    unit: Optional[str]
    confidence: float           # 0.0–1.0, extractor's certainty
    xbrl_concept: Optional[str] # iXBRL concept name for traceability (e.g. "esrs_E1-1_01")

class TaxonomyFinancials(BaseModel):
    """CapEx/revenue data from the Taxonomy sections of the management report JSON — internal to fetcher node"""
    capex_total_eur: Optional[float]
    capex_green_eur: Optional[float]       # Taxonomy-aligned CapEx
    opex_total_eur: Optional[float]
    opex_green_eur: Optional[float]        # Taxonomy-aligned OpEx (if disclosed)
    revenue_eur: Optional[float]
    fiscal_year: str
    taxonomy_activities: list[str]         # e.g. ["4.1 Electricity generation from solar", "8.1 Data processing"]
    source_document: str                   # "Annual Management Report — Taxonomy Section"
    confidence: float                      # 0.0–1.0, extraction certainty
```

---

## 4. AuditState TypedDict — Shared Agent Memory

`state.py` is the backbone of the LangGraph pipeline. Each node reads from it and writes to it.
Nodes only write to their own output keys. Input keys are never modified after initialization.

```
AuditState keys by lifecycle stage:

┌─ INIT (set by FastAPI before graph.invoke()) ─────────────────────────────┐
│  audit_id              str          UUID for this audit run                │
│  report_json           dict         Full cleaned JSON from XHTML report   │
│  esrs_data             dict         ESRS-tagged iXBRL sections (→ Extr.)  │
│  taxonomy_data         dict         Taxonomy-tagged iXBRL sections (→ Fet)│
│  entity_id             str          Company name / LEI from user input     │
│  logs                  list[dict]   Accumulates { agent, msg, ts } entries │
│  pipeline_trace        list[dict]   Accumulates { agent, started_at, ms } │
└───────────────────────────────────────────────────────────────────────────┘

┌─ NODE 1 OUTPUT (Extractor writes) ────────────────────────────────────────┐
│  esrs_claims       dict[str, ESRSClaim]    keyed by ESRS ID e.g. "E1-1"  │
│  company_meta      CompanyMeta             name, LEI, sector, FY, juris.  │
└───────────────────────────────────────────────────────────────────────────┘

┌─ NODE 2 OUTPUT (Fetcher writes) ──────────────────────────────────────────┐
│  taxonomy_financials   TaxonomyFinancials  CapEx + revenue from Taxonomy  │
│  document_source       RegistrySource      populated from upload metadata │
└───────────────────────────────────────────────────────────────────────────┘

┌─ NODE 3 OUTPUT (Auditor writes) ──────────────────────────────────────────┐
│  esrs_ledger           list[ESRSLedgerItem]  scored double materiality    │
│  taxonomy_alignment    TaxonomyAlignment     capex_aligned_pct + status   │
│  compliance_cost       ComplianceCost        projected fine (EUR)         │
│  taxonomy_alignment_score  float             raw 0–100 (EU-specific key)  │
└───────────────────────────────────────────────────────────────────────────┘

┌─ NODE 4 OUTPUT (Consultant writes — also assembles final CSRDAudit) ──────┐
│  roadmap               TaxonomyRoadmap      3-pillar action plan          │
│  final_audit           CSRDAudit            complete contract-compliant   │
└───────────────────────────────────────────────────────────────────────────┘
```

**EU-specific keys** (required per task brief):

| Key | Node | Type | Purpose |
|-----|------|------|---------|
| `esrs_claims` | Node 1 → Node 3 | `dict[str, ESRSClaim]` | Extracted ESRS data points with confidence |
| `taxonomy_financials` | Node 2 → Node 3 | `TaxonomyFinancials` | CapEx/revenue from Taxonomy sections of report JSON |
| `taxonomy_alignment_score` | Node 3 → Node 4 | `float (0–100)` | Raw numeric score before thresholding |

---

## 5. LangGraph State Machine Design

### Graph Topology

```
START
  │
  ▼
[extractor]  ──── read ESRS sections from report JSON → ESRS claims + company meta
  │
  ▼
[fetcher]    ──── read Taxonomy sections from report JSON → CapEx/revenue financials
  │
  ▼
[auditor]    ──── score impact + financial materiality → compute taxonomy %
  │
  ▼
[consultant] ──── generate roadmap → assemble final CSRDAudit JSON
  │
  ▼
END
```

**Why strictly sequential?** Each node has hard data dependencies on the previous:
- Fetcher reads Taxonomy sections independently but runs after Extractor to maintain
  a consistent pipeline trace and allow the Extractor to identify the company first
- Auditor needs both `esrs_claims` AND `taxonomy_financials` to score the Say-Do Gap
- Consultant needs `esrs_ledger` + `taxonomy_alignment` to generate a relevant roadmap

**No conditional branching in v1.** Error handling: nodes log failures into `state["logs"]`
and emit safe defaults — never halt the graph.

**Note on section routing**: Both agents read from the same report JSON, but different sections:
| Report Section | Read by | State key | Why |
|---------------|---------|-----------|-----|
| ESRS-tagged iXBRL nodes | Extractor | `esrs_data` | Contains E1-1, E1-5, E1-6 disclosures + company metadata |
| Taxonomy-tagged iXBRL nodes | Fetcher | `taxonomy_data` | Contains structured CapEx/OpEx/Revenue alignment data |

Section routing is performed by `report_parser.py` during `POST /audit/run`, before the graph
is invoked. The parser filters iXBRL concept names to split the report into ESRS vs. Taxonomy sections.

### graph.py

```python
from langgraph.graph import StateGraph, END

workflow = StateGraph(AuditState)
workflow.add_node("extractor",  extractor_node)
workflow.add_node("fetcher",    fetcher_node)
workflow.add_node("auditor",    auditor_node)
workflow.add_node("consultant", consultant_node)

workflow.set_entry_point("extractor")
workflow.add_edge("extractor",  "fetcher")
workflow.add_edge("fetcher",    "auditor")
workflow.add_edge("auditor",    "consultant")
workflow.add_edge("consultant", END)

graph = workflow.compile()
```

---

## 6. Agent System Prompts — Full Specifications

All prompts live in `backend/tools/prompts.py` as module-level string constants.

---

### Node 1 — ESRS Reader (Extractor)
**Constant**: `SYSTEM_PROMPT_EXTRACTOR`

**Input**: `esrs_data` — ESRS-tagged iXBRL sections extracted from the Annual Management Report JSON

```
You are a senior EU CSRD compliance auditor specialising in ESRS E1 (Climate Change).
Your task is to read structured iXBRL data extracted from a company's Annual Management Report
(XHTML format, pre-parsed to JSON) and validate specific mandatory disclosures.

DATA FORMAT: Structured JSON with iXBRL tags preserved. Each node contains:
  - concept: XBRL taxonomy concept name (e.g. "esrs_E1-1_01", "ifrs-full:Revenue")
  - value: The disclosed value (string or numeric)
  - unit: Unit of measurement if applicable (e.g. "EUR", "MWh", "tCO2eq")
  - context: Reporting period and entity context
  - decimals: Precision indicator

The iXBRL tags use the ESRS taxonomy. Map concept names directly to the required data points.
Values are pre-extracted — your job is to validate completeness, resolve ambiguities between
related concepts, and structure the output.

FRAMEWORK: ESRS (European Sustainability Reporting Standards), Commission Delegated Regulation (EU) 2023/2772

REQUIRED EXTRACTION TARGETS (ESRS E1):
════════════════════════════════════════

E1-1 | Transition Plan for Climate Change Mitigation
  Extract:
  - Net-zero target year (e.g. "2040", "2050")
  - Interim decarbonisation milestone years and % reduction targets (vs base year)
  - Total CapEx committed to green transition (EUR, absolute value)
  - % of total CapEx classified as EU Taxonomy-aligned
  - Specific EU Taxonomy activities referenced (e.g. "4.1 Electricity generation from solar")

E1-5 | Energy Consumption and Mix
  Extract:
  - Total annual energy consumption (MWh or GWh — note the unit)
  - Renewable energy percentage of total mix (%)
  - Breakdown by source: natural gas (MWh), electricity (MWh), on-site renewables (MWh)
  - Year-on-year energy intensity change (%) or energy per unit revenue

E1-6 | Gross Scopes 1, 2, 3 GHG Emissions
  Extract:
  - Scope 1 gross emissions (tCO₂eq, direct)
  - Scope 2 market-based (tCO₂eq)
  - Scope 2 location-based (tCO₂eq)
  - Scope 3 categories disclosed (list category numbers e.g. "Cat 1, Cat 11")
  - Scope 3 total (tCO₂eq) if consolidated figure disclosed
  - GHG intensity metric (tCO₂eq per EUR million revenue or per MWh)
  - Base year used for all GHG metrics

ALSO EXTRACT (Company Metadata):
  - Company legal name (exactly as stated in the document)
  - LEI (Legal Entity Identifier) if present — format: 20-char alphanumeric
  - Industry/sector classification
  - Fiscal year of the report (integer)
  - Jurisdiction / country of incorporation
  - Report title (exact)

OUTPUT FORMAT: Return ONLY a valid JSON object. Schema:
{
  "company_meta": {
    "name": str,
    "lei": str | null,
    "sector": str,
    "fiscal_year": int,
    "jurisdiction": str,
    "report_title": str
  },
  "esrs_claims": {
    "E1-1": { "data_point": str, "disclosed_value": str|null, "unit": str|null, "confidence": float, "xbrl_concept": str|null },
    "E1-5": { "data_point": str, "disclosed_value": str|null, "unit": str|null, "confidence": float, "xbrl_concept": str|null },
    "E1-6": { "data_point": str, "disclosed_value": str|null, "unit": str|null, "confidence": float, "xbrl_concept": str|null }
  }
}

RULES:
- confidence is 0.0–1.0: 1.0 = explicit iXBRL tag with value + unit, 0.5 = concept present but value ambiguous, 0.0 = not found
- xbrl_concept: the iXBRL concept name that sourced this data point (for audit traceability)
- Never hallucinate or estimate values. Only extract what is explicitly in the structured data.
- If a data point is missing from the iXBRL tags, set disclosed_value to null and confidence to 0.0.
```

---

### Node 2 — Financial Extractor (Fetcher)
**Constant**: `SYSTEM_PROMPT_FETCHER`

**Input**: `taxonomy_data` — Taxonomy-tagged iXBRL sections extracted from the Annual Management Report JSON

```
You are an EU Taxonomy financial data extraction specialist.
Your task is to read structured iXBRL data from the Taxonomy alignment sections of a company's
Annual Management Report (XHTML format, pre-parsed to JSON). The data includes pre-parsed
financial values tagged with EU Taxonomy concept names.

DATA FORMAT: Structured JSON with iXBRL tags. Financial values may already include:
  - concept: XBRL taxonomy concept (e.g. "eutaxonomy:CapExAligned", "ifrs-full:Revenue")
  - value: Numeric or string value
  - unit: Currency unit (typically "iso4217:EUR")
  - context: Reporting period
  - decimals: Precision (-3 = thousands, -6 = millions)

Validate that EUR values are in absolute terms. If the iXBRL decimals attribute indicates
thousands (-3) or millions (-6), multiply accordingly.

DOCUMENT TYPE: EU Taxonomy Table (Art. 8 disclosure) — Annex II of Commission Delegated Regulation (EU) 2021/2178

REQUIRED EXTRACTION TARGETS:
════════════════════════════════

─── CAPEX (Capital Expenditure) ───
  - Total CapEx (EUR, absolute value)
  - Taxonomy-aligned CapEx (EUR, absolute value)
  - Taxonomy-aligned CapEx percentage (%) — this is the primary alignment metric
  - Taxonomy-eligible but not aligned CapEx (EUR) if disclosed separately
  - Breakdown by Taxonomy activity code if available (e.g. "8.1 Data processing", "4.1 Solar")

─── OPEX (Operating Expenditure) ───
  - Total OpEx (EUR) if disclosed
  - Taxonomy-aligned OpEx (EUR) if disclosed
  - Taxonomy-aligned OpEx percentage (%)

─── REVENUE ───
  - Total net revenue / turnover (EUR)
  - Taxonomy-aligned revenue (EUR) if disclosed
  - Taxonomy-aligned revenue percentage (%)

─── METADATA ───
  - Fiscal year of the table
  - Activity codes listed (EU Taxonomy NACE activity references)
  - Whether the table uses the "simplified" or "full" Taxonomy reporting format

OUTPUT FORMAT: Return ONLY a valid JSON object. Schema:
{
  "taxonomy_financials": {
    "capex_total_eur": float | null,
    "capex_green_eur": float | null,
    "opex_total_eur": float | null,
    "opex_green_eur": float | null,
    "revenue_eur": float | null,
    "fiscal_year": str,
    "taxonomy_activities": [str],
    "source_document": "Annual Management Report — Taxonomy Section",
    "confidence": float
  }
}

RULES:
- confidence is 0.0–1.0: 1.0 = clearly tagged iXBRL values with units,
  0.5 = values present but concept mapping ambiguous, 0.0 = taxonomy section not found
- Never hallucinate or estimate values. Only extract what is explicitly in the structured data.
- If a value is missing, set it to null.
- EUR values should be in absolute terms — check the decimals attribute and multiply if needed.
```

---

### Node 3 — Double Materiality Evaluator (Auditor)
**Constant**: `SYSTEM_PROMPT_AUDITOR`

```
You are an EU Taxonomy and CSRD double materiality assessment specialist.
Apply the regulatory double materiality framework to score each ESRS E1 data point.

INPUT: esrs_claims (from ESRS sections of the management report) + taxonomy_financials (from Taxonomy sections of the same report)

DOUBLE MATERIALITY SCORING ALGORITHM:
══════════════════════════════════════

For each ESRS standard (E1-1, E1-5, E1-6), compute two independent scores:

─── IMPACT MATERIALITY (the "Say" — does the company disclose credibly?) ───
Score each standard 0–100:

  E1-1 (Transition Plan):
    +35 pts  disclosed_value is present AND contains a target year
    +25 pts  CapEx commitment amount explicitly stated (EUR)
    +20 pts  1.5°C pathway alignment explicitly referenced
    -30 pts  confidence < 0.5 (partial or implied only)
    -20 pts  no target year found (null)

  E1-5 (Energy):
    +40 pts  total energy consumption disclosed with unit (MWh/GWh)
    +30 pts  renewable % explicitly stated
    +20 pts  year-on-year trend disclosed
    -25 pts  only estimated/approximated values
    -15 pts  missing unit (value present but ambiguous)

  E1-6 (GHG Emissions):
    +30 pts  Scope 1 AND Scope 2 market-based both disclosed with values
    +30 pts  Scope 3 total or category breakdown disclosed
    +20 pts  GHG intensity metric present
    -20 pts  Scope 3 missing entirely
    -15 pts  No methodology or base year disclosed

─── FINANCIAL MATERIALITY (the "Do" — does CapEx match the claims?) ───
Computed once from taxonomy_financials (extracted from EU Taxonomy Table), applied to all ledger rows:
  +40 pts  capex_green_eur / capex_total_eur > 0.30 (green CapEx > 30%)
  +30 pts  capex_green_eur / capex_total_eur > 0.15 (green CapEx > 15%)
  +20 pts  capex_total_eur is present and non-zero
  -20 pts  taxonomy_financials.capex_total_eur is null
  -30 pts  capex_green_eur / capex_total_eur < 0.10 (< 10% green investment)

─── AGGREGATE TAXONOMY ALIGNMENT ───
  capex_aligned_pct = (capex_green_eur / capex_total_eur) × 100  [clamp 0–100]
  taxonomy_status:
    capex_aligned_pct >= 60  → "aligned"
    capex_aligned_pct >= 20  → "partially_aligned"
    capex_aligned_pct <  20  → "non_compliant"

─── ESRS STATUS CLASSIFICATION (per standard) ───
  impact_score >= 70 AND disclosed_value not null  → "disclosed"
  impact_score >= 40                               → "partial"
  disclosed_value is null                          → "missing"
  financial_materiality score < 20                 → "non_compliant" (override)

─── COMPLIANCE COST (Art. 51 CSRD Directive 2022/2464) ───
  non_compliant_count = count of ledger rows with status in ["missing","non_compliant"]
  base_rate = non_compliant_count / total_esrs_count
  projected_fine_eur = revenue_eur × base_rate × 0.05
  basis = "Art. 51 CSRD Directive (EU) 2022/2464 — up to EUR 10M or 5% of net worldwide turnover"

─── MATERIALITY LEVEL MAPPING (float score → label) ───
  score >= 70  → "high"
  score >= 40  → "medium"
  score >= 20  → "low"
  score <  20  → "not_material"

OUTPUT: Valid JSON only. Schema:
{
  "esrs_ledger": [
    { "id": str, "esrs_id": str, "data_point": str,
      "impact_materiality": str, "financial_materiality": str,
      "status": str, "registry_evidence": str }
  ],
  "taxonomy_alignment": { "capex_aligned_pct": float, "status": str, "label": str },
  "compliance_cost": { "projected_fine_eur": float, "basis": str },
  "taxonomy_alignment_score": float
}
```

---

### Node 4 — Taxonomy Consultant
**Constant**: `SYSTEM_PROMPT_CONSULTANT`

```
You are an EU Taxonomy strategic advisor and CSRD compliance consultant.
Your clients are European AI infrastructure companies. Generate precise, actionable roadmaps.

INPUT: esrs_ledger (scored gaps), taxonomy_alignment (current CapEx %), company_meta

ROADMAP FRAMEWORK — THREE PILLARS:
═════════════════════════════════════

Pillar 1 — "Hardware" (Infrastructure Decarbonisation)
  Regulatory lever: EU Taxonomy Delegated Act Annex I, Activity 8.1 (Data processing)
  Taxonomy criteria: PUE ≤ 1.3 (climate mitigation) + REF ≤ 0.4 (water use)
  Scope: GPU rack refresh (B200/GB300), liquid cooling, end-of-life circularity
  ESRS impact: E1-1 CapEx commitment credibility, E1-6 Scope 2 reduction

Pillar 2 — "Power" (Energy Procurement)
  Regulatory lever: ESRS E1-5, EU Guarantee of Origin (GO) scheme
  Taxonomy criteria: renewable energy % ≥ 70% of grid draw
  Scope: Corporate PPAs with EU generators, on-site solar/wind, REC procurement
  ESRS impact: E1-5 renewable mix %, E1-6 Scope 2 market-based reduction

Pillar 3 — "Workload" (Software Efficiency)
  Regulatory lever: ESRS E1-6 GHG intensity metric
  Taxonomy criteria: improving energy-per-FLOP ratio year-on-year
  Scope: carbon-aware scheduling, mixed-precision training, idle GPU reduction
  ESRS impact: E1-6 GHG intensity, E1-5 energy intensity

INSTRUCTIONS:
  - Read the esrs_ledger to identify which ESRS statuses are "missing" or "non_compliant"
  - Priority rule: "critical" if any linked ESRS is "non_compliant",
                   "high" if "missing",
                   "moderate" if "partial"
  - alignment_increase_pct: realistic range 5–25 pts, reference a specific mechanism
  - summary: 2–3 sentences, specific to the company's actual gaps — not generic
  - Reference actual numbers from the ledger (e.g. "Current renewable mix of 29%...")

OUTPUT: Valid JSON only.
{
  "roadmap": {
    "hardware": { "title": str, "summary": str, "priority": str, "alignment_increase_pct": float },
    "power":    { "title": str, "summary": str, "priority": str, "alignment_increase_pct": float },
    "workload": { "title": str, "summary": str, "priority": str, "alignment_increase_pct": float }
  }
}
```

---

## 7. Report Parser Tool — JSON Cleaning + Section Routing

**File**: `backend/tools/report_parser.py`

Replaces `pdf_reader.py`. Receives the pre-parsed JSON from the XHTML→JSON converter
(built by Data Lead B), cleans junk data, and routes sections to the appropriate agents.
Called once during `POST /audit/run` before the graph is invoked.

```python
import json
from typing import Any

# Tags and patterns that indicate non-content junk in the XHTML→JSON output
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
    ...

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
    ...

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
    ...
```

**Usage in `main.py`**: Called once during the `/audit/run` handler.
The cleaned JSON is stored in `AuditState` as `report_json`, with routed sections
in `esrs_data` and `taxonomy_data` respectively.

---

## 8. FastAPI Endpoints + SSE Streaming Protocol

**File**: `backend/main.py`

### Endpoint Table

| Method | Path | Content-Type | Purpose |
|--------|------|-------------|---------|
| POST | `/audit/run` | multipart/form-data | Accept report JSON + entity_id, start async run, return `audit_id` |
| GET | `/audit/{audit_id}/stream` | text/event-stream | SSE: emit log lines + final CSRDAudit JSON |
| GET | `/audit/{audit_id}` | application/json | Return cached result (for reconnects) |
| GET | `/health` | application/json | Liveness probe |

### POST /audit/run

**Request fields** (multipart/form-data — 1 JSON file + 1 text field):
- `report_json`: JSON file (pre-parsed Annual Management Report from XHTML→JSON converter)
- `entity_id`: string (company name or LEI)

**Response**: `{ "audit_id": "<uuid4>" }`

**Processing pipeline** (synchronous, before graph launch):
1. Parse uploaded JSON file
2. `clean_report_json(raw_json)` — strip junk data (CSP errors, script tags, DOM artifacts)
3. `extract_esrs_sections(cleaned)` — route ESRS-tagged iXBRL nodes for Extractor
4. `extract_taxonomy_sections(cleaned)` — route Taxonomy-tagged iXBRL nodes for Fetcher
5. Initialize `AuditState` with `report_json`, `esrs_data`, `taxonomy_data`
6. Launch LangGraph as background `asyncio` task, return immediately

### GET /audit/{audit_id}/stream

**SSE Event Types**:

```
# Log line — emitted by each node (3–5 per node)
data: {"type":"log","agent":"extractor","message":"Parsing CSRD report...","timestamp":1708500001234}

# Node completion marker
data: {"type":"node_complete","agent":"extractor","duration_ms":4810}

# Final result — last event, contains full CSRDAudit JSON
data: {"type":"complete","audit":{...CSRDAudit...}}

# Error — if graph fails
data: {"type":"error","message":"..."}
```

**Frontend compatibility note**: Field names (`type`, `agent`, `message`, `timestamp`) must
match what `frontend/src/components/audit-chamber.tsx` expects for its terminal log playback.

### In-Memory Job Store (v1)

```python
job_queues: dict[str, asyncio.Queue] = {}   # audit_id → SSE event queue
job_results: dict[str, dict] = {}           # audit_id → final CSRDAudit JSON
```

---

## 9. Prompt Caching Strategy (Claude API)

With structured iXBRL JSON, token counts are significantly lower than raw PDF text
(~60–80% fewer tokens for the same report). Prompt caching still applies for re-runs.

**Implementation in `agents/extractor.py`** (Extractor reads ESRS sections):

```python
import json

messages = [
    {
        "role": "user",
        "content": [
            {"type": "text", "text": "ESRS SECTIONS FROM ANNUAL MANAGEMENT REPORT (iXBRL JSON):\n\n"},
            {
                "type": "text",
                "text": json.dumps(state["esrs_data"], indent=2),
                "cache_control": {"type": "ephemeral"},  # ← prompt cache marker
            },
            {"type": "text", "text": "\n\nExtract all ESRS E1 data points as specified."},
        ]
    }
]
response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=4096,
    system=SYSTEM_PROMPT_EXTRACTOR,
    messages=messages,
)
```

**Implementation in `agents/fetcher.py`** (Fetcher reads Taxonomy sections):

```python
import json

messages = [
    {
        "role": "user",
        "content": [
            {"type": "text", "text": "TAXONOMY SECTIONS FROM ANNUAL MANAGEMENT REPORT (iXBRL JSON):\n\n"},
            {
                "type": "text",
                "text": json.dumps(state["taxonomy_data"], indent=2),
                "cache_control": {"type": "ephemeral"},
            },
            {"type": "text", "text": "\n\nExtract all CapEx, OpEx, and Revenue alignment data."},
        ]
    }
]
response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=4096,
    system=SYSTEM_PROMPT_FETCHER,
    messages=messages,
)
```

Cache TTL is 5 minutes (Anthropic default). Same report audited multiple times within
that window pays only output token cost. Structured JSON also benefits from better
cache hit rates since the content is deterministic (no PDF extraction variance).

---

## 10. Iterative Implementation Steps

### Pre-flight — Write PRD to Docs
- [x] Create `docs/` folder at project root
- [x] Write this PRD as `docs/PRD-agentic-backend.md`

### Iteration 0 — Scaffold ✓ COMPLETE (2026-02-21)
- [x] Create `backend/` directory and all empty files listed in Section 2
- [x] Write `requirements.txt`
- [x] Write `schemas.py` — all Pydantic models mapping to TypeScript contract
- [x] Write `state.py` — `AuditState` TypedDict (with 3 document text fields)
- [x] Write `tools/prompts.py` — 4 system prompt string constants

**Gate**: `python -c "from schemas import CSRDAudit; print('OK')"` passes ✓

**Implementation notes**:
- `ESRSLedgerItem` includes `evidence_source: EvidenceSource` (present in `types.ts` but omitted from PRD table) — TypeScript source of truth takes precedence
- Internal schemas `ESRSClaim` and `TaxonomyFinancials` live in `schemas.py`
- `backend/.venv` created; activate with `source backend/.venv/bin/activate`

### Iteration 0.5 — Migrate to Single-Document JSON Input ✓ COMPLETE (2026-02-21)
- [x] Update `state.py` — replace `management_text`, `taxonomy_text`, `transition_text` with `report_json`, `esrs_data`, `taxonomy_data`
- [x] Update `schemas.py` — `ESRSClaim.page_ref` → `ESRSClaim.xbrl_concept`, `TaxonomyFinancials.source_document` default → `"Annual Management Report — Taxonomy Section"`
- [x] Write `tools/report_parser.py` — `clean_report_json()`, `extract_esrs_sections()`, `extract_taxonomy_sections()`
- [x] Delete `tools/pdf_reader.py` (replaced by `report_parser.py`)
- [x] Update `tools/prompts.py` — rewrite Extractor + Fetcher preambles for structured JSON input (iXBRL concept/value/unit/context/decimals data format)
- [x] Update stub agents to read from new state keys (`esrs_data`, `taxonomy_data`)
- [x] Update `backend/tests/test_iteration1.py` — fix test fixtures for new state shape
- [x] Remove `pdfplumber` from `requirements.txt`

**Gate**: `graph.invoke({"audit_id":"test","report_json":{...},"esrs_data":{...},"taxonomy_data":{...},"entity_id":"test"})` runs end-to-end ✓

**Implementation notes**:
- `report_parser.py` handles two common iXBRL JSON shapes: flat dict keyed by concept name (Shape A) and list-of-tagged-nodes under a top-level key (Shape B)
- ESRS section routing filters for `esrs_e1-1`, `esrs_e1-5`, `esrs_e1-6` + entity identification concepts (LEI, company name, jurisdiction)
- Taxonomy section routing filters for `eutaxonomy`, `taxonomyeligibility`, `taxonomyalignment` + standard financial tags (`ifrs-full:capitalexpenditures`, etc.)
- `clean_report_json()` recursively strips script/style elements, CSP metadata, whitespace-only text nodes, and browser rendering artifacts
- Extractor stub now uses `xbrl_concept` (e.g. `"esrs_e1-1_01"`) instead of `page_ref` in dummy ESRSClaim objects
- Consultant now assembles 1 source entry (single Annual Management Report) instead of 3 separate documents
- All 72 unit tests passing; all 3 PRD gate checks green (`schemas OK`, `graph OK`, `parser OK`)

### Iteration 1 — LangGraph Skeleton with Echo Nodes ✓ COMPLETE (2026-02-21)
- [x] Write `graph.py` — all 4 nodes as pass-through stubs that log + write dummy values
- [x] Graph runs end-to-end with all 4 nodes

**Gate**: Full graph runs without error, all 4 nodes execute in order, `final_audit` is populated ✓

**Implementation notes**:
- Each stub node accumulates `logs` and `pipeline_trace` from prior nodes (no reducer needed — each node reads, extends, and returns the full list)
- Auditor derives `capex_aligned_pct` directly from `taxonomy_financials` written by Fetcher
- Consultant assembles the full `CSRDAudit` Pydantic model including `PipelineTrace` from accumulated `pipeline_trace`
- `backend/tests/test_iteration1.py` — 72 unit tests (node isolation + end-to-end), all passing
- Warning: `langchain_core` Pydantic v1 shim is incompatible with Python 3.14; cosmetic only, does not affect runtime

### Iteration 2 — FastAPI + SSE Layer ✓ COMPLETE (2026-02-21)
- [x] Write `main.py` with all 4 endpoints (POST accepts 1 JSON file + entity_id)
- [x] Integrate `report_parser.py` in the `/audit/run` handler (clean → route → init state)
- [x] SSE endpoint streams log lines, node_complete events, and final CSRDAudit JSON
- [x] Test with `curl -N http://localhost:8000/audit/{id}/stream`
- [x] Update frontend: single upload slot, send 1 JSON file instead of 3 PDFs

**Gate**: Frontend terminal shows streaming log lines; final result renders as stub data ✓

**Implementation notes**:
- `main.py`: FastAPI app with CORS (localhost:3000), 4 endpoints matching PRD Section 8
- Background graph execution via `threading.Thread` + `graph.invoke()` — events collected in a thread-safe `_AuditJob` object with `threading.Event` completion signal
- SSE streaming via `StreamingResponse` with async generator polling `job.events` list; yields `data: {json}\n\n` per SSE spec
- In-memory job store: `_jobs: dict[str, _AuditJob]` holding events list + completion flag + cached result
- Log events grouped by agent execution order; `node_complete` emitted after each agent's logs; `complete` event last
- Frontend updated: `api.ts` sends single `report_json` file + `entity_id`; `useAuditStream.ts` accepts `File | null`; `audit-chamber.tsx` single upload card replacing 3-slot Document Vault
- SSE URL updated from `/audit/stream/{id}` to `/audit/{id}/stream` (matching PRD endpoint table)
- Added `httpx>=0.27.0` and `pytest>=8.0.0` to `requirements.txt` for TestClient
- `backend/tests/test_iteration2.py` — 39 unit tests (health, POST validation, cached result, SSE format, CORS, parser integration, end-to-end), all passing
- All 72 iteration 1 tests remain green (zero regressions); all 4 PRD gate checks pass

### Iteration 3 — Real Extractor Node
- [ ] Write `agents/extractor.py` — real Claude API call with prompt caching
- [ ] Feed `esrs_data` (structured iXBRL JSON) to Claude
- [ ] Parse JSON response into `ESRSClaim` objects → populate `state["esrs_claims"]`

**Gate**: `esrs_claims` in state contains real extracted values with `confidence > 0.5`

### Iteration 4 — Real Fetcher Node
- [ ] Write `agents/fetcher.py` — Claude API call to validate Taxonomy financials
- [ ] Feed `taxonomy_data` (structured iXBRL JSON) to Claude with `SYSTEM_PROMPT_FETCHER`
- [ ] Parse JSON response into `TaxonomyFinancials` → populate `state["taxonomy_financials"]`

**Gate**: `taxonomy_financials.capex_total_eur` and `capex_green_eur` populated from real report JSON

### Iteration 5 — Real Auditor Node
- [ ] Write `agents/auditor.py` — scoring prompt + JSON parsing
- [ ] Validate `capex_aligned_pct` math matches `taxonomy_financials`
- [ ] Populate `esrs_ledger`, `taxonomy_alignment`, `compliance_cost`, `taxonomy_alignment_score`

**Gate**: End-to-end run with real report JSON produces valid ESRS ledger with correct status classifications

### Iteration 6 — Real Consultant Node + Final Assembly
- [ ] Write `agents/consultant.py` — roadmap generation + `CSRDAudit` assembly
- [ ] Assemble `sources[]` from the uploaded report name, `pipeline` timing, `document_source`
- [ ] Validate assembled JSON against every field in `frontend/src/lib/types.ts`

**Gate**: Frontend renders a complete live audit report from a real XHTML→JSON upload

### Iteration 7 — Polish + Handoff Prep
- [ ] Add CORS config (`http://localhost:3000` for dev)
- [ ] Add `.env` / `dotenv` for `ANTHROPIC_API_KEY`
- [ ] Document JSON schema contract between Data Lead B's converter and `report_parser.py`

**Gate**: `uvicorn main:app --reload` + frontend in dev = full live demo

---

## 11. Critical Files Reference

| File | Why It Matters |
|------|---------------|
| [frontend/src/lib/types.ts](../frontend/src/lib/types.ts) | **Source of truth** for all Pydantic model field names — must match exactly |
| [frontend/src/lib/mock-data.ts](../frontend/src/lib/mock-data.ts) | Reference values for expected output shape |
| [frontend/src/components/audit-chamber.tsx](../frontend/src/components/audit-chamber.tsx) | SSE event consumption logic + single-document upload slot — defines expected field names |
| [contracts/audit-report.schema.ts](../contracts/audit-report.schema.ts) | Canonical re-export — confirms type names |

---

## 12. Verification Plan

```bash
# 1. Install dependencies
cd backend && pip install -r requirements.txt

# 2. Schema import test
python -c "from schemas import CSRDAudit; print('schemas OK')"

# 3. Graph compile test
python -c "from graph import graph; print('graph OK')"

# 4. Report parser test
python -c "from tools.report_parser import clean_report_json, extract_esrs_sections, extract_taxonomy_sections; print('parser OK')"

# 5. Start server
uvicorn main:app --reload

# 6. Upload Annual Management Report (pre-parsed JSON)
curl -X POST http://localhost:8000/audit/run \
  -F "report_json=@annual-management-report.json" \
  -F "entity_id=Lumiere Systemes SA"
# → { "audit_id": "<uuid>" }

# 7. Stream result
curl -N http://localhost:8000/audit/<audit_id>/stream
# → SSE log lines + complete event with CSRDAudit JSON

# 8. Extraction validation
# Verify report_parser strips junk data and routes sections correctly
# Verify extractor reads ESRS claims from esrs_data (iXBRL sections)
# Verify fetcher reads CapEx/revenue from taxonomy_data (iXBRL sections)
# Verify auditor cross-references claims vs. financials correctly

# 9. Frontend end-to-end
# Set NEXT_PUBLIC_API_URL=http://localhost:8000
# Upload 1 real XHTML→JSON management report → confirm full audit report renders
```

---

## 13. Data Lead Handoff Contracts

### Data Lead B (NLP Modeler) — XHTML→JSON Converter & Scoring Seams

**Seam 1 — XHTML→JSON Converter** (owned by Data Lead B):
```
Input:  Annual Management Report (XHTML/iXBRL format)
Output: Structured JSON with iXBRL tags preserved

Contract: The JSON must preserve these iXBRL attributes per node:
  - concept: XBRL taxonomy concept name
  - value: The disclosed value (string or numeric)
  - unit: Unit of measurement (e.g. "iso4217:EUR", "xbrli:pure")
  - context: Reporting period and entity identifier
  - decimals: Precision indicator (e.g. -3 for thousands)

Role 1 (report_parser.py) consumes this JSON. If the schema changes,
report_parser.py is the only file that needs updating.
```

**Seam 2 — Report Parser** (`tools/report_parser.py`, owned by Role 1):
```python
def clean_report_json(raw_json: dict) -> dict:
    """Strip junk data from XHTML→JSON output. Data Lead B can improve
    their converter to reduce junk, making this function simpler over time."""

def extract_esrs_sections(report: dict) -> dict:
    """Filter ESRS-tagged iXBRL nodes. If Data Lead B adds new ESRS
    concept patterns, update the filter here."""

def extract_taxonomy_sections(report: dict) -> dict:
    """Filter Taxonomy-tagged iXBRL nodes. Same — new concept patterns
    from Data Lead B are absorbed here."""
```

**Seam 3 — Scoring Constants** (`tools/prompts.py`):
Double materiality scoring weights live in `SYSTEM_PROMPT_AUDITOR` — tunable without
code changes. Adjust point values and thresholds to calibrate severity.
