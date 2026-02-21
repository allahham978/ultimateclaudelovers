# PRD: EU CSRD Agentic Backend
## EU AI Infrastructure Accountability Engine — Role 1 (Architect) Implementation Plan

**Product**: EU AI Infrastructure Accountability Engine
**Role**: The Architect — owns orchestration, API layer, state machine, and agent personalities
**Version**: v2.0 — Document-first, contract-locked, SSE-streamed
**Locked Choices**: Claude `claude-sonnet-4-6` · 3-PDF multipart upload · SSE streaming · ESRS E1 scope (v1)

---

## 1. Product Context

The frontend is production-complete and rendering a `CSRDAudit` JSON contract from
`frontend/src/lib/types.ts`. It currently runs on 100% mock data from `frontend/src/lib/mock-data.ts`.

The backend does not exist. This PRD defines everything Role 1 must ship to make the frontend live.

**The "Say-Do Gap" mission**: Cross-reference what a company *claims* in its ESRS sustainability
statement against what it *actually* spent (CapEx) in its own EU Taxonomy Table and Climate
Transition Plan. Three documents in, one audit, one number, one roadmap.

### Three Golden Source Documents (user-uploaded)

| Slot | Document | What it provides |
|------|----------|-----------------|
| `management` | Integrated Management Report | Audited financials, sustainability statement, ESRS disclosures |
| `taxonomy` | EU Taxonomy Table | Standardised CapEx/OpEx/Revenue alignment data (green vs. total spend) |
| `transition` | Climate Transition Plan | ESRS E1 interim targets, decarbonisation milestones, retrofit plans |

All financial and ESRS data is extracted directly from these uploaded documents. **No external
registry APIs are called.** The Fetcher agent's role is to parse the Taxonomy Table for CapEx
financials, not to route to external business registers.

### Role 1 owns
- The LangGraph state machine (nodes, edges, routing logic)
- The FastAPI API layer + SSE streaming protocol
- All 4 agent system prompts ("agent personalities")
- Pydantic tool schemas (input/output contracts for each agent)
- PDF text extraction for all 3 golden-source documents
- The `AuditState` TypedDict

### Data Lead B owns (enhancement target)
- **Data Lead B (NLP Modeler)**: Advanced PDF chunking strategy, scored double materiality algorithm

**Role 1's contract with Data Lead B**: extraction functions with typed signatures. When they ship
improved implementations, they drop them in as replacements with zero API surface changes.

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
│   ├── extractor.py               # Node 1 — ESRS Reader (Management Report + Transition Plan → claims)
│   ├── fetcher.py                 # Node 2 — Financial Extractor (Taxonomy Table → CapEx financials)
│   ├── auditor.py                 # Node 3 — Double Materiality Evaluator
│   └── consultant.py             # Node 4 — Taxonomy Consultant + final assembly
│
├── tools/
│   ├── __init__.py
│   ├── pdf_reader.py              # pdfplumber text extraction wrapper (handles all 3 PDFs)
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
    """Raw extracted claim from ESRS PDF — internal to extractor node"""
    standard: str               # "E1-1" | "E1-5" | "E1-6"
    data_point: str
    disclosed_value: Optional[str]
    unit: Optional[str]
    confidence: float           # 0.0–1.0, extractor's certainty
    page_ref: Optional[int]

class TaxonomyFinancials(BaseModel):
    """CapEx/revenue data extracted from the EU Taxonomy Table PDF — internal to fetcher node"""
    capex_total_eur: Optional[float]
    capex_green_eur: Optional[float]       # Taxonomy-aligned CapEx
    opex_total_eur: Optional[float]
    opex_green_eur: Optional[float]        # Taxonomy-aligned OpEx (if disclosed)
    revenue_eur: Optional[float]
    fiscal_year: str
    taxonomy_activities: list[str]         # e.g. ["4.1 Electricity generation from solar", "8.1 Data processing"]
    source_document: str                   # "EU Taxonomy Table" (always — extracted from upload)
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
│  management_text       str          Extracted text from Management Report  │
│  taxonomy_text         str          Extracted text from EU Taxonomy Table  │
│  transition_text       str          Extracted text from Transition Plan    │
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
| `taxonomy_financials` | Node 2 → Node 3 | `TaxonomyFinancials` | CapEx/revenue extracted from EU Taxonomy Table PDF |
| `taxonomy_alignment_score` | Node 3 → Node 4 | `float (0–100)` | Raw numeric score before thresholding |

---

## 5. LangGraph State Machine Design

### Graph Topology

```
START
  │
  ▼
[extractor]  ──── parse Management Report + Transition Plan → ESRS claims + company meta
  │
  ▼
[fetcher]    ──── parse EU Taxonomy Table → CapEx/revenue financials
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
- Fetcher reads the Taxonomy Table independently but runs after Extractor to maintain
  a consistent pipeline trace and allow the Extractor to identify the company first
- Auditor needs both `esrs_claims` AND `taxonomy_financials` to score the Say-Do Gap
- Consultant needs `esrs_ledger` + `taxonomy_alignment` to generate a relevant roadmap

**No conditional branching in v1.** Error handling: nodes log failures into `state["logs"]`
and emit safe defaults — never halt the graph.

**Note on document assignment**: Each golden-source document is read by a specific agent:
| Document | Read by | Why |
|----------|---------|-----|
| Management Report | Extractor | Contains sustainability statement + ESRS disclosures |
| Transition Plan | Extractor | Contains E1-1 targets, milestones, pathway alignment |
| EU Taxonomy Table | Fetcher | Contains structured CapEx/OpEx/Revenue alignment data |

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

**Input documents**: `management_text` (Integrated Management Report) + `transition_text` (Climate Transition Plan)

```
You are a senior EU CSRD compliance auditor specialising in ESRS E1 (Climate Change).
Your task is to read TWO corporate documents and extract specific mandatory disclosures.

DOCUMENTS PROVIDED:
  1. Integrated Management Report — audited financials + sustainability statement
  2. Climate Transition Plan — ESRS E1 interim targets + decarbonisation pathway

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
    "E1-1": { "data_point": str, "disclosed_value": str|null, "unit": str|null, "confidence": float, "page_ref": int|null },
    "E1-5": { "data_point": str, "disclosed_value": str|null, "unit": str|null, "confidence": float, "page_ref": int|null },
    "E1-6": { "data_point": str, "disclosed_value": str|null, "unit": str|null, "confidence": float, "page_ref": int|null }
  }
}

RULES:
- confidence is 0.0–1.0: 1.0 = explicit statement with number, 0.5 = implied, 0.0 = not found
- Never hallucinate or estimate values. Only extract what is explicitly in the text.
- If a data point is missing, set disclosed_value to null and confidence to 0.0.
```

---

### Node 2 — Financial Extractor (Fetcher)
**Constant**: `SYSTEM_PROMPT_FETCHER`

**Input document**: `taxonomy_text` (EU Taxonomy Table)

```
You are an EU Taxonomy financial data extraction specialist.
Your task is to read a company's EU Taxonomy Table and extract structured CapEx, OpEx,
and Revenue alignment data. This is a standardised disclosure table mandated by
Article 8 of the EU Taxonomy Regulation (2020/852).

DOCUMENT TYPE: EU Taxonomy Table — Annex II of Commission Delegated Regulation (EU) 2021/2178

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
    "source_document": "EU Taxonomy Table",
    "confidence": float
  }
}

RULES:
- confidence is 0.0–1.0: 1.0 = clearly structured table with explicit values,
  0.5 = values present but ambiguous layout, 0.0 = table not found or unreadable
- Never hallucinate or estimate values. Only extract what is explicitly in the text.
- If a value is missing, set it to null.
- EUR values should be in absolute terms (not thousands/millions) — if the table
  uses "EUR thousands" or "EUR millions", multiply accordingly.
```

---

### Node 3 — Double Materiality Evaluator (Auditor)
**Constant**: `SYSTEM_PROMPT_AUDITOR`

```
You are an EU Taxonomy and CSRD double materiality assessment specialist.
Apply the regulatory double materiality framework to score each ESRS E1 data point.

INPUT: esrs_claims (extracted ESRS disclosures) + taxonomy_financials (CapEx/revenue from Taxonomy Table)

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

## 7. PDF Reader Tool — Multi-Document Extraction

**File**: `backend/tools/pdf_reader.py`

A single pdfplumber wrapper that extracts text from all 3 golden-source PDFs. Called once
during `POST /audit/run` before the graph is invoked.

```python
import pdfplumber
from io import BytesIO

def extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extract full text from a PDF file using pdfplumber.

    Args:
        pdf_bytes: Raw PDF file bytes from the multipart upload.

    Returns:
        Concatenated text from all pages, separated by page markers.
    """
    pages = []
    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            pages.append(f"--- PAGE {i} ---\n{text}")
    return "\n\n".join(pages)
```

**Usage in `main.py`**: Called once per uploaded PDF during the `/audit/run` handler.
The extracted text for each document is stored in `AuditState` as `management_text`,
`taxonomy_text`, and `transition_text` respectively.

---

## 8. FastAPI Endpoints + SSE Streaming Protocol

**File**: `backend/main.py`

### Endpoint Table

| Method | Path | Content-Type | Purpose |
|--------|------|-------------|---------|
| POST | `/audit/run` | multipart/form-data | Accept PDF + entity_id, start async run, return `audit_id` |
| GET | `/audit/{audit_id}/stream` | text/event-stream | SSE: emit log lines + final CSRDAudit JSON |
| GET | `/audit/{audit_id}` | application/json | Return cached result (for reconnects) |
| GET | `/health` | application/json | Liveness probe |

### POST /audit/run

**Request fields** (multipart/form-data — 3 PDF files + 1 text field):
- `management_report`: PDF bytes (Integrated Management Report)
- `taxonomy_table`: PDF bytes (EU Taxonomy Table)
- `transition_plan`: PDF bytes (Climate Transition Plan)
- `entity_id`: string (company name or LEI)

**Response**: `{ "audit_id": "<uuid4>" }`

Extract text from all 3 PDFs with pdfplumber, initialize `AuditState` with
`management_text`, `taxonomy_text`, `transition_text`, launch LangGraph as background
`asyncio` task, return immediately.

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

ESRS PDFs can be 10,000–80,000 tokens each. With 3 documents, total input can reach
~200,000 tokens. Prompt caching prevents re-processing costs on re-runs.

**Implementation in `agents/extractor.py`** (Extractor reads 2 documents):

```python
messages = [
    {
        "role": "user",
        "content": [
            {"type": "text", "text": "DOCUMENT 1 — INTEGRATED MANAGEMENT REPORT:\n\n"},
            {
                "type": "text",
                "text": state["management_text"],
                "cache_control": {"type": "ephemeral"},  # ← prompt cache marker
            },
            {"type": "text", "text": "\n\nDOCUMENT 2 — CLIMATE TRANSITION PLAN:\n\n"},
            {
                "type": "text",
                "text": state["transition_text"],
                "cache_control": {"type": "ephemeral"},
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

**Implementation in `agents/fetcher.py`** (Fetcher reads 1 document):

```python
messages = [
    {
        "role": "user",
        "content": [
            {"type": "text", "text": "EU TAXONOMY TABLE:\n\n"},
            {
                "type": "text",
                "text": state["taxonomy_text"],
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

Cache TTL is 5 minutes (Anthropic default). Same documents audited multiple times within
that window pays only output token cost (~70% savings on large reports).

---

## 10. Iterative Implementation Steps

### Pre-flight — Write PRD to Docs
- [x] Create `docs/` folder at project root
- [x] Write this PRD as `docs/PRD-agentic-backend.md`

### Iteration 0 — Scaffold
- [ ] Create `backend/` directory and all empty files listed in Section 2
- [ ] Write `requirements.txt`
- [ ] Write `schemas.py` — all Pydantic models mapping to TypeScript contract
- [ ] Write `state.py` — `AuditState` TypedDict (with 3 document text fields)
- [ ] Write `tools/prompts.py` — 4 system prompt string constants

**Gate**: `python -c "from schemas import CSRDAudit; print('OK')"` passes

### Iteration 1 — LangGraph Skeleton with Echo Nodes
- [ ] Write `graph.py` — all 4 nodes as pass-through stubs that log + write dummy values
- [ ] `graph.invoke({"audit_id":"test","management_text":"...","taxonomy_text":"...","transition_text":"...","entity_id":"test"})` runs end-to-end

**Gate**: Full graph runs without error, all 4 nodes execute in order, `final_audit` is populated

### Iteration 2 — FastAPI + SSE Layer
- [ ] Write `main.py` with all 4 endpoints (POST accepts 3 PDF files)
- [ ] Write `tools/pdf_reader.py` — pdfplumber wrapper
- [ ] SSE endpoint reads from `asyncio.Queue`, streams dummy log lines
- [ ] Test with `curl -N http://localhost:8000/audit/{id}/stream`
- [ ] Verify frontend renders: set `NEXT_PUBLIC_API_URL`, drop 3 PDFs

**Gate**: Frontend terminal shows streaming log lines; final result renders as stub data

### Iteration 3 — Real Extractor Node
- [ ] Write `agents/extractor.py` — real Claude API call with prompt caching
- [ ] Feed both `management_text` + `transition_text` to Claude
- [ ] Parse JSON response into `ESRSClaim` objects → populate `state["esrs_claims"]`

**Gate**: `esrs_claims` in state contains real extracted values with `confidence > 0.5`

### Iteration 4 — Real Fetcher Node
- [ ] Write `agents/fetcher.py` — Claude API call to parse EU Taxonomy Table
- [ ] Feed `taxonomy_text` to Claude with `SYSTEM_PROMPT_FETCHER`
- [ ] Parse JSON response into `TaxonomyFinancials` → populate `state["taxonomy_financials"]`

**Gate**: `taxonomy_financials.capex_total_eur` and `capex_green_eur` populated from real Taxonomy Table

### Iteration 5 — Real Auditor Node
- [ ] Write `agents/auditor.py` — scoring prompt + JSON parsing
- [ ] Validate `capex_aligned_pct` math matches `taxonomy_financials`
- [ ] Populate `esrs_ledger`, `taxonomy_alignment`, `compliance_cost`, `taxonomy_alignment_score`

**Gate**: End-to-end run with real PDFs produces valid ESRS ledger with correct status classifications

### Iteration 6 — Real Consultant Node + Final Assembly
- [ ] Write `agents/consultant.py` — roadmap generation + `CSRDAudit` assembly
- [ ] Assemble `sources[]` from the 3 uploaded document names, `pipeline` timing, `document_source`
- [ ] Validate assembled JSON against every field in `frontend/src/lib/types.ts`

**Gate**: Frontend renders a complete live audit report from 3 real PDF uploads

### Iteration 7 — Polish + Handoff Prep
- [ ] Add CORS config (`http://localhost:3000` for dev)
- [ ] Add `.env` / `dotenv` for `ANTHROPIC_API_KEY`
- [ ] Document extraction seams in `prompts.py` for Data Lead B

**Gate**: `uvicorn main:app --reload` + frontend in dev = full live demo

---

## 11. Critical Files Reference

| File | Why It Matters |
|------|---------------|
| [frontend/src/lib/types.ts](../frontend/src/lib/types.ts) | **Source of truth** for all Pydantic model field names — must match exactly |
| [frontend/src/lib/mock-data.ts](../frontend/src/lib/mock-data.ts) | Reference values for expected output shape |
| [frontend/src/components/audit-chamber.tsx](../frontend/src/components/audit-chamber.tsx) | SSE event consumption logic + 3-document upload slots — defines expected field names |
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

# 4. Start server
uvicorn main:app --reload

# 5. Upload 3 Golden Source PDFs
curl -X POST http://localhost:8000/audit/run \
  -F "management_report=@management-report.pdf" \
  -F "taxonomy_table=@taxonomy-table.pdf" \
  -F "transition_plan=@transition-plan.pdf" \
  -F "entity_id=Lumiere Systemes SA"
# → { "audit_id": "<uuid>" }

# 6. Stream result
curl -N http://localhost:8000/audit/<audit_id>/stream
# → SSE log lines + complete event with CSRDAudit JSON

# 7. Extraction validation
# Verify extractor pulls ESRS claims from Management Report + Transition Plan
# Verify fetcher pulls CapEx/revenue from Taxonomy Table
# Verify auditor cross-references claims vs. financials correctly

# 8. Frontend end-to-end
# Set NEXT_PUBLIC_API_URL=http://localhost:8000
# Upload 3 real EU CSRD PDFs → confirm full audit report renders
```

---

## 13. Data Lead Handoff Contracts

### Data Lead B (NLP Modeler) — Extraction & Scoring Seams

**Seam 1 — ESRS Claim Parsing** (`agents/extractor.py`):
```python
def parse_esrs_claims(claude_response_text: str) -> dict[str, ESRSClaim]:
    """Replace with more sophisticated parser if needed.
    E.g. advanced PDF chunking, table detection, or multi-pass extraction."""
```

**Seam 2 — Taxonomy Table Parsing** (`agents/fetcher.py`):
```python
def parse_taxonomy_financials(claude_response_text: str) -> TaxonomyFinancials:
    """Replace with specialised iXBRL parser or structured table extraction
    if Claude's free-text extraction proves insufficient for complex tables."""
```

**Seam 3 — Scoring Constants** (`tools/prompts.py`):
Double materiality scoring weights live in `SYSTEM_PROMPT_AUDITOR` — tunable without
code changes. Adjust point values and thresholds to calibrate severity.
