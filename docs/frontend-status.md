# Frontend Status & API Integration Layer
## EU AI Infrastructure Accountability Engine — Frontend Progress Report

**Last updated**: 2026-02-21
**Frontend framework**: Next.js 14.2.35 · React 18 · TypeScript 5 · Tailwind CSS 3.4

---

## 1. Current State: Production-Ready UI + API Layer Wired

The frontend is **feature-complete** and **build-passing** (`next build` clean, zero type errors).
It runs in two modes controlled by a single env var:

| Mode | `NEXT_PUBLIC_USE_MOCK` | Behaviour |
|------|------------------------|-----------|
| **Mock** (default) | `true` | Hardcoded `MOCK_AUDIT` + `AUDIT_LOGS` with `setTimeout` playback. Zero network calls. |
| **Live** | `false` | `POST /audit/run` (multipart) → SSE stream via `EventSource`. Requires running backend. |

Flipping the toggle requires no code changes — just edit `.env.local` and restart the dev server.

---

## 2. File Structure

```
frontend/
├── .env.local                          # NEXT_PUBLIC_USE_MOCK=true, NEXT_PUBLIC_API_URL
├── .env.example                        # Checked-in template for the above
│
├── src/
│   ├── app/
│   │   ├── layout.tsx                  # Root layout (fonts, metadata)
│   │   ├── page.tsx                    # Single route — renders <AuditChamber />
│   │   └── globals.css                 # Tailwind base + custom animations
│   │
│   ├── components/
│   │   ├── audit-chamber.tsx           # Main orchestrator — idle / analyzing / complete states
│   │   └── results-view.tsx            # Renders the full CSRDAudit report
│   │
│   ├── hooks/
│   │   └── useAuditStream.ts           # Custom hook: mock vs. real flow, cleanup, state
│   │
│   └── lib/
│       ├── config.ts                   # Reads env vars → typed { useMock, apiUrl } object
│       ├── api.ts                      # startAuditRun() (POST) + streamAuditEvents() (SSE)
│       ├── types.ts                    # Full TypeScript contract (CSRDAudit + SSE event types)
│       ├── mock-data.ts                # MOCK_AUDIT + AUDIT_LOGS (21 timed log entries)
│       └── utils.ts                    # Shared utility functions
```

---

## 3. Architecture

```
.env.local (toggle)
    ↓
config.ts (reads env)
    ↓
useAuditStream.ts (branches on config.useMock)
    ├── MOCK PATH: setTimeout playback of AUDIT_LOGS → MOCK_AUDIT
    └── REAL PATH: api.ts → POST /audit/run → EventSource SSE stream
            ↓
audit-chamber.tsx (thin UI layer consuming the hook)
    ↓
results-view.tsx (receives CSRDAudit prop — unchanged either path)
```

### Data flow detail

1. **Idle** — User enters entity name, uploads 3 PDFs into document vault slots.
2. **Analyzing** — `useAuditStream.startAudit(entity, files)` fires.
   - Mock: replays `AUDIT_LOGS` via `setTimeout`, then sets `MOCK_AUDIT` as the result.
   - Real: `POST /audit/run` with multipart form (entity + 3 PDF files) → receives `run_id` → opens `EventSource` on `GET /audit/stream/{run_id}`.
3. **Complete** — `audit` state populated → `<ResultsView audit={audit} />` renders.

---

## 4. API Contract (Frontend ↔ Backend)

### `POST /audit/run`

**Request**: `multipart/form-data`

| Field | Type | Required |
|-------|------|----------|
| `entity` | string | yes |
| `management_report` | File (PDF) | yes |
| `taxonomy_table` | File (PDF) | yes |
| `transition_plan` | File (PDF) | yes |

**Response**: `{ "run_id": "<uuid>" }`

### `GET /audit/stream/{run_id}` (SSE)

Server-Sent Events stream. Each event's `data` field is JSON matching one of:

```typescript
// Agent log line (displayed in the terminal UI)
{ type: "log", agent: AgentName, message: string, timestamp: string }

// Agent finished its node (drives progress bar: completedNodes / 4)
{ type: "node_complete", agent: AgentName, duration_ms: number }

// Audit finished — full result payload
{ type: "complete", audit: CSRDAudit }

// Fatal error — displayed to user, stream closes
{ type: "error", message: string }
```

`AgentName` = `"extractor" | "fetcher" | "auditor" | "consultant"`

---

## 5. Key Components

### `useAuditStream` hook

Returns all state the UI needs — the component is a thin consumer:

```typescript
{
  step: "idle" | "analyzing" | "complete",
  logs: AuditLog[],
  audit: CSRDAudit | null,
  error: string | null,
  progress: number,         // 0–1 (mock: logs/total, real: nodes/4)
  totalLogs: number,        // mock: known count, real: -1 (unknown)
  startAudit: (entity, files) => void,
  skipToComplete: () => void,
  reset: () => void,
}
```

- Manages all cleanup (clears `setTimeout` timers in mock mode, closes `EventSource` in real mode).
- Safe for unmount mid-stream — no console errors or dangling connections.

### `audit-chamber.tsx`

- **`filesRef`**: `useRef<Record<DocumentSlot, File | null>>` stores actual `File` objects for upload. Separate from `docs` state (which holds filename strings for display). No extra re-renders.
- **Error display**: Red banner above the chamber card when API calls fail.
- **Null audit handling**: If `step === "complete"` but `audit` is null, shows "No audit data available" with a reset button.

### `config.ts`

```typescript
export const config = {
  useMock: process.env.NEXT_PUBLIC_USE_MOCK !== "false",  // default: true
  apiUrl: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
} as const;
```

---

## 6. TypeScript Contract (`types.ts`)

The contract defines the complete `CSRDAudit` response schema that both frontend and backend must honour:

| Interface | Purpose |
|-----------|---------|
| `CSRDAudit` | Top-level response (audit_id, company, taxonomy_alignment, esrs_ledger, roadmap, pipeline, sources) |
| `CompanyMeta` | Entity metadata (name, LEI, sector, fiscal year, jurisdiction) |
| `TaxonomyAlignment` | Primary metric — CapEx-aligned percentage + status |
| `ComplianceCost` | Projected Art. 51 CSRD fine |
| `ESRSLedgerItem` | Per-data-point double materiality row (E1-1, E1-5, etc.) |
| `TaxonomyRoadmap` | Three-pillar improvement plan (hardware, power, workload) |
| `RegistrySource` | Registry metadata |
| `Source` | Document source references |
| `PipelineTrace` | Agent execution timing |
| `SSEEvent` | Union of `log` / `node_complete` / `complete` / `error` SSE events |

---

## 7. What's Done vs. What's Next

### Done (Frontend)

- [x] Document vault UI — 3-slot drag-and-drop + file picker (PDF/XHTML)
- [x] Entity input with keyboard submit
- [x] Analyzing view — progress bar, live log terminal with agent-coloured badges
- [x] Results view — full CSRDAudit rendering (taxonomy gauge, ESRS ledger, roadmap, pipeline trace)
- [x] Mock data system — realistic 21-log sequence with timed playback
- [x] API integration layer — `POST /audit/run` + SSE `EventSource` streaming
- [x] Environment-based mock/live toggle (zero code changes to switch)
- [x] Error handling — network failures, parse errors, connection loss
- [x] Cleanup — safe unmount mid-stream (timers cleared, SSE closed)
- [x] TypeScript strict — zero type errors, clean `next build`

### Next (Backend — see `docs/PRD-agentic-backend.md`)

- [ ] FastAPI scaffold (`main.py`, CORS, `/audit/run` + `/audit/stream/{run_id}`)
- [ ] LangGraph state machine with 4-agent pipeline
- [ ] PDF text extraction for all 3 golden-source documents
- [ ] Agent implementations (Extractor, Fetcher, Auditor, Consultant)
- [ ] SSE streaming from LangGraph node callbacks
- [ ] Pydantic schemas mirroring TypeScript contract 1:1

### Verification Checklist

| Scenario | Expected |
|----------|----------|
| `USE_MOCK=true` → upload 3 docs → "Run Audit" | Logs play back, skip works, results render with mock data |
| `USE_MOCK=false` + backend running → upload 3 PDFs → "Run Audit" | POST succeeds, SSE logs stream, results render with real data |
| `USE_MOCK=false` + backend down → "Run Audit" | Error banner shown, app returns to idle |
| Start audit → navigate away mid-stream | No console errors, EventSource closed |
