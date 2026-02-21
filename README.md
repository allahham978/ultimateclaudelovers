# AI Infrastructure Accountability Engine

## Scope

A B2B consulting platform that audits the gap between corporate sustainability claims and financial reality. A company uploads their ESG report as a PDF. Four specialized AI agents extract claims, fetch CapEx data, score alignment, and generate a three-pillar optimization roadmap.

The output is a single-page audit report showing the **Compute-to-Carbon Gap** — one number that answers: *are you spending where you're promising?*

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      FRONTEND                           │
│                  Next.js + TypeScript                    │
│                                                         │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │ Gap Score │  │ Say vs. Do   │  │ Three-Pillar Plan │  │
│  │  0-100    │  │   Ledger     │  │ HW / Power / Work │  │
│  └──────────┘  └──────────────┘  └───────────────────┘  │
│                  ┌──────────────┐                        │
│                  │   Pipeline   │                        │
│                  │   Timeline   │                        │
│                  └──────────────┘                        │
└──────────────────────┬──────────────────────────────────┘
                       │
                       │  AuditReport (typed JSON contract)
                       │
┌──────────────────────┴──────────────────────────────────┐
│                      BACKEND                            │
│              LangGraph Multi-Agent Pipeline              │
│              Anthropic Claude 3.5 Sonnet                 │
│                                                         │
│  PDF ──▶ [Extractor] ──▶ [Fetcher] ──▶ [Auditor] ──▶ [Consultant] │
│           parse ESG      fetch CapEx    score gaps    gen roadmap   │
│           claims         from filings   0-100 each   3 pillars     │
└─────────────────────────────────────────────────────────┘
```

## Contract-First Workflow

The frontend and backend are decoupled by a single TypeScript interface: **`AuditReport`**.

```
contracts/
├── audit-report.schema.ts   ← the typed contract (source of truth)
└── audit-report.mock.ts     ← realistic mock data for UI development
```

The frontend team builds against mock data. The backend team builds agents that produce the same shape. Neither blocks the other.

### AuditReport Shape

| Section | Purpose | Key Fields |
|---|---|---|
| `company` | Profile metadata | `name`, `ticker`, `sector`, `fiscal_year`, `report_title` |
| `gap_score` | Single headline metric (0-100) | `value`, `label` |
| `ledger[]` | 3-5 Say vs. Do rows | `the_say.claim`, `the_do.finding`, `alignment_score` |
| `recommendations` | Three-pillar roadmap | `hardware`, `power`, `workload` — each with `title`, `summary`, `priority` |
| `sources[]` | Consolidated citations | `document_name`, `document_type`, `url` |
| `pipeline` | Agent execution timeline | `agents[]` with `name`, `duration_ms`, `status` |

### UI Rendering Rules

- **alignment_score** drives a red-to-green color gradient (0 = stark red, 100 = crisp green)
- **Ledger items** are ordered worst-first (lowest score at the top)
- **Priority** on each pillar is one of: `critical`, `high`, `moderate`, `low`
- **Pipeline timeline** is visible to the user to build trust in the agent process

## Agent Pipeline

| Agent | Input | Output | Tools |
|---|---|---|---|
| **Extractor** | Raw ESG PDF | Parsed sustainability claims | PDF parser, Claude prompt cache |
| **Fetcher** | Company identifiers | CapEx line items from public filings | SEC EDGAR, financial APIs |
| **Auditor** | Claims + CapEx data | Scored ledger (0-100 per claim) + aggregate gap score | Claude financial reasoning |
| **Consultant** | Scored ledger | Three-pillar recommendation summaries | Claude synthesis |

Agents run sequentially. Each agent's output is the next agent's input. The pipeline trace records duration and status for each step.

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js, TypeScript |
| Backend Orchestration | LangGraph (Python) |
| LLM | Anthropic Claude 3.5 Sonnet |
| LLM Optimization | Prompt Caching, XML-tag processing |
| Contract | TypeScript interfaces (`contracts/`) |

## Project Philosophy

- **Less is better.** One page, one score, one ledger, one plan. No dashboard clutter.
- **Truly agentic.** Agents use tool calling and multi-step reasoning, not prompt chaining.
- **Anthropic-first.** Optimized for Claude's strengths: prompt caching, XML tags, financial reasoning.
- **Contract-first.** Frontend and backend teams never block each other.
