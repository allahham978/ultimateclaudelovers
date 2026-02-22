"""
Pydantic v2 models — mirrors the TypeScript contract in frontend/src/lib/types.ts exactly.
Field names must match 1:1. No renames, no extra fields on the public contract.

v3.0 — Unified 3-agent pipeline (extractor → scorer → advisor).
"""

from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Enum-like Literals (mirror TypeScript union types)
# ---------------------------------------------------------------------------

Priority = Literal["critical", "high", "moderate", "low"]
AgentName = Literal["extractor", "scorer", "advisor"]


# ---------------------------------------------------------------------------
# Company Metadata
# ---------------------------------------------------------------------------

class CompanyMeta(BaseModel):
    name: str
    lei: Optional[str] = None
    sector: str
    fiscal_year: int
    jurisdiction: str
    report_title: str


# ---------------------------------------------------------------------------
# Company Inputs (user-provided structured fields)
# ---------------------------------------------------------------------------

class CompanyInputs(BaseModel):
    """User-provided company parameters for compliance sizing."""
    number_of_employees: int
    revenue_eur: float
    total_assets_eur: float
    reporting_year: int


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


class FinancialContext(BaseModel):
    """Financial context extracted from iXBRL Taxonomy sections — internal to extractor."""
    capex_total_eur: Optional[float] = None
    capex_green_eur: Optional[float] = None
    opex_total_eur: Optional[float] = None
    opex_green_eur: Optional[float] = None
    revenue_eur: Optional[float] = None
    taxonomy_activities: list[str] = []
    confidence: float


# ---------------------------------------------------------------------------
# v5.0 Models — Unified 3-agent pipeline output
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Pipeline Trace
# ---------------------------------------------------------------------------

class AgentTiming(BaseModel):
    agent: AgentName
    duration_ms: int
    status: Literal["completed", "failed", "skipped"]


class PipelineTrace(BaseModel):
    total_duration_ms: int
    agents: list[AgentTiming]


# ---------------------------------------------------------------------------
# Audit Log (internal — streamed via SSE, not in final JSON)
# ---------------------------------------------------------------------------

class AuditLog(BaseModel):
    timestamp: int  # epoch ms
    agent: AgentName
    message: str


# ---------------------------------------------------------------------------
# ComplianceResult — Unified top-level response (v3.0)
# ---------------------------------------------------------------------------

class ComplianceResult(BaseModel):
    """Unified top-level response for both structured_document and free_text modes."""
    audit_id: str
    generated_at: str  # ISO 8601
    schema_version: str = "3.0"
    mode: str
    company: CompanyMeta
    company_inputs: CompanyInputs
    score: ComplianceScore
    recommendations: list[Recommendation]
    pipeline: PipelineTrace
