// ============================================================================
// EU CSRD Compliance Engine — API Contract v2.0
// ============================================================================
// Single JSON shape from multi-agent backend → Next.js frontend.
// Pivoted from generic ESG audit to EU CSRD / ESRS / Taxonomy compliance.
// ============================================================================

// Re-exports from frontend/src/lib/types.ts — keep in sync.
// This file is the canonical contract; the frontend copy is derived from it.

export type {
  CSRDAudit,
  CompanyMeta,
  TaxonomyAlignment,
  TaxonomyStatus,
  ComplianceCost,
  ESRSLedgerItem,
  MaterialityLevel,
  ESRSStatus,
  TaxonomyRoadmap,
  RoadmapPillar,
  Priority,
  RegistrySource,
  Source,
  PipelineTrace,
  AgentTiming,
  AgentName,
  AuditLog,
} from "../frontend/src/lib/types";
