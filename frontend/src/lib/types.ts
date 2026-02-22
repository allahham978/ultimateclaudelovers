// ============================================================================
// EU CSRD Compliance Engine — API Contract v3.0 (Unified Output)
// ============================================================================
// Both input modes (structured_document & free_text) produce the same
// ComplianceResult. 3-agent pipeline: extractor → scorer → advisor.
// ============================================================================

// ---------------------------------------------------------------------------
// Company Metadata (EU-focused)
// ---------------------------------------------------------------------------

export interface CompanyMeta {
  name: string;
  lei: string | null; // Legal Entity Identifier
  sector: string;
  fiscal_year: number;
  jurisdiction: string; // e.g. "France"
  report_title: string;
}

// ---------------------------------------------------------------------------
// Company Inputs (structured fields from the user)
// ---------------------------------------------------------------------------

export interface CompanyInputs {
  number_of_employees: number;
  revenue_eur: number;
  total_assets_eur: number;
  reporting_year: number;
}

// ---------------------------------------------------------------------------
// Compliance Score (0–100)
// ---------------------------------------------------------------------------

export interface ComplianceScore {
  overall: number; // 0–100
  size_category: string; // e.g. "large_undertaking"
  applicable_standards_count: number;
  disclosed_count: number;
  partial_count: number;
  missing_count: number;
}

// ---------------------------------------------------------------------------
// Recommendation (grouped by priority tier in the UI)
// ---------------------------------------------------------------------------

export type Priority = "critical" | "high" | "moderate" | "low";

export interface Recommendation {
  id: string;
  priority: Priority;
  esrs_id: string;
  title: string;
  description: string;
  regulatory_reference: string;
  category?: string;
  impact?: string;
}

// ---------------------------------------------------------------------------
// Pipeline & Logs
// ---------------------------------------------------------------------------

export type AgentName = "extractor" | "scorer" | "advisor";

export interface AgentTiming {
  agent: AgentName;
  duration_ms: number;
  status: "completed" | "failed" | "skipped";
}

export interface PipelineTrace {
  total_duration_ms: number;
  agents: AgentTiming[];
}

export interface AuditLog {
  timestamp: number;
  agent: AgentName;
  message: string;
}

// ---------------------------------------------------------------------------
// ComplianceResult — Unified top-level response for both input modes
// ---------------------------------------------------------------------------

export interface ComplianceResult {
  audit_id: string;
  generated_at: string;
  schema_version: string;
  mode: "structured_document" | "free_text";
  company: CompanyMeta;
  company_inputs: CompanyInputs;
  score: ComplianceScore;
  recommendations: Recommendation[];
  pipeline: PipelineTrace;
}

// ---------------------------------------------------------------------------
// SSE Event Types (real-time streaming from backend)
// ---------------------------------------------------------------------------

export interface SSELogEvent {
  type: "log";
  agent: AgentName;
  message: string;
  timestamp: string;
}

export interface SSENodeCompleteEvent {
  type: "node_complete";
  agent: AgentName;
  duration_ms: number;
}

export interface SSECompleteEvent {
  type: "complete";
  result?: ComplianceResult;
}

export interface SSEErrorEvent {
  type: "error";
  message: string;
}

export type SSEEvent =
  | SSELogEvent
  | SSENodeCompleteEvent
  | SSECompleteEvent
  | SSEErrorEvent;
