// ============================================================================
// AI Infrastructure Accountability Engine — API Contract v1.0
// ============================================================================
// This is the SINGLE shape that flows from the multi-agent backend to the
// Next.js frontend. Both teams build against this contract independently.
// ============================================================================

// ---------------------------------------------------------------------------
// 1. Top-Level Response
// ---------------------------------------------------------------------------

export interface AuditReport {
  audit_id: string;                   // uuid — stable key for persistence
  generated_at: string;               // ISO 8601 timestamp
  schema_version: "1.0";

  company: CompanyMeta;
  gap_score: GapScore;
  ledger: LedgerItem[];               // 3-5 items, ordered by severity (worst first)
  recommendations: ThreePillarPlan;
  sources: Source[];                   // global consolidated list
  pipeline: PipelineTrace;
}

// ---------------------------------------------------------------------------
// 2. Company Metadata (from profile + PDF extraction)
// ---------------------------------------------------------------------------

export interface CompanyMeta {
  name: string;                       // e.g. "Anthropic"
  ticker: string | null;              // null for private companies
  sector: string;                     // e.g. "AI / Cloud Infrastructure"
  fiscal_year: number;                // e.g. 2025
  report_title: string;               // title of the uploaded ESG document
}

// ---------------------------------------------------------------------------
// 3. Aggregate Gap Score
// ---------------------------------------------------------------------------

export interface GapScore {
  value: number;                      // 0-100. 0 = full misalignment, 100 = full alignment
  label: string;                      // human-readable, e.g. "Significant Gap"
}

// ---------------------------------------------------------------------------
// 4. Say vs. Do Ledger
// ---------------------------------------------------------------------------

export interface LedgerItem {
  id: string;                         // stable key for React rendering
  category: LedgerCategory;

  the_say: {
    claim: string;                    // verbatim or paraphrased claim from ESG report
    source_ref: string;               // e.g. "ESG Report 2025, p.14"
  };

  the_do: {
    finding: string;                  // what the CapEx data actually shows
    capex_usd: number | null;         // dollar figure if quantifiable, null otherwise
    source_ref: string;               // e.g. "10-K Filing 2025, Note 7"
  };

  alignment_score: number;            // 0-100, drives red-to-green gradient
}

export type LedgerCategory =
  | "energy"
  | "emissions"
  | "hardware"
  | "water"
  | "waste";

// ---------------------------------------------------------------------------
// 5. Three-Pillar Recommendations (Summary-only for V1)
// ---------------------------------------------------------------------------

export interface ThreePillarPlan {
  hardware: PillarSummary;
  power: PillarSummary;
  workload: PillarSummary;
}

export interface PillarSummary {
  title: string;                      // e.g. "Hardware Upgrades"
  summary: string;                    // 2-3 sentence recommendation
  priority: Priority;
}

export type Priority = "critical" | "high" | "moderate" | "low";

// ---------------------------------------------------------------------------
// 6. Sources (Global consolidated list)
// ---------------------------------------------------------------------------

export interface Source {
  id: string;                         // e.g. "src-1", referenced by ledger source_refs
  document_name: string;
  document_type: "esg_report" | "sec_filing" | "press_release" | "third_party";
  url: string | null;                 // public link if available
}

// ---------------------------------------------------------------------------
// 7. Agent Pipeline Trace (visible to user — simple timeline)
// ---------------------------------------------------------------------------

export interface PipelineTrace {
  total_duration_ms: number;
  agents: AgentTiming[];
}

export interface AgentTiming {
  agent: AgentName;
  duration_ms: number;
  status: "completed" | "failed" | "skipped";
}

export type AgentName =
  | "extractor"
  | "fetcher"
  | "auditor"
  | "consultant";
