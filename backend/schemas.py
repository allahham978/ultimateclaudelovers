"""
Pydantic v2 models — mirrors the TypeScript contract in frontend/src/lib/types.ts exactly.
Field names must match 1:1. No renames, no extra fields on the public contract.
"""

from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Enum-like Literals (mirror TypeScript union types)
# ---------------------------------------------------------------------------

TaxonomyStatus = Literal["aligned", "partially_aligned", "non_compliant"]
MaterialityLevel = Literal["high", "medium", "low", "not_material"]
ESRSStatus = Literal["disclosed", "partial", "missing", "non_compliant"]
Priority = Literal["critical", "high", "moderate", "low"]
AgentName = Literal["extractor", "scorer", "advisor", "fetcher", "auditor", "consultant"]
EvidenceSource = Literal["management_report", "taxonomy_table", "transition_plan"]


# ---------------------------------------------------------------------------
# 2. Company Metadata
# ---------------------------------------------------------------------------

class CompanyMeta(BaseModel):
    name: str
    lei: Optional[str] = None
    sector: str
    fiscal_year: int
    jurisdiction: str
    report_title: str


# ---------------------------------------------------------------------------
# 3. EU Taxonomy Alignment
# ---------------------------------------------------------------------------

# LEGACY v2.0
class TaxonomyAlignment(BaseModel):
    capex_aligned_pct: float  # 0–100
    status: TaxonomyStatus
    label: str


# ---------------------------------------------------------------------------
# 4. Compliance Cost
# ---------------------------------------------------------------------------

# LEGACY v2.0
class ComplianceCost(BaseModel):
    projected_fine_eur: float
    basis: str


# ---------------------------------------------------------------------------
# 5. ESRS Ledger
# ---------------------------------------------------------------------------

# LEGACY v2.0
class ESRSLedgerItem(BaseModel):
    id: str
    esrs_id: str
    data_point: str
    impact_materiality: MaterialityLevel
    financial_materiality: MaterialityLevel
    status: ESRSStatus
    evidence_source: EvidenceSource = "management_report"
    registry_evidence: str


# ---------------------------------------------------------------------------
# 6. Taxonomy Roadmap
# ---------------------------------------------------------------------------

# LEGACY v2.0
class RoadmapPillar(BaseModel):
    title: str
    summary: str
    priority: Priority
    alignment_increase_pct: float


# LEGACY v2.0
class TaxonomyRoadmap(BaseModel):
    hardware: RoadmapPillar
    power: RoadmapPillar
    workload: RoadmapPillar


# ---------------------------------------------------------------------------
# 7. Registry Source
# ---------------------------------------------------------------------------

class RegistrySource(BaseModel):
    name: str
    registry_type: Literal["national", "eu_bris"]
    jurisdiction: str


# ---------------------------------------------------------------------------
# 8. Sources
# ---------------------------------------------------------------------------

class Source(BaseModel):
    id: str
    document_name: str
    document_type: Literal["csrd_report", "eu_registry", "national_filing", "third_party"]
    url: Optional[str] = None


# ---------------------------------------------------------------------------
# 9. Pipeline Trace
# ---------------------------------------------------------------------------

class AgentTiming(BaseModel):
    agent: AgentName
    duration_ms: int
    status: Literal["completed", "failed", "skipped"]


class PipelineTrace(BaseModel):
    total_duration_ms: int
    agents: list[AgentTiming]


# ---------------------------------------------------------------------------
# 10. Audit Log (internal — streamed via SSE, not in final JSON)
# ---------------------------------------------------------------------------

class AuditLog(BaseModel):
    timestamp: int  # epoch ms
    agent: AgentName
    message: str


# ---------------------------------------------------------------------------
# 1. Top-Level Response
# ---------------------------------------------------------------------------

# LEGACY v2.0
class CSRDAudit(BaseModel):
    audit_id: str
    generated_at: str  # ISO 8601
    schema_version: Literal["2.0"] = "2.0"

    company: CompanyMeta
    taxonomy_alignment: TaxonomyAlignment
    compliance_cost: ComplianceCost
    esrs_ledger: list[ESRSLedgerItem]
    roadmap: TaxonomyRoadmap
    registry_source: RegistrySource
    sources: list[Source]
    pipeline: PipelineTrace


# ---------------------------------------------------------------------------
# Internal schemas — used inside the state machine, not in the API contract
# ---------------------------------------------------------------------------

class ESRSClaim(BaseModel):
    """Extracted claim from ESRS sections of the management report JSON — internal to extractor node."""
    standard: str               # "E1-1" | "E1-5" | "E1-6"
    data_point: str
    disclosed_value: Optional[str] = None
    unit: Optional[str] = None
    confidence: float           # 0.0–1.0
    xbrl_concept: Optional[str] = None  # iXBRL concept name for traceability


# ---------------------------------------------------------------------------
# v5.0 Models — Unified 3-agent pipeline
# ---------------------------------------------------------------------------

class CompanyInputs(BaseModel):
    """User-provided company parameters for compliance sizing."""
    number_of_employees: int
    revenue_eur: float
    total_assets_eur: float
    reporting_year: int


class FinancialContext(BaseModel):
    """Financial context extracted from iXBRL Taxonomy sections — internal to extractor."""
    capex_total_eur: Optional[float] = None
    capex_green_eur: Optional[float] = None
    opex_total_eur: Optional[float] = None
    opex_green_eur: Optional[float] = None
    revenue_eur: Optional[float] = None
    taxonomy_activities: list[str] = []
    confidence: float


class ComplianceScore(BaseModel):
    """Aggregated compliance score produced by the scorer node."""
    overall: int  # 0-100
    size_category: str
    applicable_standards_count: int
    disclosed_count: int
    partial_count: int
    missing_count: int


class Recommendation(BaseModel):
    """Single actionable recommendation produced by the advisor node."""
    id: str
    priority: Priority
    esrs_id: str
    title: str
    description: str
    regulatory_reference: str


class ComplianceResult(BaseModel):
    """Unified top-level response for both structured_document and free_text modes (v5.0)."""
    audit_id: str
    generated_at: str  # ISO 8601
    schema_version: str = "3.0"
    mode: str
    company: CompanyMeta
    company_inputs: CompanyInputs
    score: ComplianceScore
    recommendations: list[Recommendation]
    pipeline: PipelineTrace


# LEGACY v2.0
class TaxonomyFinancials(BaseModel):
    """CapEx/revenue data from Taxonomy sections of the management report JSON — internal to fetcher node."""
    capex_total_eur: Optional[float] = None
    capex_green_eur: Optional[float] = None
    opex_total_eur: Optional[float] = None
    opex_green_eur: Optional[float] = None
    revenue_eur: Optional[float] = None
    fiscal_year: str
    taxonomy_activities: list[str] = []
    source_document: str = "Annual Management Report — Taxonomy Section"
    confidence: float           # 0.0–1.0


# ---------------------------------------------------------------------------
# Compliance Check Mode — New models for dual-mode support
# ---------------------------------------------------------------------------

CoverageLevel = Literal["covered", "partial", "not_covered"]
EffortLevel = Literal["low", "medium", "high"]


# LEGACY v2.0
class ExtractedGoal(BaseModel):
    """Sustainability goal/claim extracted from free-text input — compliance check mode."""
    id: str
    description: str
    esrs_relevance: Optional[str] = None
    confidence: float  # 0.0–1.0


# LEGACY v2.0
class ESRSCoverageItem(BaseModel):
    """ESRS standard coverage assessment — compliance check mode."""
    esrs_id: str
    standard_name: str
    coverage: CoverageLevel
    details: str


# LEGACY v2.0
class ComplianceTodo(BaseModel):
    """Prioritised regulatory action item — compliance check mode."""
    id: str
    priority: Priority
    esrs_id: str
    title: str
    description: str
    regulatory_reference: str
    estimated_effort: EffortLevel


# LEGACY v2.0
class ComplianceCostEstimate(BaseModel):
    """Rough compliance cost range — compliance check mode (no structured financial data)."""
    estimated_range_low_eur: float
    estimated_range_high_eur: float
    basis: str
    caveat: str


# LEGACY v2.0
class ComplianceCheckResult(BaseModel):
    """Top-level response for compliance check mode — mirrors TypeScript ComplianceCheckResult."""
    audit_id: str
    generated_at: str  # ISO 8601
    schema_version: str = "2.0"
    mode: str = "compliance_check"
    company: CompanyMeta
    extracted_goals: list[ExtractedGoal]
    esrs_coverage: list[ESRSCoverageItem]
    todo_list: list[ComplianceTodo]
    estimated_compliance_cost: ComplianceCostEstimate
    pipeline: PipelineTrace
