// ============================================================================
// EU CSRD Compliance Engine — API Contract v3.0
// ============================================================================
// Unified 3-agent pipeline: extractor → scorer → advisor.
// Both input modes produce the same ComplianceResult.
// ============================================================================

// Re-exports from frontend/src/lib/types.ts — keep in sync.
// This file is the canonical contract; the frontend copy is derived from it.

export type {
  CompanyMeta,
  CompanyInputs,
  ComplianceScore,
  Priority,
  Recommendation,
  AgentName,
  AgentTiming,
  PipelineTrace,
  AuditLog,
  ComplianceResult,
  SSELogEvent,
  SSENodeCompleteEvent,
  SSECompleteEvent,
  SSEErrorEvent,
  SSEEvent,
} from "../frontend/src/lib/types";
