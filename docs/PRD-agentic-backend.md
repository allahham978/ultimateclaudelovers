# PRD: EU CSRD Agentic Backend
## EU AI Infrastructure Accountability Engine — Role 1 (Architect) Implementation Plan

**Product**: EU AI Infrastructure Accountability Engine
**Role**: The Architect — owns orchestration, API layer, state machine, and agent personalities
**Version**: v1.0 — Stub-first, contract-locked, SSE-streamed
**Locked Choices**: Claude `claude-sonnet-4-6` · Multipart PDF upload · SSE streaming · ESRS E1 scope (v1)

---

## 1. Product Context

The frontend is production-complete and rendering a `CSRDAudit` JSON contract from
`frontend/src/lib/types.ts`. It currently runs on 100% mock data from `frontend/src/lib/mock-data.ts`.

The backend does not exist. This PRD defines everything Role 1 must ship to make the frontend live.

**The "Say-Do Gap" mission**: Cross-reference what a company *claims* in its ESRS sustainability
statement against what it *actually* spent (CapEx) in its official registry filings. One audit,
one number, one roadmap.

### Role 1 owns
- The LangGraph state machine (nodes, edges, routing logic)
- The FastAPI API layer + SSE streaming protocol
- All 4 agent system prompts ("agent personalities")
- Pydantic tool schemas (input/output contracts for each agent)
- Mock stubs for registry tools (so the pipeline runs end-to-end today)
- The `AuditState` TypedDict

### Data Leads own (stub targets for now)
- **Data Lead A (Financial Engineer)**: Real Infogreffe API call, BRIS integration, EU Taxonomy Table parser
- **Data Lead B (NLP Modeler)**: Advanced PDF chunking strategy, scored double materiality algorithm

**Role 1's contract with Data Leads**: stub functions with typed signatures. When they ship the real
implementations, they drop them in as replacements with zero API surface changes.

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
│   ├── extractor.py               # Node 1 — ESRS Reader (PDF → claims)
│   ├── fetcher.py                 # Node 2 — BRIS Router (claims → registry financials)
│   ├── auditor.py                 # Node 3 — Double Materiality Evaluator
│   └── consultant.py             # Node 4 — Taxonomy Consultant + final assembly
│
├── tools/
│   ├── __init__.py
│   ├── pdf_reader.py              # pdfplumber text extraction wrapper
│   ├── registry_mock.py           # Dummy Infogreffe / BRIS / Handelsregister
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

class RegistryFinancials(BaseModel):
    """Raw financials from registry stub — internal to fetcher node"""
    capex_total_eur: Optional[float]
    capex_green_eur: Optional[float]
    revenue_eur: Optional[float]
    fiscal_year: str
    source_name: str            # "Infogreffe - France" | "BRIS - EU Registry" | ...
    registry_type: str          # "national" | "eu_bris"
    jurisdiction: str
```

---

## 4. AuditState TypedDict — Shared Agent Memory

`state.py` is the backbone of the LangGraph pipeline. Each node reads from it and writes to it.
Nodes only write to their own output keys. Input keys are never modified after initialization.

```
AuditState keys by lifecycle stage:

┌─ INIT (set by FastAPI before graph.invoke()) ─────────────────────────────┐
│  audit_id          str          UUID for this audit run                    │
│  pdf_text          str          Full extracted text from pdfplumber        │
│  entity_id         str          Company name / LEI from user input         │
│  logs              list[dict]   Accumulates { agent, msg, ts } entries     │
│  pipeline_trace    list[dict]   Accumulates { agent, started_at, ms }      │
└───────────────────────────────────────────────────────────────────────────┘

┌─ NODE 1 OUTPUT (Extractor writes) ────────────────────────────────────────┐
│  esrs_claims       dict[str, ESRSClaim]    keyed by ESRS ID e.g. "E1-1"  │
│  company_meta      CompanyMeta             name, LEI, sector, FY, juris.  │
└───────────────────────────────────────────────────────────────────────────┘

┌─ NODE 2 OUTPUT (Fetcher writes) ──────────────────────────────────────────┐
│  registry_financials   RegistryFinancials  raw CapEx + revenue numbers    │
│  registry_source       RegistrySource      which registry was queried     │
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
| `registry_financials` | Node 2 → Node 3 | `RegistryFinancials` | Actual CapEx/revenue from national registry |
| `taxonomy_alignment_score` | Node 3 → Node 4 | `float (0–100)` | Raw numeric score before thresholding |

---

## 5. LangGraph State Machine Design

### Graph Topology

```
START
  │
  ▼
[extractor]  ──── parse PDF → extract ESRS claims → identify company
  │
  ▼
[fetcher]    ──── route to correct registry → retrieve CapEx/revenue
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
- Fetcher needs `company_meta.jurisdiction` from Extractor to route correctly
- Auditor needs both `esrs_claims` AND `registry_financials` to score the Say-Do Gap
- Consultant needs `esrs_ledger` + `taxonomy_alignment` to generate a relevant roadmap

**No conditional branching in v1.** Error handling: nodes log failures into `state["logs"]`
and emit safe defaults — never halt the graph.

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

```
You are a senior EU CSRD compliance auditor specialising in ESRS E1 (Climate Change).
Your task is to read a corporate sustainability statement and extract specific mandatory disclosures.

DOCUMENT TYPE: Integrated Management Report or CSRD Sustainability Statement
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

### Node 2 — BRIS Router (Fetcher)
**Constant**: `SYSTEM_PROMPT_FETCHER`

```
You are a corporate registry routing specialist for the EU Business Registers Interconnection System (BRIS).
Your role is to identify the correct national registry for a given company and call the appropriate tool.

ROUTING DECISION TREE (apply in strict order):
════════════════════════════════════════════════

Step 1 — Check jurisdiction field from company metadata.
Step 2 — If jurisdiction is missing, infer from legal form suffix in company name.

JURISDICTION → TOOL MAPPING:
  "France" or legal forms [SA, SAS, SARL, SCI, SASU, SE]  → call: get_infogreffe_data
  "Germany" or legal forms [GmbH, AG, KG, OHG, UG, SE]   → call: get_handelsregister_data
  "Netherlands", "Belgium", "Spain", "Italy",
  "Poland", "Sweden", "Denmark", "Austria",
  "Finland", "Ireland", or any other EU state             → call: get_bris_data
  Unknown / not inferable                                  → call: get_bris_data (EU fallback)

After calling the tool, you will receive a RegistryFinancials JSON object.
Return it without modification. Do not invent or adjust any financial values.
You have exactly ONE tool to call. Call it once. Do not call multiple tools.
```

---

### Node 3 — Double Materiality Evaluator (Auditor)
**Constant**: `SYSTEM_PROMPT_AUDITOR`

```
You are an EU Taxonomy and CSRD double materiality assessment specialist.
Apply the regulatory double materiality framework to score each ESRS E1 data point.

INPUT: esrs_claims (extracted ESRS disclosures) + registry_financials (official CapEx/revenue data)

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
Computed once from registry_financials, applied to all ledger rows:
  +40 pts  capex_green_eur / capex_total_eur > 0.30 (green CapEx > 30%)
  +30 pts  capex_green_eur / capex_total_eur > 0.15 (green CapEx > 15%)
  +20 pts  capex_total_eur is present and non-zero
  -20 pts  registry_financials.capex_total_eur is null
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

## 7. Mock Registry Tools — Stub Interfaces for Data Lead A

**File**: `backend/tools/registry_mock.py`

Function signatures are frozen. Data Lead A replaces function bodies only.

```python
def get_infogreffe_data(company_name: str) -> dict:
    """STUB: French RCS via Infogreffe — replace with real API call"""
    return {
        "capex_total_eur": 180_000_000,
        "capex_green_eur": 55_800_000,       # 31% green (matches mock frontend)
        "revenue_eur": 420_000_000,
        "fiscal_year": "2025",
        "source_name": "Infogreffe - France",
        "registry_type": "national",
        "jurisdiction": "France"
    }

def get_handelsregister_data(company_name: str) -> dict:
    """STUB: German Handelsregister — replace with real BRIS DE node"""
    return {
        "capex_total_eur": 250_000_000,
        "capex_green_eur": 87_500_000,       # 35% green
        "revenue_eur": 890_000_000,
        "fiscal_year": "2025",
        "source_name": "Handelsregister - Germany",
        "registry_type": "national",
        "jurisdiction": "Germany"
    }

def get_bris_data(company_name: str) -> dict:
    """STUB: EU BRIS fallback — replace with real BRIS API"""
    return {
        "capex_total_eur": 120_000_000,
        "capex_green_eur": 36_000_000,       # 30% green
        "revenue_eur": 310_000_000,
        "fiscal_year": "2025",
        "source_name": "BRIS - EU Registry",
        "registry_type": "eu_bris",
        "jurisdiction": "EU"
    }
```

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

**Request fields**:
- `file`: PDF bytes (the CSRD report)
- `entity_id`: string (company name or LEI)

**Response**: `{ "audit_id": "<uuid4>" }`

Extract PDF text with pdfplumber, initialize `AuditState`, launch LangGraph as background
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

ESRS PDFs can be 10,000–80,000 tokens. Prompt caching prevents re-processing costs.

**Implementation in `agents/extractor.py`**:

```python
messages = [
    {
        "role": "user",
        "content": [
            {"type": "text", "text": "Here is the sustainability report:\n\n"},
            {
                "type": "text",
                "text": pdf_text,
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

Cache TTL is 5 minutes (Anthropic default). Same PDF audited multiple times within that
window pays only output token cost (~70% savings on large reports).

---

## 10. Iterative Implementation Steps

### Pre-flight — Write PRD to Docs
- [x] Create `docs/` folder at project root
- [x] Write this PRD as `docs/PRD-agentic-backend.md`

### Iteration 0 — Scaffold (2–3 hours)
- [ ] Create `backend/` directory and all empty files listed in Section 2
- [ ] Write `requirements.txt`
- [ ] Write `schemas.py` — all Pydantic models mapping to TypeScript contract
- [ ] Write `state.py` — `AuditState` TypedDict
- [ ] Write `tools/registry_mock.py` — 3 stub functions
- [ ] Write `tools/prompts.py` — 4 system prompt string constants

**Gate**: `python -c "from schemas import CSRDAudit; print('OK')"` passes

### Iteration 1 — LangGraph Skeleton with Echo Nodes (3–4 hours)
- [ ] Write `graph.py` — all 4 nodes as pass-through stubs that log + write dummy values
- [ ] `graph.invoke({"audit_id":"test","pdf_text":"...","entity_id":"test"})` runs end-to-end

**Gate**: Full graph runs without error, all 4 nodes execute in order, `final_audit` is populated

### Iteration 2 — FastAPI + SSE Layer (3–4 hours)
- [ ] Write `main.py` with all 4 endpoints
- [ ] SSE endpoint reads from `asyncio.Queue`, streams dummy log lines
- [ ] Test with `curl -N http://localhost:8000/audit/{id}/stream`
- [ ] Verify frontend renders: set `NEXT_PUBLIC_API_URL`, drop a PDF

**Gate**: Frontend terminal shows streaming log lines; final result renders as stub data

### Iteration 3 — Real Extractor Node (4–5 hours)
- [ ] Write `tools/pdf_reader.py` — pdfplumber wrapper
- [ ] Write `agents/extractor.py` — real Claude API call with prompt caching
- [ ] Parse JSON response into `ESRSClaim` objects → populate `state["esrs_claims"]`

**Gate**: `esrs_claims` in state contains real extracted values with `confidence > 0.5`

### Iteration 4 — Real Fetcher Node (2–3 hours)
- [ ] Write `agents/fetcher.py` — Claude `tool_use` pattern
- [ ] Define 3 Anthropic tools matching mock function signatures
- [ ] Claude routes to correct stub based on `company_meta.jurisdiction`

**Gate**: French company → Infogreffe stub called; German company → Handelsregister stub called

### Iteration 5 — Real Auditor Node (3–4 hours)
- [ ] Write `agents/auditor.py` — scoring prompt + JSON parsing
- [ ] Validate `capex_aligned_pct` math matches registry financials
- [ ] Populate `esrs_ledger`, `taxonomy_alignment`, `compliance_cost`, `taxonomy_alignment_score`

**Gate**: End-to-end run with real PDF produces valid ESRS ledger with correct status classifications

### Iteration 6 — Real Consultant Node + Final Assembly (3–4 hours)
- [ ] Write `agents/consultant.py` — roadmap generation + `CSRDAudit` assembly
- [ ] Assemble `sources[]`, `pipeline` timing, `registry_source` from state
- [ ] Validate assembled JSON against every field in `frontend/src/lib/types.ts`

**Gate**: Frontend renders a complete live audit report from a real PDF upload

### Iteration 7 — Polish + Handoff Prep (2–3 hours)
- [ ] Add CORS config (`http://localhost:3000` for dev)
- [ ] Add `.env` / `dotenv` for `ANTHROPIC_API_KEY`
- [ ] Write clear stub comments in `registry_mock.py` for Data Lead A
- [ ] Document extraction seams in `prompts.py` for Data Lead B

**Gate**: `uvicorn main:app --reload` + frontend in dev = full live demo

---

## 11. Critical Files Reference

| File | Why It Matters |
|------|---------------|
| [frontend/src/lib/types.ts](../frontend/src/lib/types.ts) | **Source of truth** for all Pydantic model field names — must match exactly |
| [frontend/src/lib/mock-data.ts](../frontend/src/lib/mock-data.ts) | Reference values for registry mock stubs |
| [frontend/src/components/audit-chamber.tsx](../frontend/src/components/audit-chamber.tsx) | SSE event consumption logic — defines expected field names |
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

# 5. Upload PDF
curl -X POST http://localhost:8000/audit/run \
  -F "file=@test.pdf" \
  -F "entity_id=Lumiere Systemes SA"
# → { "audit_id": "<uuid>" }

# 6. Stream result
curl -N http://localhost:8000/audit/<audit_id>/stream
# → SSE log lines + complete event with CSRDAudit JSON

# 7. Routing test
# French company name (SA suffix) → Infogreffe mock
# German company name (GmbH suffix) → Handelsregister mock

# 8. Frontend end-to-end
# Set NEXT_PUBLIC_API_URL=http://localhost:8000
# Upload real EU CSRD PDF → confirm full audit report renders
```

---

## 13. Data Lead Handoff Contracts

### Data Lead A (Financial Engineer) — Registry Stubs
Replace function bodies in `backend/tools/registry_mock.py`. Signatures are frozen:
```python
def get_infogreffe_data(company_name: str) -> dict   # returns RegistryFinancials fields
def get_handelsregister_data(company_name: str) -> dict
def get_bris_data(company_name: str) -> dict
```

### Data Lead B (NLP Modeler) — Extraction Seam
The extractor node in `agents/extractor.py` exposes a clean seam:
```python
def parse_esrs_claims(claude_response_text: str) -> dict[str, ESRSClaim]:
    """Replace with more sophisticated parser if needed"""
```
Double materiality scoring constants live in `SYSTEM_PROMPT_AUDITOR` in `tools/prompts.py` —
tunable without code changes.
