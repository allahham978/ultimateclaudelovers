// ============================================================================
// EU CSRD Compliance Engine — API Contract v3.0 (Unified Output)
// ============================================================================

// ============================================================================
// v5.0 — Unified Output Contract (Iteration 11+)
// Both input modes produce the same ComplianceResult.
// ============================================================================

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

export interface Recommendation {
  id: string;
  priority: Priority; // "critical" | "high" | "moderate" | "low"
  esrs_id: string;
  title: string;
  description: string;
  regulatory_reference: string;
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
// v5.0 Agent Names (3-agent pipeline)
// ---------------------------------------------------------------------------

export type V5AgentName = "extractor" | "scorer" | "advisor";

// ============================================================================
// DEPRECATED — Legacy v2.0 types below (kept for compilation, iteration 13 cleanup)
// ============================================================================

// ---------------------------------------------------------------------------
// 1. Top-Level Response (DEPRECATED — use ComplianceResult)
// ---------------------------------------------------------------------------

/** @deprecated Use ComplianceResult instead — will be removed in iteration 13 */
export interface CSRDAudit {
  audit_id: string;
  generated_at: string;
  schema_version: "2.0";

  company: CompanyMeta;
  taxonomy_alignment: TaxonomyAlignment;
  compliance_cost: ComplianceCost;
  esrs_ledger: ESRSLedgerItem[];
  roadmap: TaxonomyRoadmap;
  registry_source: RegistrySource;
  sources: Source[];
  pipeline: PipelineTrace;
}

// ---------------------------------------------------------------------------
// 2. Company Metadata (EU-focused)
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
// 3. EU Taxonomy Alignment (Primary Metric)
// ---------------------------------------------------------------------------

export interface TaxonomyAlignment {
  capex_aligned_pct: number; // 0-100 — % of CapEx qualifying as green
  status: TaxonomyStatus;
  label: string; // e.g. "Partially Aligned"
}

export type TaxonomyStatus =
  | "aligned"
  | "partially_aligned"
  | "non_compliant";

// ---------------------------------------------------------------------------
// 4. Financial Materiality — Cost of Non-Compliance
// ---------------------------------------------------------------------------

export interface ComplianceCost {
  projected_fine_eur: number;
  basis: string; // legal basis for the fine calculation
}

// ---------------------------------------------------------------------------
// 5. ESRS Ledger (Double Materiality View)
// ---------------------------------------------------------------------------

export interface ESRSLedgerItem {
  id: string;
  esrs_id: string; // e.g. "E1-1", "S1-6", "G1-1"
  data_point: string; // what the ESRS standard requires
  impact_materiality: MaterialityLevel;
  financial_materiality: MaterialityLevel;
  status: ESRSStatus;
  evidence_source: EvidenceSource; // which golden-source document provided evidence
  registry_evidence: string; // e.g. "Infogreffe — Rapport de gestion 2025"
}

export type EvidenceSource =
  | "management_report"
  | "taxonomy_table"
  | "transition_plan";

export type MaterialityLevel = "high" | "medium" | "low" | "not_material";
export type ESRSStatus = "disclosed" | "partial" | "missing" | "non_compliant";

// ---------------------------------------------------------------------------
// 6. Taxonomy Roadmap (Three-Pillar with projected alignment increase)
// ---------------------------------------------------------------------------

export interface TaxonomyRoadmap {
  hardware: RoadmapPillar;
  power: RoadmapPillar;
  workload: RoadmapPillar;
}

export interface RoadmapPillar {
  title: string;
  summary: string;
  priority: Priority;
  alignment_increase_pct: number; // e.g. 18 means +18% taxonomy alignment
}

export type Priority = "critical" | "high" | "moderate" | "low";

// ---------------------------------------------------------------------------
// 7. Registry Source
// ---------------------------------------------------------------------------

export interface RegistrySource {
  name: string; // e.g. "Infogreffe - France"
  registry_type: "national" | "eu_bris";
  jurisdiction: string;
}

// ---------------------------------------------------------------------------
// 8. Sources
// ---------------------------------------------------------------------------

export interface Source {
  id: string;
  document_name: string;
  document_type:
    | "csrd_report"
    | "eu_registry"
    | "national_filing"
    | "third_party";
  url: string | null;
}

// ---------------------------------------------------------------------------
// 9. Pipeline & Logs (unchanged)
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

/** @deprecated Use V5AgentName instead — will be removed in iteration 13 */
export type AgentName = "extractor" | "fetcher" | "auditor" | "consultant" | "scorer" | "advisor";

export interface AuditLog {
  timestamp: number;
  agent: AgentName;
  message: string;
}

// ---------------------------------------------------------------------------
// 10. SSE Event Types (real-time streaming from backend)
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
  result?: ComplianceResult; // v5.0 unified output
  audit?: CSRDAudit; // deprecated — legacy v2.0
  compliance_check?: ComplianceCheckResult; // deprecated — legacy v2.0
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

// ============================================================================
// Compliance Check Mode — Output Contract (DEPRECATED — use ComplianceResult)
// ============================================================================

/** @deprecated Use ComplianceResult instead — will be removed in iteration 13 */
export interface ComplianceCheckResult {
  audit_id: string;
  generated_at: string;
  schema_version: "2.0";
  mode: "compliance_check";

  company: CompanyMeta;
  extracted_goals: ExtractedGoal[];
  esrs_coverage: ESRSCoverageItem[];
  todo_list: ComplianceTodo[];
  estimated_compliance_cost: ComplianceCostEstimate;
  pipeline: PipelineTrace;
}

export interface ExtractedGoal {
  id: string;
  description: string;
  esrs_relevance: string | null;
  confidence: number;
}

export type CoverageLevel = "covered" | "partial" | "not_covered";

export interface ESRSCoverageItem {
  esrs_id: string;
  standard_name: string;
  coverage: CoverageLevel;
  details: string;
}

export interface ComplianceTodo {
  id: string;
  priority: Priority;
  esrs_id: string;
  title: string;
  description: string;
  regulatory_reference: string;
  estimated_effort: "low" | "medium" | "high";
}

export interface ComplianceCostEstimate {
  estimated_range_low_eur: number;
  estimated_range_high_eur: number;
  basis: string;
  caveat: string;
}
