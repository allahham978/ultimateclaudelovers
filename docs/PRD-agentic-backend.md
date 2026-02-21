# PRD: EU CSRD Agentic Backend
## EU Sustainability Compliance Engine — Role 1 (Architect) Implementation Plan

**Product**: EU Sustainability Compliance Engine
**Role**: The Architect — owns orchestration, API layer, state machine, and agent personalities
**Version**: v5.0 — Unified output (Compliance Score + Recommendations), dual-input, SSE-streamed
**Locked Choices**: Claude `claude-sonnet-4-6` · Single XHTML→JSON upload OR free-text · SSE streaming · ESRS full scope (all standards from `master_requirements.json`) · 3-agent pipeline (Extractor → Scorer → Advisor)

---

## 1. Product Context

The frontend renders results from a JSON contract defined in `frontend/src/lib/types.ts`.
The backend pipeline processes user input through 3 agents and returns a unified result.

### Mission

**One input, one score, one set of recommendations.**

The user submits either a structured XHTML/iXBRL management report (pre-parsed to JSON) or
free-text describing their sustainability situation. Both modes also collect structured company
inputs (employees, revenue, total assets, reporting year). The system produces:

1. **Sustainability Compliance Score** — a single number (0–100) measuring how compliant the
   company is with applicable EU CSRD/ESRS requirements from the knowledge base
2. **Actionable Recommendations** — a prioritized list grouped by priority tier
   (Critical / High / Moderate / Low) telling the company exactly what to fix

Both input modes produce the **same output format** rendered by the **same UI component**.
The structured document path yields higher-confidence extraction and more specific
recommendations, but the score formula (disclosure completeness vs. knowledge base
requirements) is identical.

### Dual-Input Modes

**Mode 1 — Structured Document**: Upload a pre-parsed Annual Management Report (JSON).
The Extractor reads structured iXBRL data including ESRS disclosures AND financial data
(CapEx/OpEx/Revenue). Financial data does NOT affect the compliance score but enables
more precise, actionable recommendations from the Advisor.

**Mode 2 — Free Text**: Toggle a switch, paste or describe the company's sustainability
situation. The Extractor does best-effort extraction from unstructured prose. Lower
confidence, but same score + recommendations output.

### Single Golden Source Document (Mode 1)

The EU Annual Management Report (XHTML/iXBRL format) is the legally mandated master document
that companies file under CSRD. It contains **everything** in a single machine-readable file:

| Section within report | What it provides | Used for |
|----------------------|-----------------|----------|
| Sustainability Statement (ESRS disclosures) | All ESRS data points (E1–E5, S1–S4, G1) | Compliance scoring |
| EU Taxonomy Table (Art. 8 disclosure) | CapEx/OpEx/Revenue alignment data | Recommendation specificity |
| Audited Financial Statements | Revenue, CapEx totals, company metadata | Recommendation specificity |

**Input format**: The XHTML file is pre-parsed to JSON by an engineer-built converter that
preserves iXBRL tag structure (concept names, values, units, reporting contexts as key-value
pairs). The backend receives this **structured JSON**, not raw XHTML or PDF.

**No external registry APIs are called.** All data is extracted from the single uploaded report.

### Role 1 owns
- The LangGraph state machine (3 nodes, edges, conditional extractor logic)
- The FastAPI API layer + SSE streaming protocol
- All agent system prompts — 3 agents × 2 modes = 6 prompt variants ("agent personalities")
- Pydantic tool schemas (input/output contracts for each agent)
- JSON validation, cleaning, and section routing for the Annual Management Report
- The `AuditState` TypedDict (dual-mode, unified output)
- Knowledge base loader (`master_requirements.json`)

### Data Lead B owns (enhancement target)
- **Data Lead B (NLP Modeler)**: XHTML→JSON converter (iXBRL parser)

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
├── graph.py                       # LangGraph state machine (3-node pipeline)
│
├── agents/
│   ├── __init__.py
│   ├── extractor.py               # Node 1 — Data Extractor (structured iXBRL OR free text → claims + financials)
│   ├── scorer.py                  # Node 2 — Compliance Scorer (claims + knowledge base → score 0–100)
│   └── advisor.py                 # Node 3 — Recommendation Advisor (gaps + financials → grouped recommendations)
│
├── data/
│   ├── master_requirements.json   # Knowledge base — CSRD/ESRS thresholds + requirements (golden rule source)
│   └── schemas/                   # JSON Schema files for master_requirements.json validation
│
├── tools/
│   ├── __init__.py
│   ├── report_parser.py           # JSON validator + junk stripper + section router
│   ├── prompts.py                 # All 6 system prompt strings (3 agents × 2 modes)
│   └── knowledge_base.py          # Loader + query functions for master_requirements.json
│
└── requirements.txt
```

---

## 3. Exact Contract Mapping: TypeScript → Pydantic

The `ComplianceResult` TypeScript interface in `frontend/src/lib/types.ts` is the **single source of truth**.
Every Pydantic model in `schemas.py` must map 1:1 to it. No extra fields, no renames.

**Both input modes produce the same `ComplianceResult` output.**

### Unified Output Contract

| TypeScript | Pydantic Model | Key Fields |
|------------|---------------|-----------|
| `ComplianceResult` | `ComplianceResult` | Top-level return shape (replaces `CSRDAudit` and `ComplianceCheckResult`) |
| `CompanyMeta` | `CompanyMeta` | `name, lei, sector, fiscal_year, jurisdiction, report_title` |
| `CompanyInputs` | `CompanyInputs` | `number_of_employees, revenue_eur, total_assets_eur, reporting_year` |
| `ComplianceScore` | `ComplianceScore` | `overall (int 0–100), category_scores (dict), size_category, applicable_standards_count, disclosed_count` |
| `Recommendation` | `Recommendation` | `id, priority, esrs_id, title, description, regulatory_reference` |
| `Priority` | `Priority` | Literal["critical","high","moderate","low"] |
| `PipelineTrace` | `PipelineTrace` | `total_duration_ms, agents: list[AgentTiming]` |
| `AgentTiming` | `AgentTiming` | `agent, duration_ms, status` |

```python
class CompanyInputs(BaseModel):
    """Structured company data provided by the user — drives threshold-based compliance
    determination against master_requirements.json. Required in both modes."""
    number_of_employees: int          # Headcount — drives CSRD size-category thresholds
    revenue_eur: float                # Net turnover in EUR — drives CSRD applicability
    total_assets_eur: float           # Balance sheet total in EUR — drives CSRD size-category
    reporting_year: int               # The fiscal year being reported on (e.g. 2025)

class ComplianceScore(BaseModel):
    """Single compliance score (0–100) based on disclosure completeness vs. knowledge base."""
    overall: int                      # 0–100, primary score displayed to the user
    size_category: str                # e.g. "large_undertaking", "listed_sme", "exempt"
    applicable_standards_count: int   # how many ESRS standards apply for this company
    disclosed_count: int              # how many of those are fully disclosed
    partial_count: int                # how many are partially disclosed
    missing_count: int                # how many are completely missing

class Recommendation(BaseModel):
    """Single actionable recommendation — grouped by priority tier in the UI."""
    id: str
    priority: Priority                # "critical" | "high" | "moderate" | "low"
    esrs_id: str                      # which ESRS standard this relates to
    title: str                        # short imperative action (e.g. "Conduct Scope 1 & 2 GHG inventory")
    description: str                  # 2–3 sentences: what to do, why, regulatory basis
    regulatory_reference: str         # e.g. "ESRS E1-6, DR E1-6.44"

class ComplianceResult(BaseModel):
    """Unified top-level response for both input modes."""
    audit_id: str
    generated_at: str                 # ISO 8601
    schema_version: str = "3.0"
    mode: str                         # "structured_document" | "free_text"
    company: CompanyMeta
    company_inputs: CompanyInputs
    score: ComplianceScore
    recommendations: list[Recommendation]    # grouped by priority tier in the UI
    pipeline: PipelineTrace
```

### Internal Schemas (not in TypeScript contract — used inside state machine)

```python
class ESRSClaim(BaseModel):
    """Extracted claim from ESRS sections — internal to extractor node."""
    standard: str               # e.g. "E1-1", "S1-1", "G1" — any ESRS standard
    data_point: str
    disclosed_value: Optional[str]
    unit: Optional[str]
    confidence: float           # 0.0–1.0, extractor's certainty
    xbrl_concept: Optional[str] # iXBRL concept name for traceability

class FinancialContext(BaseModel):
    """Financial data extracted from structured documents — improves recommendation quality.
    NOT used for compliance scoring. Only populated in structured_document mode."""
    capex_total_eur: Optional[float]
    capex_green_eur: Optional[float]
    opex_total_eur: Optional[float]
    opex_green_eur: Optional[float]
    revenue_eur: Optional[float]
    taxonomy_activities: list[str] = []
    confidence: float           # 0.0–1.0
```

---

## 4. AuditState TypedDict — Shared Agent Memory

`state.py` is the backbone of the LangGraph pipeline. Each node reads from it and writes to it.
Nodes only write to their own output keys. Input keys are never modified after initialization.

```
AuditState keys by lifecycle stage:

┌─ INIT (set by FastAPI before graph.invoke()) ─────────────────────────────┐
│  audit_id              str               UUID for this audit run           │
│  mode                  str               "structured_document" | "free_text"│
│  report_json           dict              Full cleaned JSON (structured only)│
│  esrs_data             dict              ESRS-tagged iXBRL sections        │
│  taxonomy_data         dict              Taxonomy-tagged sections           │
│  entity_id             str               Company name / LEI from user      │
│  company_inputs        CompanyInputs     employees, revenue, assets, year  │
│  free_text_input       str               Raw user text (free_text only)    │
│  logs                  list[dict]        Accumulates { agent, msg, ts }    │
│  pipeline_trace        list[dict]        Accumulates { agent, started_at } │
└───────────────────────────────────────────────────────────────────────────┘

┌─ NODE 1 OUTPUT (Extractor writes) ────────────────────────────────────────┐
│  esrs_claims          dict[str, ESRSClaim]   keyed by ESRS ID e.g. "E1-1"│
│  company_meta         CompanyMeta            name, LEI, sector, FY, juris.│
│  financial_context    FinancialContext | None CapEx/revenue (structured    │
│                                              doc only — used by Advisor   │
│                                              for recommendation quality,  │
│                                              NOT for scoring)             │
└───────────────────────────────────────────────────────────────────────────┘

┌─ NODE 2 OUTPUT (Scorer writes) ───────────────────────────────────────────┐
│  compliance_score     ComplianceScore        overall 0–100 + breakdown    │
│  applicable_reqs      list[dict]             matched requirements from KB │
│  coverage_gaps        list[dict]             { esrs_id, status, details } │
└───────────────────────────────────────────────────────────────────────────┘

┌─ NODE 3 OUTPUT (Advisor writes — also assembles final ComplianceResult) ──┐
│  recommendations      list[Recommendation]   grouped by priority tier     │
│  final_result         ComplianceResult       complete unified output      │
└───────────────────────────────────────────────────────────────────────────┘
```

**Key data flows**:

| Key | From → To | Type | Purpose |
|-----|-----------|------|---------|
| `esrs_claims` | Extractor → Scorer | `dict[str, ESRSClaim]` | Extracted ESRS data points with confidence |
| `company_inputs` | INIT → Scorer | `CompanyInputs` | Drives size-category + applicable standards from KB |
| `compliance_score` | Scorer → Advisor | `ComplianceScore` | Score + gap analysis for recommendation generation |
| `financial_context` | Extractor → Advisor | `FinancialContext` | Financial data for recommendation specificity (structured doc only) |

---

## 5. LangGraph State Machine Design

### Graph Topology

```
START
  │
  ▼
[extractor]  ──── extract ESRS claims + company meta + financial context (if structured doc)
  │
  ▼
[scorer]     ──── load knowledge base + match company inputs → compliance score (0–100)
  │
  ▼
[advisor]    ──── generate grouped recommendations → assemble final ComplianceResult
  │
  ▼
END
```

**Strictly sequential** — each node has hard data dependencies on the previous:
- Scorer needs `esrs_claims` from Extractor + `company_inputs` from INIT to match against KB
- Advisor needs `compliance_score` + `coverage_gaps` from Scorer to generate relevant recommendations
- Advisor also reads `financial_context` from Extractor (if available) for recommendation specificity

**No conditional branching in the graph.** The Extractor handles mode-switching internally
(structured document vs. free text). All 3 nodes always run. Error handling: nodes log failures
into `state["logs"]` and emit safe defaults — never halt the graph.

**Section routing** (structured document mode only): `report_parser.py` splits the report JSON
into `esrs_data` and `taxonomy_data` before the graph is invoked. In free-text mode, only
`free_text_input` is populated.

### graph.py

```python
from langgraph.graph import StateGraph, END

workflow = StateGraph(AuditState)
workflow.add_node("extractor", extractor_node)
workflow.add_node("scorer",    scorer_node)
workflow.add_node("advisor",   advisor_node)

workflow.set_entry_point("extractor")
workflow.add_edge("extractor", "scorer")
workflow.add_edge("scorer",    "advisor")
workflow.add_edge("advisor",   END)

graph = workflow.compile()
```

---

## 6. Agent System Prompts — Full Specifications

All prompts live in `backend/tools/prompts.py` as module-level string constants.
Each agent has two prompt variants: one for structured document input, one for free text.

---

### Node 1 — Data Extractor
**Constants**: `SYSTEM_PROMPT_EXTRACTOR` (structured doc), `SYSTEM_PROMPT_EXTRACTOR_LITE` (free text)

The Extractor reads the user's input and produces three outputs:
1. `esrs_claims` — extracted ESRS data points with confidence scores
2. `company_meta` — company metadata
3. `financial_context` — CapEx/OpEx/Revenue data (structured document only, `None` for free text)

#### Structured Document Mode (`SYSTEM_PROMPT_EXTRACTOR`)

**Input**: `esrs_data` (ESRS-tagged iXBRL sections) + `taxonomy_data` (Taxonomy-tagged sections)

```
You are a senior EU CSRD compliance data extraction specialist.
Your task is to read structured iXBRL data extracted from a company's Annual Management Report
(XHTML format, pre-parsed to JSON) and extract ALL ESRS disclosures and financial data.

DATA FORMAT: Structured JSON with iXBRL tags preserved. Each node contains:
  - concept: XBRL taxonomy concept name (e.g. "esrs_E1-1_01", "ifrs-full:Revenue")
  - value: The disclosed value (string or numeric)
  - unit: Unit of measurement if applicable (e.g. "EUR", "MWh", "tCO2eq")
  - context: Reporting period and entity context
  - decimals: Precision indicator

FRAMEWORK: ESRS (European Sustainability Reporting Standards), Commission Delegated Regulation (EU) 2023/2772

EXTRACTION SCOPE — ALL ESRS STANDARDS:
═══════════════════════════════════════

Extract data points for every ESRS standard present in the document. This includes but is
not limited to: E1–E5 (Environmental), S1–S4 (Social), G1 (Governance), ESRS 2 (General).

For each standard found, extract:
  - The standard ID (e.g. "E1-1", "S1-6", "G1")
  - A summary data_point description
  - The disclosed_value (exact value from the data)
  - The unit (if applicable)
  - confidence (0.0–1.0): 1.0 = explicit tag + value + unit, 0.5 = ambiguous, 0.0 = not found
  - xbrl_concept: the iXBRL concept name for traceability

ALSO EXTRACT — Financial Context (from Taxonomy sections):
  - capex_total_eur, capex_green_eur, opex_total_eur, opex_green_eur, revenue_eur
  - taxonomy_activities (list of activity codes)
  - confidence for financial extraction

ALSO EXTRACT — Company Metadata:
  - Company legal name, LEI, sector, fiscal year, jurisdiction, report title

OUTPUT FORMAT: Return ONLY a valid JSON object. Schema:
{
  "company_meta": { "name": str, "lei": str|null, "sector": str, "fiscal_year": int,
                     "jurisdiction": str, "report_title": str },
  "esrs_claims": {
    "<ESRS_ID>": { "data_point": str, "disclosed_value": str|null, "unit": str|null,
                    "confidence": float, "xbrl_concept": str|null },
    ...
  },
  "financial_context": {
    "capex_total_eur": float|null, "capex_green_eur": float|null,
    "opex_total_eur": float|null, "opex_green_eur": float|null,
    "revenue_eur": float|null, "taxonomy_activities": [str], "confidence": float
  }
}

RULES:
- Extract ALL ESRS standards found, not just E1. The key is the ESRS ID (e.g. "E1-1", "S1-6").
- Never hallucinate or estimate values. Only extract what is explicitly present.
- If a data point is missing, set disclosed_value to null and confidence to 0.0.
- EUR values should be in absolute terms — check the decimals attribute and multiply if needed.
```

#### Free Text Mode (`SYSTEM_PROMPT_EXTRACTOR_LITE`)

**Input**: `free_text_input` — raw user text

```
You are a senior EU CSRD compliance analyst. Your task is to read unstructured text
provided by a company and extract any sustainability-related disclosures you can identify.

The input is NOT a structured iXBRL document. It may be:
- A rough sustainability report or draft
- Meeting notes or internal strategy documents
- A partial or incomplete management report
- Plain-text descriptions of the company's sustainability efforts
- Very little information at all

EXTRACTION SCOPE — ALL ESRS STANDARDS:
═══════════════════════════════════════

Map any sustainability claims to ESRS standards where possible. This includes:
  - E1–E5 (Environmental): climate, pollution, water, biodiversity, resource use
  - S1–S4 (Social): own workforce, value chain workers, communities, consumers
  - G1 (Governance): business conduct

For each claim found, map to the closest ESRS standard and extract:
  - The standard ID (e.g. "E1-1", "S1-1", "G1")
  - A summary data_point description
  - The disclosed_value (if any specific figure is stated)
  - The unit (if applicable)
  - confidence (0.0–1.0): 1.0 = explicit numeric + unit, 0.7 = specific claim no figure,
    0.5 = vague mention, 0.3 = implied, 0.0 = not found
  - xbrl_concept: always null in free text mode

OUTPUT FORMAT: Return ONLY a valid JSON object. Schema:
{
  "company_meta": { "name": str|null, "lei": null, "sector": str|null, "fiscal_year": int|null,
                     "jurisdiction": str|null, "report_title": "User-Provided Sustainability Description" },
  "esrs_claims": {
    "<ESRS_ID>": { "data_point": str, "disclosed_value": str|null, "unit": str|null,
                    "confidence": float, "xbrl_concept": null },
    ...
  },
  "financial_context": null
}

RULES:
- Never hallucinate or invent data not present in the input text.
- If the input contains almost nothing, return mostly null values and few/no esrs_claims.
- financial_context is always null in free text mode.
```

---

### Node 2 — Compliance Scorer
**Constant**: `SYSTEM_PROMPT_SCORER`

The Scorer loads `master_requirements.json`, determines the company's size category from
`company_inputs`, identifies which ESRS standards are applicable, and computes a compliance
score (0–100) based on disclosure completeness.

**Input**: `esrs_claims` + `company_inputs` + knowledge base (loaded at runtime)

```
You are an EU CSRD compliance scoring specialist.
Your task is to assess a company's sustainability compliance against applicable ESRS requirements.

INPUT:
  - esrs_claims: extracted ESRS data points with confidence scores
  - company_inputs: { number_of_employees, revenue_eur, total_assets_eur, reporting_year }
  - applicable_requirements: list of ESRS standards that apply to this company
    (pre-filtered by size category and reporting year from master_requirements.json)

COMPLIANCE SCORING ALGORITHM:
═════════════════════════════

Step 1 — SIZE CATEGORY DETERMINATION (pre-computed, provided as input):
  The company's size category and applicable standards are determined from company_inputs
  against thresholds in master_requirements.json. You receive the filtered list.

Step 2 — DISCLOSURE COVERAGE ASSESSMENT:
  For each applicable ESRS requirement, classify the company's disclosure status:
    "disclosed"     = esrs_claims contains a matching claim with confidence ≥ 0.7
                      AND disclosed_value is not null
    "partial"       = esrs_claims contains a matching claim with 0.3 ≤ confidence < 0.7
                      OR disclosed_value is null but data_point mentions the topic
    "missing"       = no matching claim found, OR confidence < 0.3

Step 3 — SCORE CALCULATION:
  disclosed_count = count of "disclosed" standards
  partial_count   = count of "partial" standards
  missing_count   = count of "missing" standards
  total           = applicable_standards_count

  overall_score = round(((disclosed_count * 1.0 + partial_count * 0.5) / total) * 100)
  Clamp to 0–100.

OUTPUT FORMAT: Return ONLY a valid JSON object. Schema:
{
  "compliance_score": {
    "overall": int,
    "size_category": str,
    "applicable_standards_count": int,
    "disclosed_count": int,
    "partial_count": int,
    "missing_count": int
  },
  "coverage_gaps": [
    { "esrs_id": str, "standard_name": str, "status": "disclosed"|"partial"|"missing",
      "details": str },
    ...
  ]
}

RULES:
- The score is purely based on disclosure completeness — NOT financial performance.
- Apply the same formula regardless of whether input is from structured document or free text.
- coverage_gaps must include ALL applicable standards, not just the ones with gaps.
- Order coverage_gaps by: missing first, then partial, then disclosed.
```

---

### Node 3 — Recommendation Advisor
**Constants**: `SYSTEM_PROMPT_ADVISOR` (shared — same prompt for both modes)

The Advisor reads the score, coverage gaps, and (optionally) financial context to generate
actionable recommendations grouped by priority tier.

**Input**: `compliance_score` + `coverage_gaps` + `financial_context` (may be None) + `company_meta`

```
You are an EU CSRD compliance advisor. Generate specific, actionable recommendations
to help the company improve their sustainability compliance score.

INPUT:
  - compliance_score: overall score (0–100) + breakdown
  - coverage_gaps: per-standard disclosure status (disclosed/partial/missing)
  - financial_context: CapEx/OpEx/Revenue data (may be null if free-text input)
  - company_meta: company name, sector, jurisdiction

RECOMMENDATION GENERATION RULES:
═════════════════════════════════

For each standard with status "missing" or "partial" in coverage_gaps:
  Generate 1 specific recommendation with:
  - title: imperative verb + specific action (e.g. "Conduct Scope 1 & 2 GHG inventory")
  - description: 2–3 sentences explaining what to do, why it matters, regulatory basis
  - regulatory_reference: specific ESRS disclosure requirement (e.g. "ESRS E1-6, DR E1-6.44")

PRIORITY RULES:
  "critical" = "missing" AND it's a mandatory CSRD disclosure (core standards like E1, S1, ESRS 2)
  "high"     = "missing" but lower regulatory urgency, OR "partial" with significant gaps
  "moderate" = "partial" coverage with minor gaps
  "low"      = "disclosed" but could be improved for best practice

FINANCIAL CONTEXT (when available):
  If financial_context is not null, use the CapEx/revenue data to make recommendations MORE
  SPECIFIC. For example:
  - "Your green CapEx of €12M (18% of total) could be increased to meet the 30% threshold..."
  - "With revenue of €85M, the potential Art. 51 fine exposure is approximately..."
  Do NOT use financial data to change the priority — only to enrich the description.

GROUP BY PRIORITY: Output recommendations sorted by priority (critical first → low last).

OUTPUT FORMAT: Return ONLY a valid JSON object. Schema:
{
  "recommendations": [
    { "id": "rec-1", "priority": str, "esrs_id": str, "title": str,
      "description": str, "regulatory_reference": str },
    ...
  ]
}

RULES:
- Be specific to the company's actual gaps — not generic boilerplate.
- Reference the company's sector and situation where possible.
- Every "missing" or "partial" standard MUST have at least one recommendation.
- Recommendations should be achievable and reference real regulatory provisions.
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
        Dict of Taxonomy-tagged iXBRL nodes for the Extractor agent (financial context).
    """
    ...
```

**Usage in `main.py`**: Called once during the `/audit/run` handler (structured document mode only).
The cleaned JSON is stored in `AuditState` as `report_json`, with routed sections
in `esrs_data` and `taxonomy_data` respectively. Both are read by the Extractor.

---

## 8. FastAPI Endpoints + SSE Streaming Protocol

**File**: `backend/main.py`

### Endpoint Table

| Method | Path | Content-Type | Purpose |
|--------|------|-------------|---------|
| POST | `/audit/run` | multipart/form-data | Accept inputs, start async run, return `audit_id` |
| GET | `/audit/{audit_id}/stream` | text/event-stream | SSE: emit log lines + final ComplianceResult JSON |
| GET | `/audit/{audit_id}` | application/json | Return cached result (for reconnects) |
| GET | `/health` | application/json | Liveness probe |

### POST /audit/run

**Request fields** (multipart/form-data):
- `entity_id`: string (company name or LEI)
- `mode`: string (`"structured_document"` | `"free_text"`, default `"structured_document"`)
- `report_json`: JSON file (required for `structured_document` mode)
- `free_text`: string (required for `free_text` mode)
- `number_of_employees`: integer (required, both modes)
- `revenue_eur`: float (required, both modes)
- `total_assets_eur`: float (required, both modes)
- `reporting_year`: integer (required, both modes)

**Response**: `{ "audit_id": "<uuid4>" }`

**Validation**:
- `mode=structured_document`: `report_json` required, `free_text` ignored. 400 if no file.
- `mode=free_text`: `free_text` required, `report_json` ignored. 400 if no text.
- All 4 company inputs required in both modes. 400 if any missing.

**Processing pipeline** (synchronous, before graph launch):
1. Validate inputs per mode
2. If structured document: parse uploaded JSON, `clean_report_json()`, `extract_esrs_sections()`, `extract_taxonomy_sections()`
3. Build `CompanyInputs` from form fields
4. Initialize `AuditState` with all inputs
5. Launch LangGraph as background task, return immediately

### GET /audit/{audit_id}/stream

**SSE Event Types**:

```
# Log line — emitted by each node (3–5 per node)
data: {"type":"log","agent":"extractor","message":"Extracting ESRS disclosures...","timestamp":1708500001234}

# Node completion marker
data: {"type":"node_complete","agent":"extractor","duration_ms":4810}

# Final result — last event, contains unified ComplianceResult JSON
data: {"type":"complete","result":{...ComplianceResult...}}

# Error — if graph fails
data: {"type":"error","message":"..."}
```

**Agent names in SSE events**: `"extractor"`, `"scorer"`, `"advisor"` (3 agents, both modes).

### In-Memory Job Store (v1)

```python
job_queues: dict[str, asyncio.Queue] = {}   # audit_id → SSE event queue
job_results: dict[str, dict] = {}           # audit_id → final ComplianceResult JSON
```

---

## 9. Prompt Caching Strategy (Claude API)

With structured iXBRL JSON, token counts are significantly lower than raw PDF text
(~60–80% fewer tokens for the same report). Prompt caching still applies for re-runs.

**Implementation in `agents/extractor.py`** (Extractor reads ESRS + Taxonomy sections in one call):

```python
import json

# Structured document mode — send both ESRS and Taxonomy data
content_parts = [
    {"type": "text", "text": "ESRS SECTIONS FROM ANNUAL MANAGEMENT REPORT (iXBRL JSON):\n\n"},
    {
        "type": "text",
        "text": json.dumps(state["esrs_data"], indent=2),
        "cache_control": {"type": "ephemeral"},
    },
    {"type": "text", "text": "\n\nTAXONOMY SECTIONS (iXBRL JSON):\n\n"},
    {
        "type": "text",
        "text": json.dumps(state["taxonomy_data"], indent=2),
        "cache_control": {"type": "ephemeral"},
    },
    {"type": "text", "text": "\n\nExtract all ESRS data points and financial context as specified."},
]

messages = [{"role": "user", "content": content_parts}]
response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=4096,
    system=SYSTEM_PROMPT_EXTRACTOR,
    messages=messages,
)
```

Cache TTL is 5 minutes (Anthropic default). Same report processed multiple times within
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

### Iteration 3 — Real Extractor Node ✓ COMPLETE
- [x] Write `agents/extractor.py` — real Claude API call with prompt caching
- [x] Feed `esrs_data` (structured iXBRL JSON) to Claude
- [x] Parse JSON response into `ESRSClaim` objects → populate `state["esrs_claims"]`

**Gate**: `esrs_claims` in state contains real extracted values with `confidence > 0.5` ✓

### Iteration 4 — Compliance Check Scaffold (Backend) ✓ COMPLETE (2026-02-21)
- [x] Update `state.py` — add `mode`, `free_text_input`, `extracted_goals`, `esrs_coverage`, `compliance_cost_estimate`, `todo_list`, `final_compliance_check` keys
- [x] Add new Pydantic models to `schemas.py` — `ExtractedGoal`, `ESRSCoverageItem`, `ComplianceTodo`, `ComplianceCostEstimate`, `ComplianceCheckResult`
- [x] Add 3 new system prompts to `tools/prompts.py` — `SYSTEM_PROMPT_EXTRACTOR_LITE`, `SYSTEM_PROMPT_AUDITOR_LITE`, `SYSTEM_PROMPT_CONSULTANT_LITE`
- [x] Update `graph.py` — add conditional routing after Extractor (`route_after_extractor`)
- [x] Update agent stubs to check `state["mode"]` and branch logic (full_audit vs compliance_check)
- [x] Update `main.py` — accept `mode` + `free_text` form fields, validate per mode, update `_run_graph` for dual-mode complete events

**Gate**: `graph.invoke({"mode":"compliance_check","free_text_input":"...","entity_id":"test",...})` runs 3-node pipeline (skips fetcher) and returns `final_compliance_check`. Full audit path unchanged (zero regression). ✓

**Implementation notes**:
- `schemas.py`: Added 7 new types — `CoverageLevel`, `EffortLevel`, `ExtractedGoal`, `ESRSCoverageItem`, `ComplianceTodo`, `ComplianceCostEstimate`, `ComplianceCheckResult`
- `state.py`: Added 7 new keys for dual-mode support — `mode`, `free_text_input`, `extracted_goals`, `esrs_coverage`, `compliance_cost_estimate`, `todo_list`, `final_compliance_check`
- `graph.py`: Replaced linear `add_edge("extractor", "fetcher")` with `add_conditional_edges` using `route_after_extractor()` — routes to `"auditor"` when `mode == "compliance_check"`, else `"fetcher"`
- `tools/prompts.py`: 3 new prompt constants (`SYSTEM_PROMPT_EXTRACTOR_LITE`, `SYSTEM_PROMPT_AUDITOR_LITE`, `SYSTEM_PROMPT_CONSULTANT_LITE`) for unstructured text processing
- Agent stubs: All 3 reused agents (extractor, auditor, consultant) check `state.get("mode")` and branch to compliance-specific logic; fetcher unchanged (simply skipped)
- `main.py`: `POST /audit/run` now accepts `mode` (default `"full_audit"`) and optional `free_text` form fields; validation rejects missing `report_json` in full_audit mode and missing `free_text` in compliance_check mode; `_run_graph` emits `{"type":"complete","compliance_check":{...}}` for compliance check results
- Compliance check stub outputs: extractor writes `extracted_goals`, auditor writes `esrs_coverage` + `compliance_cost_estimate`, consultant writes `todo_list` + assembles `ComplianceCheckResult` with 3-agent pipeline trace
- Consultant always appends 2 foundational to-do items ("Prepare XHTML/iXBRL report" + "Engage CSRD auditor") regardless of coverage
- Updated `test_iteration2.py`: `test_rejects_missing_report_file` now expects 400 (was 422) since `report_json` is optional at the FastAPI parameter level (validation moved to handler logic)
- `backend/tests/test_iteration4.py` — 96 unit tests (schemas, state, prompts, graph routing, all 3 agents in compliance mode, FastAPI dual-mode endpoints, SSE compliance events, full audit regression), all passing
- All 198 tests across iterations 1, 2, 4 passing; all 4 PRD gate checks green (`schemas OK`, `graph OK`, `parser OK`, `compliance_check gate OK`)

### Iteration 5 — Compliance Check Frontend ✓ COMPLETE
- [x] Add new TypeScript types to `frontend/src/lib/types.ts` — `ComplianceCheckResult`, `ExtractedGoal`, `ESRSCoverageItem`, `ComplianceTodo`, `ComplianceCostEstimate`, updated `SSECompleteEvent`
- [x] Update `audit-chamber.tsx` — add mode toggle switch, text area for compliance check mode, conditional rendering
- [x] Update `api.ts` — add `startComplianceCheck()` function
- [x] Update `useAuditStream.ts` — handle `complianceCheck` result, dynamic progress (3 vs 4 agents), new `startComplianceCheck` action
- [x] Create `ComplianceCheckView` component — renders extracted goals, ESRS coverage table, to-do list, cost estimate with caveat
- [x] Add mock data — `MOCK_COMPLIANCE_CHECK` and `COMPLIANCE_CHECK_LOGS` in `mock-data.ts`

**Gate**: Toggle between modes on UI. Compliance check with stub agents produces mock to-do list via SSE. Full audit path unchanged (zero regression). ✓

### Iteration 6 — Real Fetcher Node ✓ COMPLETE (2026-02-21)
- [x] Write `agents/fetcher.py` — Claude API call to validate Taxonomy financials
- [x] Feed `taxonomy_data` (structured iXBRL JSON) to Claude with `SYSTEM_PROMPT_FETCHER`
- [x] Parse JSON response into `TaxonomyFinancials` → populate `state["taxonomy_financials"]`

**Gate**: `taxonomy_financials.capex_total_eur` and `capex_green_eur` populated from real report JSON ✓

**Implementation notes**:
- `fetcher.py`: Real Claude API call using `anthropic.Anthropic()` client with `claude-sonnet-4-6` model
- Prompt caching enabled: `taxonomy_data` JSON sent with `cache_control: {"type": "ephemeral"}` per PRD Section 9
- `_parse_llm_json()`: Robust JSON parsing handles markdown fences (`json ... `), bare fences, and leading whitespace
- `_build_taxonomy_financials()`: Constructs `TaxonomyFinancials` Pydantic model from Claude's response; handles both nested (`{"taxonomy_financials": {...}}`) and flat response shapes
- `_safe_defaults()`: Returns zero-confidence `TaxonomyFinancials` with all financial fields as `None` on API error or parse failure — never halts the graph
- Error handling: all exceptions caught, logged to `state["logs"]`, and safe defaults returned
- `RegistrySource` populated with `name="Annual Management Report"`, `registry_type="eu_bris"`, `jurisdiction="EU"`
- Updated `tests/conftest.py`: Added shared mock helpers (`_make_mock_claude_response`, `MOCK_FETCHER_RESPONSE_JSON`, `MOCK_EXTRACTOR_RESPONSE_JSON`, `mock_anthropic_client` fixture)
- `backend/tests/test_iteration6.py` — 44 unit tests (API call construction, JSON parsing, TaxonomyFinancials building, safe defaults, error handling, state management, PRD gate, downstream integration), all passing
- `backend/tests/integration_test_fetcher.py` — manual integration test for live Claude API with real XHTML report
- All 242 tests across iterations 1, 2, 4, 6 passing; all 5 PRD gate checks green (`schemas OK`, `graph OK`, `parser OK`, `compliance_check gate OK`, `fetcher OK`)

### Iteration 7 — Real Auditor Node (Both Modes) ✓ COMPLETE
- [x] Write `agents/auditor.py` — full audit: scoring prompt + JSON parsing; compliance check: coverage assessment + cost estimate
- [x] Full audit: validate `capex_aligned_pct` math matches `taxonomy_financials`
- [x] Full audit: populate `esrs_ledger`, `taxonomy_alignment`, `compliance_cost`, `taxonomy_alignment_score`
- [x] Compliance check: populate `esrs_coverage`, `compliance_cost_estimate`

**Gate**: Full audit produces valid ESRS ledger. Compliance check produces valid coverage assessment + cost estimate range. ✓

---

**v5.0 PIVOT** — Iterations 8+ reflect the unified output architecture.
The system now produces a single `ComplianceResult` (score + recommendations) for both input
modes, replacing the separate `CSRDAudit` and `ComplianceCheckResult` contracts. The 4-agent
pipeline (extractor → fetcher → auditor → consultant) is consolidated to 3 agents
(extractor → scorer → advisor). See PRD Sections 1–6 for the full revised architecture.

---

### Iteration 8 — v5.0 Backend Pivot: Unified Schemas + 3-Agent Graph

Refactor the backend to match the new architecture. Replace old schemas/agents with unified ones.

- [ ] **Schemas pivot** (`schemas.py`):
  - Add new models: `CompanyInputs`, `ComplianceScore`, `Recommendation`, `ComplianceResult`, `FinancialContext`
  - Keep `CompanyMeta`, `PipelineTrace`, `AgentTiming`, `ESRSClaim` (internal)
  - Deprecate (leave in file, mark as legacy): `CSRDAudit`, `ComplianceCheckResult`, `TaxonomyAlignment`, `ComplianceCost`, `ESRSLedgerItem`, `TaxonomyRoadmap`, `RoadmapPillar`, `TaxonomyFinancials`, `ExtractedGoal`, `ESRSCoverageItem`, `ComplianceTodo`, `ComplianceCostEstimate`
  - Update `AgentName` literal: `"extractor" | "scorer" | "advisor"`
  - Update `Priority` to keep: `"critical" | "high" | "moderate" | "low"`

- [ ] **State pivot** (`state.py`):
  - Add new keys: `company_inputs`, `financial_context`, `compliance_score`, `applicable_reqs`, `coverage_gaps`, `recommendations`, `final_result`
  - Update `mode` values: `"structured_document" | "free_text"` (rename from `"full_audit" | "compliance_check"`)
  - Remove old keys: `extracted_goals`, `esrs_coverage`, `compliance_cost_estimate`, `todo_list`, `final_compliance_check`, `esrs_ledger`, `taxonomy_alignment`, `compliance_cost`, `taxonomy_alignment_score`, `roadmap`, `final_audit`, `taxonomy_financials`, `document_source`

- [ ] **Graph pivot** (`graph.py`):
  - Replace 4-node graph with 3-node: `extractor → scorer → advisor`
  - Remove conditional routing (all 3 nodes always run in both modes)
  - Remove `fetcher_node` and `consultant_node` imports
  - Add `scorer_node` and `advisor_node` imports

- [ ] **Prompts pivot** (`tools/prompts.py`):
  - Add new prompts: `SYSTEM_PROMPT_SCORER`, `SYSTEM_PROMPT_ADVISOR`
  - Update `SYSTEM_PROMPT_EXTRACTOR` — extract ALL ESRS standards + financial context
  - Update `SYSTEM_PROMPT_EXTRACTOR_LITE` — extract ALL ESRS standards from free text
  - Deprecate: `SYSTEM_PROMPT_FETCHER`, `SYSTEM_PROMPT_AUDITOR`, `SYSTEM_PROMPT_AUDITOR_LITE`, `SYSTEM_PROMPT_CONSULTANT`, `SYSTEM_PROMPT_CONSULTANT_LITE`

- [ ] **API pivot** (`main.py`):
  - Accept 4 new form fields: `number_of_employees`, `revenue_eur`, `total_assets_eur`, `reporting_year`
  - Update mode values: `"structured_document"` / `"free_text"`
  - SSE complete event: `{"type":"complete","result":{...ComplianceResult...}}` (unified)
  - Build `CompanyInputs` from form fields, add to initial state

- [ ] **Stub agents**:
  - Write `agents/scorer.py` — stub: deterministic score from esrs_claims count
  - Write `agents/advisor.py` — stub: generate dummy recommendations from coverage_gaps
  - Update `agents/extractor.py` — add `financial_context` output (structured doc mode)
  - Deprecate `agents/fetcher.py`, `agents/auditor.py`, `agents/consultant.py` (keep files, mark legacy)

**Gate**: 3-node graph runs end-to-end in both modes. `final_result` is a valid `ComplianceResult` with stub data. SSE streams `{"type":"complete","result":{...}}`. Old 4-node graph no longer invoked.

### Iteration 9 — Knowledge Base + Scoring Engine

Build the knowledge base infrastructure and real Scorer agent.

- [ ] Create `backend/data/` directory
- [ ] Add `master_requirements.json` — knowledge base with:
  - CSRD size-category thresholds (employees, revenue, assets)
  - All ESRS standards (E1–E5, S1–S4, G1, ESRS 2)
  - Per-standard disclosure requirements
  - Phase-in schedules by reporting year
- [ ] Add `backend/data/schemas/` — JSON Schema for validating knowledge base structure
- [ ] Write `backend/tools/knowledge_base.py`:
  - `load_requirements()` — parse + cache `master_requirements.json`
  - `determine_size_category(employees, revenue, assets)` — match against CSRD thresholds
  - `get_applicable_requirements(size_category, reporting_year)` — return filtered ESRS list
- [ ] Write real `agents/scorer.py`:
  - Load knowledge base via `knowledge_base.load_requirements()`
  - Read `company_inputs` → call `determine_size_category()`
  - Call `get_applicable_requirements()` → get mandatory standards list
  - Compare `esrs_claims` against applicable requirements
  - Classify each: "disclosed" (confidence ≥ 0.7 + value), "partial" (0.3–0.7), "missing" (< 0.3)
  - Compute overall score: `round(((disclosed * 1.0 + partial * 0.5) / total) * 100)`
  - Output: `compliance_score`, `applicable_reqs`, `coverage_gaps`
- [ ] Write `backend/tests/test_knowledge_base.py` — threshold matching, requirement filtering, phase-in logic
- [ ] Write `backend/tests/test_scorer.py` — scoring algorithm, edge cases (0 applicable, all disclosed, all missing)

**Gate**: Scorer produces valid `ComplianceScore` with `overall` 0–100 driven by knowledge base. `coverage_gaps` lists all applicable standards with correct status. Score formula: `(disclosed + partial*0.5) / total * 100`.

### Iteration 10 — Real Advisor Agent + Recommendation Generation

Build the real Advisor agent that generates grouped recommendations.

- [ ] Write real `agents/advisor.py`:
  - Read `compliance_score`, `coverage_gaps`, `financial_context`, `company_meta`
  - For each "missing" or "partial" standard in `coverage_gaps`:
    - Generate 1 `Recommendation` with title, description, regulatory_reference
    - Assign priority: "critical" (missing + mandatory), "high" (missing or partial with big gap), "moderate" (partial minor), "low" (disclosed but improvable)
  - If `financial_context` is not None: enrich descriptions with specific financial figures
  - Sort by priority tier (critical → high → moderate → low)
  - Assemble final `ComplianceResult` (score + recommendations + company + pipeline)
- [ ] Update `SYSTEM_PROMPT_ADVISOR` if Claude-generated recommendations are used
- [ ] Write `backend/tests/test_advisor.py` — recommendation generation, priority assignment, financial context enrichment

**Gate**: Advisor produces valid `Recommendation` list grouped by priority. Financial context enriches descriptions when available. `ComplianceResult` assembles correctly with pipeline timing.

### Iteration 11 — Frontend: Unified Result View + Company Inputs

Rebuild the frontend for the unified output and structured company inputs.

- [ ] **TypeScript types** (`types.ts`):
  - Add: `CompanyInputs`, `ComplianceScore`, `Recommendation`, `ComplianceResult`
  - Update `SSECompleteEvent`: `{ type: "complete", result: ComplianceResult }`
  - Update `AgentName`: `"extractor" | "scorer" | "advisor"`
  - Deprecate old types (keep for reference): `CSRDAudit`, `ComplianceCheckResult`, etc.

- [ ] **Unified result component** (`compliance-result-view.tsx` — NEW):
  - **Score section**: Large prominent score display (0–100), color-coded (green ≥ 70, amber ≥ 40, red < 40)
  - **Recommendations section**: Grouped by priority tier with collapsible sections:
    - Critical (red) — expanded by default
    - High (amber) — expanded by default
    - Moderate (yellow) — collapsed
    - Low (green) — collapsed
  - Each recommendation card: title, ESRS ID badge, description, regulatory reference
  - Same component for both modes — no mode indicator needed

- [ ] **Company inputs** (`audit-chamber.tsx`):
  - Add 4 structured input fields (employees, revenue, assets, year) on same page
  - Fields appear between entity input and document/text section
  - 2×2 grid layout
  - Required in both modes — `canRun` logic updated

- [ ] **Mode rename**:
  - Toggle labels: "Structured Document" / "Free Text" (replacing "Full Audit" / "Compliance Check")

- [ ] **API layer** (`api.ts`):
  - Both `startAuditRun()` and `startComplianceCheck()` → single `startAnalysis()` function
  - Sends all company inputs as form fields

- [ ] **Hook** (`useAuditStream.ts`):
  - Single `result: ComplianceResult | null` (replaces `audit` + `complianceCheck`)
  - SSE handles `{"type":"complete","result":{...}}`
  - Progress: always 3 agents

- [ ] **Mock data** (`mock-data.ts`):
  - Add `MOCK_COMPLIANCE_RESULT` with score + recommendations
  - Update `MOCK_LOGS` for 3-agent pipeline

- [ ] Remove old components: `results-view.tsx` (old audit view), `compliance-check-view.tsx` (old compliance view)

**Frontend layout** (idle page):
```
┌──────────────────────────────────────────────────────────────┐
│  ◉ Structured Document    ○ Free Text                        │
├──────────────────────────────────────────────────────────────┤
│  [Entity input]                            [Run Analysis]     │
├──────────────────────────────────────────────────────────────┤
│  Company Details                                              │
│  ┌──────────────┐ ┌──────────────┐                           │
│  │ Employees    │ │ Revenue (€)  │                           │
│  │ [    500   ] │ │ [85,000,000] │                           │
│  └──────────────┘ └──────────────┘                           │
│  ┌──────────────┐ ┌──────────────┐                           │
│  │ Assets (€)   │ │ Year         │                           │
│  │ [42,000,000] │ │ [   2025   ] │                           │
│  └──────────────┘ └──────────────┘                           │
├──────────────────────────────────────────────────────────────┤
│  (Structured Document mode)                                   │
│  ┌─ Annual Management Report ─────────────────┐              │
│  │ [drag & drop / click]                       │              │
│  └─────────────────────────────────────────────┘              │
│                     — OR —                                    │
│  (Free Text mode)                                             │
│  ┌─ Sustainability Description ───────────────┐              │
│  │ Paste or describe your current situation... │              │
│  └─────────────────────────────────────────────┘              │
└──────────────────────────────────────────────────────────────┘
```

**Result page** (same for both modes):
```
┌──────────────────────────────────────────────────────────────┐
│  Sustainability Compliance Score                              │
│                                                               │
│              ┌─────────────┐                                  │
│              │     72      │  ← large, color-coded            │
│              │   / 100     │                                  │
│              └─────────────┘                                  │
│  15 of 18 applicable standards addressed                      │
│  Company: Lumiere Systemes SA · Large Undertaking · 2025      │
├──────────────────────────────────────────────────────────────┤
│  Recommendations                                              │
│                                                               │
│  ▼ Critical (2)                        ← red, expanded       │
│  ┌─────────────────────────────────────────────────────┐     │
│  │ [E1-6] Conduct Scope 1 & 2 GHG inventory           │     │
│  │ Your GHG emissions are not disclosed. ESRS E1-6...  │     │
│  │ Ref: ESRS E1-6, DR E1-6.44                         │     │
│  └─────────────────────────────────────────────────────┘     │
│  ┌─────────────────────────────────────────────────────┐     │
│  │ [S1-1] Establish own workforce impact assessment    │     │
│  │ No workforce materiality data found. ESRS S1-1...   │     │
│  │ Ref: ESRS S1-1, DR S1-1.01                         │     │
│  └─────────────────────────────────────────────────────┘     │
│                                                               │
│  ▼ High (3)                            ← amber, expanded    │
│  ...                                                          │
│                                                               │
│  ▸ Moderate (4)                        ← yellow, collapsed  │
│  ▸ Low (6)                             ← green, collapsed   │
├──────────────────────────────────────────────────────────────┤
│  Pipeline: Extractor (2.1s) → Scorer (0.8s) → Advisor (3.2s)│
└──────────────────────────────────────────────────────────────┘
```

**Gate**: Both modes produce identical `ComplianceResult` rendered by same component. Score displays prominently. Recommendations grouped by priority tier. Company inputs required and visible. Old result views removed.

### Iteration 12 — Real Extractor (Unified)

Upgrade the extractor to handle ALL ESRS standards and financial context extraction in one pass.

- [ ] Refactor `agents/extractor.py`:
  - Structured doc mode: send BOTH `esrs_data` + `taxonomy_data` to Claude in one call
  - Extract claims for ALL ESRS standards found (not just E1)
  - Extract `financial_context` (CapEx/OpEx/Revenue) from taxonomy data
  - Free text mode: extract all identifiable ESRS claims, `financial_context = None`
- [ ] Update prompts: `SYSTEM_PROMPT_EXTRACTOR` and `SYSTEM_PROMPT_EXTRACTOR_LITE` per Section 6
- [ ] Write `backend/tests/test_extractor_v5.py` — both modes, all ESRS standards, financial context

**Gate**: Extractor populates `esrs_claims` with all found standards (not limited to E1). `financial_context` populated in structured doc mode, `None` in free text. Both modes flow through scorer → advisor without error.

### Iteration 13 — Polish + End-to-End Testing
- [ ] Remove deprecated agent files (`fetcher.py`, `auditor.py`, `consultant.py`) or archive
- [ ] Remove deprecated schema models and state keys
- [ ] Add `.env` / `dotenv` for `ANTHROPIC_API_KEY`
- [ ] Document `master_requirements.json` schema for knowledge base maintainers
- [ ] End-to-end test: both modes with real data + structured company inputs
- [ ] Performance check: 3-agent pipeline should be faster than old 4-agent pipeline

**Gate**: `uvicorn main:app --reload` + frontend in dev = full live demo. Both modes: enter company details → submit → see score + recommendations. Clean codebase with no deprecated code.

---

## 11. Critical Files Reference

| File | Why It Matters |
|------|---------------|
| [frontend/src/lib/types.ts](../frontend/src/lib/types.ts) | **Source of truth** for all Pydantic model field names — must match exactly |
| [frontend/src/lib/mock-data.ts](../frontend/src/lib/mock-data.ts) | Reference values for expected output shape |
| [frontend/src/components/audit-chamber.tsx](../frontend/src/components/audit-chamber.tsx) | SSE event consumption logic + input form — defines expected field names |
| [backend/data/master_requirements.json](../backend/data/master_requirements.json) | **Knowledge base** — all CSRD/ESRS thresholds, requirements, phase-in schedules |
| [backend/tools/knowledge_base.py](../backend/tools/knowledge_base.py) | Knowledge base loader + query functions |
| [contracts/audit-report.schema.ts](../contracts/audit-report.schema.ts) | Canonical re-export — confirms type names |

---

## 12. Verification Plan

```bash
# 1. Install dependencies
cd backend && pip install -r requirements.txt

# 2. Schema import test (v5.0 — unified ComplianceResult)
python -c "from schemas import ComplianceResult, ComplianceScore, Recommendation; print('schemas OK')"

# 3. Graph compile test (3-node pipeline)
python -c "from graph import graph; print('graph OK')"

# 4. Report parser test
python -c "from tools.report_parser import clean_report_json, extract_esrs_sections, extract_taxonomy_sections; print('parser OK')"

# 5. Knowledge base test
python -c "from tools.knowledge_base import load_requirements, determine_size_category; print('knowledge_base OK')"

# 6. Start server
uvicorn main:app --reload

# 7. Structured document mode
curl -X POST http://localhost:8000/audit/run \
  -F "report_json=@annual-management-report.json" \
  -F "entity_id=Lumiere Systemes SA" \
  -F "mode=structured_document" \
  -F "number_of_employees=500" \
  -F "revenue_eur=85000000" \
  -F "total_assets_eur=42000000" \
  -F "reporting_year=2025"
# → { "audit_id": "<uuid>" }

# 8. Stream result
curl -N http://localhost:8000/audit/<audit_id>/stream
# → SSE log lines (3 agents) + complete event with ComplianceResult JSON

# 9. Extraction validation
# Verify extractor reads ALL ESRS claims from esrs_data (iXBRL sections)
# Verify extractor extracts financial_context from taxonomy_data
# Verify scorer computes score from claims vs. knowledge base
# Verify advisor generates recommendations grouped by priority tier

# 10. Frontend end-to-end
# Set NEXT_PUBLIC_API_URL=http://localhost:8000
# Enter company details → upload report → see score + recommendations
# Toggle to free text → enter description → see same score + recommendations format
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

**Seam 3 — Scoring & Knowledge Base** (`tools/knowledge_base.py` + `data/master_requirements.json`):
All compliance thresholds, size-category rules, and ESRS requirements live in the knowledge base
JSON — tunable without code changes. Scoring algorithm is in `agents/scorer.py`. Recommendation
priority rules are in `SYSTEM_PROMPT_ADVISOR` (`tools/prompts.py`).

---

## 14. Dual-Input Mode Architecture (v5.0)

### 14.1 Overview

Both input modes (structured document and free text) produce the **same unified output**:
a `ComplianceResult` containing a compliance score (0–100) and prioritized recommendations.
The mode only affects the Extractor's data source and output confidence — the Scorer and
Advisor operate identically regardless of input mode.

### 14.2 Mode Comparison (v5.0)

| Aspect | Structured Document | Free Text |
|--------|-------------------|-----------|
| Input | Pre-parsed XHTML/iXBRL JSON file + company inputs | Free-text description + company inputs |
| Company inputs | employees, revenue (EUR), total assets (EUR), reporting year | Same |
| UI trigger | Default mode (file upload visible) | Toggle switch on same page |
| Pipeline | Extractor → Scorer → Advisor | Extractor → Scorer → Advisor (same) |
| Agent count | 3 | 3 |
| Output contract | `ComplianceResult` | `ComplianceResult` (identical) |
| Score formula | Disclosure completeness vs. knowledge base | Same formula |
| Financial context | Extracted (CapEx/OpEx/Revenue) → enriches recommendations | Not available (`null`) |
| Extraction confidence | High (structured iXBRL data) | Low-to-medium (best-effort from prose) |
| Recommendation quality | Higher (specific financial figures in descriptions) | Good (regulatory references, no financial specifics) |
| Progress bar | 3 agent steps | 3 agent steps |

### 14.3 Agent Architecture (v5.0)

All 3 agents run in **both modes**. The only difference is the Extractor's data source
and prompt variant. The Scorer and Advisor are mode-agnostic.

#### Agent 1: Extractor (mode-aware)

| | Structured Document | Free Text |
|---|-------------------|-----------|
| Prompt | `SYSTEM_PROMPT_EXTRACTOR` | `SYSTEM_PROMPT_EXTRACTOR_LITE` |
| Reads | `esrs_data` + `taxonomy_data` (iXBRL JSON) | `free_text_input` (raw text) |
| Writes | `esrs_claims`, `company_meta`, `financial_context` | `esrs_claims`, `company_meta`, `financial_context=None` |
| ESRS scope | All standards found in the document | All standards identifiable from text |
| Confidence | High (structured data) | Low-to-medium (best-effort from prose) |

#### Agent 2: Scorer (mode-agnostic)

| | Both Modes |
|---|-----------|
| Prompt | `SYSTEM_PROMPT_SCORER` |
| Reads | `esrs_claims` + `company_inputs` + knowledge base |
| Writes | `compliance_score`, `applicable_reqs`, `coverage_gaps` |
| Logic | Deterministic: size category → applicable standards → compare vs. claims → score |

#### Agent 3: Advisor (mode-agnostic)

| | Both Modes |
|---|-----------|
| Prompt | `SYSTEM_PROMPT_ADVISOR` |
| Reads | `compliance_score` + `coverage_gaps` + `financial_context` (may be None) + `company_meta` |
| Writes | `recommendations`, `final_result` (ComplianceResult) |
| Financial enrichment | If `financial_context` is not None, enriches recommendation descriptions |

### 14.4 Legacy Section Note

**Sections 14.4–14.12 below are preserved as historical reference for iterations 0–7.**
They document the pre-v5.0 architecture (4 agents, separate CSRDAudit/ComplianceCheckResult
contracts, say-vs-do gap analysis). The v5.0 architecture in Sections 1–6 and iterations 8+
supersedes this content. The legacy code from iterations 0–7 remains in the codebase and will
be cleaned up in Iteration 13.

---

## 15. Knowledge Base — `master_requirements.json`

### 15.1 Overview

The **knowledge base** is the single source of truth for all CSRD/ESRS compliance rules,
thresholds, and requirements. It replaces the previously hardcoded ESRS E1-only scoring rules
with a data-driven approach that covers **all ESRS standards** (E1–E5, S1–S4, G1, and CSRD
general obligations).

**File**: `backend/data/master_requirements.json`
**Loader**: `backend/tools/knowledge_base.py`
**Schemas**: `backend/data/schemas/` (JSON Schema files for validation)

### 15.2 Purpose

The knowledge base serves three functions:

1. **Size-category determination**: Given a company's `number_of_employees`, `revenue_eur`, and
   `total_assets_eur`, determine which CSRD size category they fall into (large undertaking,
   listed SME, micro-enterprise exempt, etc.) and which reporting obligations apply.

2. **Requirement mapping**: For a given size category + reporting year, determine exactly which
   ESRS standards and disclosure requirements are mandatory, which are subject to materiality
   assessment, and which are phased in for later years.

3. **Compliance scoring**: The Scorer agent reads the matched requirements and compares
   them against the extracted ESRS claims to compute the disclosure completeness score (0–100).
   The Advisor then reads the coverage gaps to generate prioritized recommendations.

### 15.3 Structured Company Inputs

Both modes (structured document and free text) accept **structured company inputs** alongside
their primary data source. These inputs are entered on the frontend **on the same page** as
the file upload or free-text area.

| Input | Type | Example | Purpose |
|-------|------|---------|---------|
| Number of Employees | integer | 500 | CSRD size-category threshold (≥250 = large) |
| Revenue (EUR) | float | 85000000.0 | CSRD size-category + fine calculation basis |
| Total Assets (EUR) | float | 42000000.0 | CSRD size-category threshold (≥25M = large) |
| Reporting Year | integer | 2025 | Determines phase-in schedule + applicable standards |

**Threshold logic**: The Scorer agent loads `master_requirements.json` (via `knowledge_base.py`),
matches the company's inputs against the thresholds defined therein, and determines:
- Whether the company is in scope for CSRD at all
- Which ESRS standards are mandatory for their size category
- Which requirements have phase-in dates that may not yet apply
- The applicable penalty regime (based on jurisdiction + revenue)

**All threshold values live in `master_requirements.json`** — no hardcoded size categories
in Python code. This allows the knowledge base to be updated independently when regulations change.

### 15.4 Knowledge Base Loader

**File**: `backend/tools/knowledge_base.py`

```python
import json
from pathlib import Path
from typing import Any

_KB_PATH = Path(__file__).parent.parent / "data" / "master_requirements.json"
_cache: dict | None = None

def load_requirements() -> dict:
    """Load and cache master_requirements.json. Called once per process."""
    global _cache
    if _cache is None:
        with open(_KB_PATH) as f:
            _cache = json.load(f)
    return _cache

def determine_size_category(
    employees: int,
    revenue_eur: float,
    total_assets_eur: float,
    requirements: dict | None = None,
) -> dict:
    """Match company inputs against CSRD size-category thresholds.

    Returns:
        { "category": str, "in_scope": bool, "applicable_standards": list[str], ... }
    """
    ...

def get_applicable_requirements(
    size_category: str,
    reporting_year: int,
    requirements: dict | None = None,
) -> list[dict]:
    """Return the list of ESRS requirements applicable to this company.

    Filters by size category and phase-in schedule for the reporting year.
    Each requirement includes: esrs_id, standard_name, mandatory (bool),
    phase_in_year (int | null), disclosure_requirements (list).
    """
    ...
```

### 15.5 ESRS Scope Expansion

The system now supports **all ESRS standards** defined in `master_requirements.json`, not just
E1 (Climate Change). The knowledge base determines which standards apply based on the company's
size category and reporting year.

| Category | Standards | Examples |
|----------|-----------|---------|
| Environmental | E1–E5 | E1 Climate Change, E2 Pollution, E3 Water, E4 Biodiversity, E5 Resource Use |
| Social | S1–S4 | S1 Own Workforce, S2 Workers in Value Chain, S3 Affected Communities, S4 Consumers |
| Governance | G1 | G1 Business Conduct |
| Cross-cutting | ESRS 1, ESRS 2 | General requirements, General disclosures |

**v5.0 scope**: `master_requirements.json` defines which standards exist, and the Scorer
iterates over whatever standards are applicable for the company's size category and reporting
year. The Extractor extracts all ESRS standards found in the input, regardless of mode.

### 15.6 Scorer + Advisor — Knowledge-Base-Driven Compliance (v5.0)

The Scorer (Node 2) and Advisor (Node 3) use `master_requirements.json` as their rule source.

**Scorer flow** (deterministic — no LLM call needed for scoring logic):
```
1. Load master_requirements.json via knowledge_base.load_requirements()
2. Read company_inputs from state (employees, revenue, assets, year)
3. determine_size_category() → get the company's CSRD category
4. get_applicable_requirements() → list of ESRS standards that apply
5. Compare applicable requirements against esrs_claims from Extractor
6. Classify each: "disclosed" (confidence ≥ 0.7 + value), "partial" (0.3–0.7), "missing" (< 0.3)
7. Compute score: round(((disclosed * 1.0 + partial * 0.5) / total) * 100)
8. Output: compliance_score, applicable_reqs, coverage_gaps
```

**Advisor flow** (LLM-powered — generates natural language recommendations):
```
1. Read compliance_score + coverage_gaps from Scorer
2. Read financial_context from Extractor (may be None in free text mode)
3. For each "missing" or "partial" standard:
   - Generate 1 Recommendation with title, description, regulatory_reference
   - Assign priority: critical/high/moderate/low based on gap severity
4. If financial_context is available: enrich descriptions with specific figures
5. Sort by priority tier (critical → low)
6. Assemble final ComplianceResult (score + recommendations + company + pipeline)
```

**Key design**: Neither agent assumes a fixed set of ESRS standards. Both iterate over whatever
standards `master_requirements.json` deems applicable for the company's size category and
reporting year. Recommendations are generated dynamically based on the matched requirements.
