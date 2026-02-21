"""
Pydantic v2 models for CSRD / ESRS reporting document requirements.

All monetary thresholds are in EUR.
All durations are in calendar days unless stated otherwise.
"""

from __future__ import annotations

from enum import IntEnum, StrEnum  # StrEnum requires Python ≥ 3.11; for 3.9/3.10 use (str, Enum) instead
from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class CSRDPhase(IntEnum):
    """CSRD phased roll-out wave."""

    PHASE_1 = 1  # Large PIEs already subject to NFRD; FY2024 data, filed 2025
    PHASE_2 = 2  # Other large EU companies; FY2025 data, filed 2026
    PHASE_3 = 3  # Listed SMEs; FY2026 data, filed 2027 (opt-out to 2029)
    PHASE_4 = 4  # Non-EU parent companies with EU nexus; FY2028 data, filed 2029


class Cadence(StrEnum):
    """Reporting or collection cadence."""

    ANNUAL = "annual"
    ONGOING = "ongoing"


class AssuranceLevel(StrEnum):
    """External assurance level."""

    LIMITED = "limited"        # Negative assurance (ISAE 3000 / ISSA 5000)
    REASONABLE = "reasonable"  # Positive assurance, equivalent to financial audit


class PeriodCovered(StrEnum):
    """Standard values for the period_covered field."""

    FULL_FINANCIAL_YEAR = "full_financial_year"
    FULL_FINANCIAL_YEAR_PLUS_FORWARD = "full_financial_year_plus_forward_looking"
    CURRENT_AND_HISTORICAL = "current_and_historical"
    ALL_PREVIOUS_CSRD_YEARS = "all_previous_csrd_reporting_years"
    SAME_AS_SUSTAINABILITY_REPORT = "same_as_sustainability_report"


# ---------------------------------------------------------------------------
# Frequency
# ---------------------------------------------------------------------------


class AnnualFrequency(BaseModel):
    """Frequency config for documents filed once per year."""

    cadence: Literal["annual"]
    collections_per_year: Literal[1]
    trigger: str = Field(
        description=(
            "Event or condition that triggers data collection / filing, "
            "e.g. 'end_of_financial_year'."
        )
    )
    max_filing_lag_days: Optional[int] = Field(
        default=None,
        ge=0,
        description="Maximum calendar days after period end before the document must be filed.",
    )
    # Optional cadence overrides for sub-processes
    hr_data_collection_cadence: Optional[str] = None
    board_review_cadence: Optional[str] = None
    internal_controls_review_cadence: Optional[str] = None
    note: Optional[str] = None


class OngoingFrequency(BaseModel):
    """Frequency config for documents maintained continuously."""

    cadence: Literal["ongoing"]
    collections_per_year: None = Field(
        default=None,
        description="Not applicable for ongoing documents; collection is continuous.",
    )
    trigger: Optional[str] = None
    max_filing_lag_days: None = Field(
        default=None,
        description="Not applicable; ongoing documents have no single filing deadline.",
    )
    # Domain-specific sub-cadences
    formal_review_cadence: Optional[str] = Field(
        default=None,
        description="How often the document is formally reviewed, e.g. 'annual'.",
    )
    update_trigger: Optional[str] = Field(
        default=None,
        description="What triggers an out-of-cycle update, e.g. 'on_process_or_methodology_change'.",
    )
    internal_audit_cadence: Optional[str] = None
    controls_testing_cadence: Optional[str] = None
    environmental_data_collection_cadence: Optional[str] = None
    hr_data_collection_cadence: Optional[str] = None
    safety_incident_data_cadence: Optional[str] = None
    supplier_data_cadence: Optional[str] = None
    annual_consolidation_required: Optional[bool] = None
    note: Optional[str] = None


Frequency = Annotated[
    Union[AnnualFrequency, OngoingFrequency],
    Field(discriminator="cadence"),
]


# ---------------------------------------------------------------------------
# Timeframe
# ---------------------------------------------------------------------------


class Timeframe(BaseModel):
    """Temporal scope of the document."""

    period_covered: str = Field(
        description="Describes which reporting period is covered. See PeriodCovered for standard values."
    )

    # Lookback
    lookback_comparative_years_minimum: Optional[int] = Field(
        default=None,
        ge=0,
        description="Minimum number of prior years required for comparative disclosure.",
    )
    lookback_comparative_years_recommended: Optional[int] = Field(
        default=None,
        ge=0,
        description="Recommended number of prior years for best practice.",
    )
    lookback_years_minimum: Optional[int] = Field(
        default=None,
        ge=0,
        description=(
            "Used for ongoing documents. Minimum years of historical data to retain."
        ),
    )
    lookback_years_recommended: Optional[int] = Field(
        default=None,
        ge=0,
    )

    # GHG-specific
    ghg_base_year_required: Optional[bool] = Field(
        default=None,
        description="Whether a GHG Protocol base year must be established and disclosed.",
    )
    ghg_base_year_note: Optional[str] = None
    ghg_base_year_retained_indefinitely: Optional[bool] = None

    # Historical baseline (E4 biodiversity)
    historical_baseline_required: Optional[bool] = None
    historical_baseline_note: Optional[str] = None

    # EU Taxonomy history
    taxonomy_kpi_history_minimum_years: Optional[int] = Field(default=None, ge=0)

    # Forward-looking
    forward_looking_horizon_years: Optional[list[int]] = Field(
        default=None,
        description="Time horizons in years for forward-looking disclosures, e.g. [1, 3, 5, 10].",
    )
    forward_looking_target_years: Optional[list[int]] = Field(
        default=None,
        description="Specific calendar years for which targets must be set, e.g. [2030, 2040, 2050].",
    )
    forward_looking_horizon_short_years: Optional[int] = Field(default=None, ge=0)
    forward_looking_horizon_medium_years: Optional[int] = Field(default=None, ge=0)
    forward_looking_horizon_long_years: Optional[int] = Field(default=None, ge=0)

    # Version history (QA docs)
    version_history_retained: Optional[bool] = None
    version_history_minimum_years: Optional[int] = Field(default=None, ge=0)

    note: Optional[str] = None


# ---------------------------------------------------------------------------
# Company Applicability
# ---------------------------------------------------------------------------


class CompanyApplicability(BaseModel):
    """
    Describes which companies are in scope for a given document under a specific CSRD phase,
    including the size thresholds that determine applicability and the disclosure level required.

    Phase 1  — Large PIEs (>500 employees) already subject to NFRD.
    Phase 2  — Other large EU companies (≥250 employees or meeting financial thresholds).
    Phase 3  — Listed SMEs (<250 employees); simplified standard (ESRS LSME) applies.
    Phase 4  — Non-EU parent companies with EU net turnover ≥ €150 million for 2 consecutive years.
    """

    csrd_phase: CSRDPhase
    label: Optional[str] = Field(
        default=None,
        description="Human-readable label for this phase entry.",
    )

    # ---- Size thresholds (EUR, headcount) ----
    # For Phases 1 & 2: minimum thresholds to qualify as 'large'
    employee_threshold_min: Optional[int] = Field(
        default=None,
        ge=1,
        description=(
            "Minimum average employee count for the company to be in scope "
            "(used for Phases 1 and 2)."
        ),
    )
    net_turnover_threshold_eur: Optional[int] = Field(
        default=None,
        ge=0,
        description="Minimum net turnover (EUR) for Phase 1/2 large company classification.",
    )
    total_assets_threshold_eur: Optional[int] = Field(
        default=None,
        ge=0,
        description="Minimum total assets (EUR) for Phase 1/2 large company classification.",
    )
    size_criteria_required_of_3: Optional[int] = Field(
        default=None,
        ge=1,
        le=3,
        description=(
            "Number of the three size criteria (employees, turnover, assets) "
            "that must be met to qualify as large."
        ),
    )

    # For Phase 3: maximum thresholds defining SME upper bound
    employee_threshold_max: Optional[int] = Field(
        default=None,
        ge=1,
        description="Maximum average employee count for SME classification (Phase 3).",
    )
    net_turnover_threshold_eur_max: Optional[int] = Field(
        default=None,
        ge=0,
        description="Maximum net turnover (EUR) for SME upper bound (Phase 3).",
    )
    total_assets_threshold_eur_max: Optional[int] = Field(
        default=None,
        ge=0,
        description="Maximum total assets (EUR) for SME upper bound (Phase 3).",
    )

    # For Phase 4: EU-nexus revenue trigger
    eu_net_turnover_threshold_eur: Optional[int] = Field(
        default=None,
        ge=0,
        description=(
            "Minimum EU net turnover (EUR) for non-EU parent companies to fall "
            "in scope (Phase 4). Must be exceeded for the required number of "
            "consecutive years."
        ),
    )
    eu_net_turnover_consecutive_years: Optional[int] = Field(
        default=None,
        ge=1,
        description=(
            "Number of consecutive financial years for which the EU net turnover "
            "threshold must be exceeded (Phase 4)."
        ),
    )
    requires_qualifying_eu_subsidiary_or_branch: Optional[bool] = Field(
        default=None,
        description=(
            "Whether the non-EU parent must also have at least one qualifying "
            "EU subsidiary or branch (Phase 4)."
        ),
    )

    # ---- Disclosure level ----
    full_disclosure_required: Optional[bool] = None
    simplified_disclosure_required: Optional[bool] = None
    simplified_standard_applies: Optional[bool] = None
    simplified_standard_name: Optional[str] = Field(
        default=None,
        description="Name of the simplified reporting standard, e.g. 'ESRS LSME'.",
    )
    simplified_presentation_permitted: Optional[bool] = None

    # ---- Opt-out (Phase 3 only) ----
    opt_out_available: Optional[bool] = None
    opt_out_until_year: Optional[int] = Field(
        default=None,
        ge=2024,
        description="Last calendar year for which the opt-out exemption is available.",
    )

    # ---- Filing timeline ----
    first_data_collection_year: Optional[int] = Field(
        default=None,
        ge=2024,
        description="First financial year for which data must be collected.",
    )
    first_filing_year: Optional[int] = Field(
        default=None,
        ge=2025,
        description="First year in which the report must be filed.",
    )
    first_comparative_year: Optional[int] = Field(
        default=None,
        ge=2023,
        description=(
            "First year for which historical comparative data must be maintained "
            "(typically one year before first_data_collection_year)."
        ),
    )

    # ---- Document-specific flags ----
    # General disclosures
    full_esrs_topics_assessed: Optional[bool] = None

    # ESRS topical disclosures
    site_level_data_required: Optional[bool] = None
    mandatory_kpis: Optional[list[str]] = Field(
        default=None,
        description=(
            "For simplified disclosures: list of KPI names that are mandatory "
            "regardless of materiality."
        ),
    )
    headcount_breakdowns_required: Optional[list[str]] = Field(
        default=None,
        description="Required breakdowns for headcount disclosures (ESRS S1).",
    )
    scope_note: Optional[str] = None

    # Assurance (ASS-001)
    assurance_level_required: Optional[AssuranceLevel] = None
    transition_to_reasonable: Optional[bool] = None
    transition_year_tbc: Optional[bool] = None

    # EU Taxonomy (TAX-001)
    full_kpi_disclosure_required: Optional[bool] = None
    eligibility_and_alignment_required: Optional[bool] = None

    # Data Collection Logs (DCL-001)
    granularity: Optional[str] = Field(
        default=None,
        description="'full' or 'simplified' — depth of data collection required.",
    )
    scope_3_required: Optional[bool] = None
    scope_3_categories_required_minimum: Optional[list[int]] = Field(
        default=None,
        description=(
            "Minimum GHG Protocol Scope 3 categories that must be collected "
            "(by category number 1–15)."
        ),
    )

    # Control & QA (QA-001)
    controls_scope: Optional[str] = None
    external_assurance_required: Optional[bool] = None

    # Historical records (HIS-001)
    full_historical_record_required: Optional[bool] = None
    simplified_historical_record_required: Optional[bool] = None

    note: Optional[str] = None

    @field_validator("csrd_phase", mode="before")
    @classmethod
    def coerce_phase(cls, v: object) -> CSRDPhase:
        return CSRDPhase(int(v))

    def company_qualifies(
        self,
        employees: int,
        revenue_eur: int,
        total_assets_eur: Optional[int] = None,
    ) -> bool:
        """
        Return True if a company with the given headcount, revenue, and (optionally)
        total assets meets the in-scope thresholds for this phase entry.

        Phase 1 & 2 — large company test:
            Must satisfy at least `size_criteria_required_of_3` (default 2) of the
            three criteria: employees ≥ min, revenue ≥ threshold, assets ≥ threshold.
            If total_assets_eur is not supplied it is treated as not meeting the
            assets criterion (conservative but safe).

        Phase 3 — SME test:
            Must fall *below* all three SME upper bounds (employees, revenue, assets).
            A company that exceeds any upper bound is captured by Phase 1 or 2 instead.

        Phase 4 — non-EU nexus test:
            revenue_eur is interpreted as EU-generated net turnover.
            Must meet or exceed eu_net_turnover_threshold_eur.
            The consecutive-years and qualifying-subsidiary conditions cannot be
            evaluated from size data alone and are not checked here.
        """
        if self.csrd_phase in (CSRDPhase.PHASE_1, CSRDPhase.PHASE_2):
            required = self.size_criteria_required_of_3 or 2
            criteria_met = 0
            if self.employee_threshold_min is not None and employees >= self.employee_threshold_min:
                criteria_met += 1
            if self.net_turnover_threshold_eur is not None and revenue_eur >= self.net_turnover_threshold_eur:
                criteria_met += 1
            if (
                self.total_assets_threshold_eur is not None
                and total_assets_eur is not None
                and total_assets_eur >= self.total_assets_threshold_eur
            ):
                criteria_met += 1
            return criteria_met >= required

        if self.csrd_phase == CSRDPhase.PHASE_3:
            if self.employee_threshold_max is not None and employees > self.employee_threshold_max:
                return False
            if self.net_turnover_threshold_eur_max is not None and revenue_eur > self.net_turnover_threshold_eur_max:
                return False
            if (
                self.total_assets_threshold_eur_max is not None
                and total_assets_eur is not None
                and total_assets_eur > self.total_assets_threshold_eur_max
            ):
                return False
            return True

        if self.csrd_phase == CSRDPhase.PHASE_4:
            if self.eu_net_turnover_threshold_eur is None:
                return False
            return revenue_eur >= self.eu_net_turnover_threshold_eur

        return False


# ---------------------------------------------------------------------------
# Phase-in Reliefs
# ---------------------------------------------------------------------------


class PhaseInRelief(BaseModel):
    """A temporary exemption or deferral available in the first year(s) of reporting."""

    relief: str = Field(description="Description of what is deferred or exempt.")
    phase_in_years: int = Field(
        ge=1,
        description="Number of years the relief applies from the first filing year.",
    )
    applies_to_phases: list[CSRDPhase] = Field(
        description="CSRD phases to which this relief is available."
    )
    note: Optional[str] = None


# ---------------------------------------------------------------------------
# Content
# ---------------------------------------------------------------------------


class MaterialityDimension(BaseModel):
    """One of the two dimensions of ESRS double materiality."""

    description: str
    scoring_criteria: list[str] = Field(
        description="Factors used to score materiality for this dimension."
    )


class MaterialityDimensions(BaseModel):
    """Both dimensions of the ESRS double materiality framework."""

    impact_materiality: MaterialityDimension
    financial_materiality: MaterialityDimension


class DataDomain(BaseModel):
    """A category of ESG data within the Data Collection Logs."""

    domain: str = Field(description="Name of the data domain, e.g. 'GHG Emissions Scope 1'.")
    metrics: list[str] = Field(
        description="Individual metric identifiers collected within this domain."
    )
    collection_cadence: str = Field(
        description=(
            "How often this domain's data is collected, "
            "e.g. 'monthly', 'annual', 'real_time_incident_reporting_monthly_consolidated'."
        )
    )
    source_systems: list[str] = Field(
        description="Source systems or data inputs for this domain."
    )


class RestatementRules(BaseModel):
    """Rules governing when and how prior-period figures must be restated."""

    restatement_required_when: list[str] = Field(
        description="Conditions that trigger a mandatory restatement."
    )
    restatement_disclosure_required: bool = Field(
        description="Whether restatements must be explicitly disclosed in the report."
    )
    restatement_standard_reference: str = Field(
        description="Authoritative reference for restatement rules, e.g. 'ESRS 1 Section 6'."
    )
    restatement_flag_in_report: bool = Field(
        description="Whether restated figures must be flagged inline in the published report."
    )


class Content(BaseModel):
    """Describes the content requirements of the document."""

    qualitative: Optional[bool] = Field(
        default=None,
        description="Whether the document includes qualitative (narrative) disclosures.",
    )
    quantitative: Optional[bool] = Field(
        default=None,
        description="Whether the document includes quantitative (numeric KPI) disclosures.",
    )
    forward_looking: Optional[bool] = Field(
        default=None,
        description="Whether the document includes forward-looking targets or projections.",
    )

    # Used by most topical ESRS and the Sustainability Report
    key_disclosures: Optional[list[str]] = Field(
        default=None,
        description="Numbered disclosure requirements, e.g. ['E1-1: Transition plan...'].",
    )
    areas: Optional[list[str]] = Field(
        default=None,
        description="High-level thematic areas covered by the document.",
    )
    primary_units: Optional[list[str]] = Field(
        default=None,
        description="Primary measurement units used in quantitative disclosures.",
    )

    # DMA-specific
    materiality_dimensions: Optional[MaterialityDimensions] = None
    topics_assessed: Optional[list[str]] = Field(
        default=None,
        description="ESRS topics evaluated during the Double Materiality Assessment.",
    )
    process_requirements: Optional[list[str]] = Field(
        default=None,
        description="Procedural requirements for the DMA process.",
    )

    # EU Taxonomy-specific
    six_environmental_objectives: Optional[list[str]] = None
    dnsh_required: Optional[bool] = Field(
        default=None,
        description="Whether Do No Significant Harm (DNSH) criteria must be assessed.",
    )
    minimum_social_safeguards_required: Optional[bool] = None
    minimum_safeguards_reference: Optional[str] = None
    key_kpis: Optional[list[str]] = Field(
        default=None,
        description="Key Performance Indicators required by the EU Taxonomy.",
    )

    # Data Collection Logs-specific
    data_domains: Optional[list[DataDomain]] = None


# ---------------------------------------------------------------------------
# Assurance
# ---------------------------------------------------------------------------


class AssuranceInfo(BaseModel):
    """External assurance requirements for the document."""

    required: bool
    current_level: Optional[AssuranceLevel] = Field(
        default=None,
        description="Assurance level required from the first reporting year.",
    )
    future_level: Optional[AssuranceLevel] = Field(
        default=None,
        description="Anticipated future assurance level (subject to EU Commission review).",
    )
    standard: Optional[str] = Field(
        default=None,
        description="Assurance standard(s) applicable, e.g. 'ISAE 3000 (Revised) / ISSA 5000'.",
    )
    note: Optional[str] = None


# ---------------------------------------------------------------------------
# Filing Format (Sustainability Report only)
# ---------------------------------------------------------------------------


class FilingFormat(BaseModel):
    """Machine-readable filing format requirements."""

    filing_format: str = Field(description="Document format, e.g. 'XHTML'.")
    tagging_format: str = Field(description="Inline tagging format, e.g. 'iXBRL'.")
    taxonomy_reference: str = Field(
        description="Reference to the applicable digital taxonomy."
    )
    embedded_in: str = Field(
        description="The parent document in which this report must be embedded."
    )


# ---------------------------------------------------------------------------
# Root Document Model
# ---------------------------------------------------------------------------


class CSRDDocument(BaseModel):
    """
    A single CSRD / ESRS reporting document requirement.

    Each document has:
    - A unique identifier and human-readable type name.
    - Governing legal / standard references.
    - A structured frequency (annual or ongoing).
    - A timeframe defining lookback and forward-looking horizons.
    - Per-phase company applicability, including size thresholds in EUR and headcount.
    - Content requirements (qualitative, quantitative, forward-looking).
    - Optional assurance, phase-in relief, alignment, and format metadata.
    """

    document_id: str = Field(
        description="Unique identifier for this document, e.g. 'E1-001'.",
        pattern=r"^[A-Z0-9]+-[0-9]{3}$",
    )
    document_type: str = Field(
        description="Human-readable document name, e.g. 'ESRS E1 – Climate Change Disclosure'."
    )
    governing_standards: list[str] = Field(
        description="ESRS standards, EU regulations, or other legal bases governing this document.",
        min_length=1,
    )

    # Mandatory flags — exactly one of these must be set
    mandatory: Optional[bool] = Field(
        default=None,
        description=(
            "True if the document is unconditionally mandatory for all in-scope companies. "
            "Mutually exclusive with mandatory_if_material."
        ),
    )
    mandatory_if_material: Optional[bool] = Field(
        default=None,
        description=(
            "True if the document is mandatory only when the topic is material "
            "per the company's Double Materiality Assessment. "
            "Mutually exclusive with mandatory."
        ),
    )
    mandatory_regardless_of_materiality: Optional[bool] = Field(
        default=None,
        description=(
            "For topical ESRS: whether any disclosures within the document are "
            "mandatory even if the topic is not material overall."
        ),
    )
    mandatory_note: Optional[str] = None

    frequency: Frequency
    timeframe: Timeframe

    company_applicability: list[CompanyApplicability] = Field(
        description=(
            "One entry per CSRD phase. Describes the size thresholds and "
            "disclosure level applicable to companies in that phase."
        ),
        min_length=1,
    )

    content: Content

    # Optional metadata
    phase_in_reliefs: Optional[list[PhaseInRelief]] = Field(
        default=None,
        description=(
            "Temporary exemptions available in the first reporting year(s), "
            "e.g. deferral of Scope 3 category-level disclosures."
        ),
    )
    alignment: Optional[list[str]] = Field(
        default=None,
        description=(
            "External frameworks and regulations with which this document aligns, "
            "e.g. 'GHG Protocol Corporate Standard', 'TCFD'."
        ),
    )
    format: Optional[FilingFormat] = None
    assurance: Optional[AssuranceInfo] = None
    restatement_rules: Optional[RestatementRules] = None

    @model_validator(mode="after")
    def validate_mandatory_flags(self) -> CSRDDocument:
        """Exactly one of mandatory / mandatory_if_material must be set."""
        has_mandatory = self.mandatory is not None
        has_conditional = self.mandatory_if_material is not None
        if has_mandatory == has_conditional:
            raise ValueError(
                "Exactly one of 'mandatory' or 'mandatory_if_material' must be set "
                f"(document_id={self.document_id!r})."
            )
        return self

    @model_validator(mode="after")
    def validate_phase_coverage(self) -> CSRDDocument:
        """All four CSRD phases must be represented in company_applicability."""
        phases_present = {entry.csrd_phase for entry in self.company_applicability}
        missing = set(CSRDPhase) - phases_present
        if missing:
            raise ValueError(
                f"Missing company_applicability entries for phases: "
                f"{sorted(p.value for p in missing)} "
                f"(document_id={self.document_id!r})."
            )
        return self


# ---------------------------------------------------------------------------
# Root Schema Model
# ---------------------------------------------------------------------------


class CSRDReportingRequirements(BaseModel):
    """Root model for the full CSRD / ESRS reporting document requirements schema."""

    schema_version: str = Field(
        alias="_schema_version",
        description="Schema version string, e.g. '2.0'.",
    )
    description: str = Field(
        alias="_description",
        description="Human-readable description of the schema.",
    )
    csrd_reporting_requirements: list[CSRDDocument] = Field(
        description="List of all CSRD reporting document requirements.",
        min_length=1,
    )

    model_config = {"populate_by_name": True}

    def get_document(self, document_id: str) -> CSRDDocument:
        """Retrieve a document by its unique ID. Raises KeyError if not found."""
        for doc in self.csrd_reporting_requirements:
            if doc.document_id == document_id:
                return doc
        raise KeyError(f"No document with document_id={document_id!r}")

    def get_documents_for_phase(
        self, phase: CSRDPhase
    ) -> list[tuple[CSRDDocument, CompanyApplicability]]:
        """
        Return (document, applicability) pairs for the given CSRD phase.

        Every document is represented in all four phases (enforced by the
        validate_phase_coverage validator), so filtering on phase membership
        alone would always return all documents. This method instead extracts
        the *specific* CompanyApplicability entry for the requested phase,
        giving the caller the phase-relevant thresholds, disclosure level,
        filing timeline and any phase-specific flags alongside the document.

        Example
        -------
        for doc, applicability in requirements.get_documents_for_phase(CSRDPhase.PHASE_3):
            print(doc.document_id, applicability.simplified_standard_name)
        """
        result: list[tuple[CSRDDocument, CompanyApplicability]] = []
        for doc in self.csrd_reporting_requirements:
            for applicability in doc.company_applicability:
                if applicability.csrd_phase == phase:
                    result.append((doc, applicability))
                    break  # only one entry per phase per document
        return result

    def get_mandatory_documents(self) -> list[CSRDDocument]:
        """Return documents that are unconditionally mandatory (not subject to materiality)."""
        return [
            doc for doc in self.csrd_reporting_requirements if doc.mandatory is True
        ]

    def get_material_dependent_documents(self) -> list[CSRDDocument]:
        """Return documents required only when the topic is material."""
        return [
            doc
            for doc in self.csrd_reporting_requirements
            if doc.mandatory_if_material is True
        ]

    def filter_documents(
        self,
        phase: CSRDPhase,
        employees: int,
        revenue_eur: int,
        total_assets_eur: Optional[int] = None,
    ) -> list[tuple[CSRDDocument, CompanyApplicability]]:
        """
        Return (document, applicability) pairs applicable to a company with the
        given CSRD phase, headcount, revenue, and optionally total assets.

        Only documents whose CompanyApplicability entry for the requested phase
        confirms the company meets the in-scope size thresholds are returned.
        See CompanyApplicability.company_qualifies() for the per-phase logic.

        Parameters
        ----------
        phase:
            The CSRD phase the company falls under (1–4).
        employees:
            Average number of employees over the financial year.
        revenue_eur:
            Net turnover in EUR for the financial year.
            For Phase 4 companies this should be EU-generated net turnover only.
        total_assets_eur:
            Total balance-sheet assets in EUR (optional).
            Supplying this improves accuracy for Phase 1/2 large-company tests,
            where 2-of-3 criteria (employees, revenue, assets) must be met.
            If omitted, the assets criterion is treated as not satisfied.

        Returns
        -------
        list[tuple[CSRDDocument, CompanyApplicability]]
            Each tuple contains the full document definition and the
            phase-specific applicability entry that matched.

        Examples
        --------
        # Large Phase 2 company: 300 employees, €50M revenue, €25M assets
        results = requirements.filter_documents(
            phase=CSRDPhase.PHASE_2,
            employees=300,
            revenue_eur=50_000_000,
            total_assets_eur=25_000_000,
        )
        for doc, applicability in results:
            print(doc.document_id, applicability.full_disclosure_required)

        # Listed SME: 80 employees, €8M revenue — no assets needed
        results = requirements.filter_documents(
            phase=CSRDPhase.PHASE_3,
            employees=80,
            revenue_eur=8_000_000,
        )
        """
        result: list[tuple[CSRDDocument, CompanyApplicability]] = []
        for doc in self.csrd_reporting_requirements:
            for applicability in doc.company_applicability:
                if applicability.csrd_phase != phase:
                    continue
                if applicability.company_qualifies(employees, revenue_eur, total_assets_eur):
                    result.append((doc, applicability))
                break  # only one entry per phase per document; stop regardless of match
        return result