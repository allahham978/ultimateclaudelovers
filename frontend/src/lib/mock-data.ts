import type {
  AuditLog,
  ComplianceResult,
} from "./types";

// ============================================================================
// v5.0 — Unified ComplianceResult Mock Data
// ============================================================================

export const MOCK_COMPLIANCE_RESULT: ComplianceResult = {
  audit_id: "eu-v5-b3e8f1a2-44c9-4d07-a1b2-9e8f7c6d5a34",
  generated_at: "2026-02-21T16:45:12Z",
  schema_version: "3.0",
  mode: "structured_document",

  company: {
    name: "Lumiere Systemes SA",
    lei: "969500XXXXXXXXXXXXXX",
    sector: "AI Infrastructure / Cloud Computing",
    fiscal_year: 2025,
    jurisdiction: "France",
    report_title: "Rapport de Durabilite CSRD — Exercice 2025",
  },

  company_inputs: {
    number_of_employees: 500,
    revenue_eur: 85_000_000,
    total_assets_eur: 42_000_000,
    reporting_year: 2025,
  },

  score: {
    overall: 72,
    size_category: "large_undertaking",
    applicable_standards_count: 18,
    disclosed_count: 11,
    partial_count: 4,
    missing_count: 3,
  },

  recommendations: [
    {
      id: "rec-1",
      priority: "critical",
      esrs_id: "E1-6",
      title: "Conduct Scope 1 & 2 GHG inventory",
      description:
        "Your GHG emissions are not disclosed. Commission a verified GHG inventory covering Scope 1 (direct) and Scope 2 (market-based and location-based) emissions across all data center facilities. This is the most critical gap — CSRD requires quantitative disclosure with methodology.",
      regulatory_reference: "ESRS E1-6, DR E1-6.44",
    },
    {
      id: "rec-2",
      priority: "critical",
      esrs_id: "S1-1",
      title: "Establish own workforce impact assessment",
      description:
        "No workforce materiality data found. Conduct a double materiality assessment for your own workforce covering working conditions, equal treatment, and health & safety. ESRS S1 is mandatory for large undertakings.",
      regulatory_reference: "ESRS S1-1, DR S1-1.01",
    },
    {
      id: "rec-3",
      priority: "high",
      esrs_id: "E1-1",
      title: "Develop quantified transition plan with interim milestones",
      description:
        "Your 2040 net-zero target lacks interim decarbonisation milestones and quantified CapEx commitments. Define 2025/2028/2030 reduction targets (vs. a stated base year) and link them to specific EU Taxonomy activities. With green CapEx of EUR 12M (18% of total), target the 30% threshold.",
      regulatory_reference: "ESRS E1-1, DR E1-1.01–E1-1.09",
    },
    {
      id: "rec-4",
      priority: "high",
      esrs_id: "E2-4",
      title: "Report pollution to air, water, and soil",
      description:
        "Data center coolant and waste reporting is completely absent. Disclose pollutant emissions from cooling systems, e-waste handling, and any reportable substance releases under E-PRTR.",
      regulatory_reference: "ESRS E2-4, DR E2-4.28–E2-4.31",
    },
    {
      id: "rec-5",
      priority: "high",
      esrs_id: "G1-1",
      title: "Formalize business conduct policies",
      description:
        "Anti-corruption, lobbying disclosure, and whistleblower channels are only partially documented. Publish a comprehensive business conduct policy covering all G1 requirements with board-level oversight confirmation.",
      regulatory_reference: "ESRS G1-1, DR G1-1.01–G1-1.04",
    },
    {
      id: "rec-6",
      priority: "moderate",
      esrs_id: "E1-5",
      title: "Complete energy breakdown by source",
      description:
        "While total energy consumption (120 GWh) is disclosed, a breakdown by source (grid electricity, natural gas, on-site renewables) and year-on-year energy intensity trend is required for full compliance.",
      regulatory_reference: "ESRS E1-5, DR E1-5.30–E1-5.37",
    },
    {
      id: "rec-7",
      priority: "moderate",
      esrs_id: "E3-1",
      title: "Assess water and marine resources impact",
      description:
        "Water consumption data for data center cooling is not disclosed. Provide total water withdrawal, consumption, and discharge volumes with breakdown by source type.",
      regulatory_reference: "ESRS E3-1, DR E3-1.09–E3-1.12",
    },
    {
      id: "rec-8",
      priority: "moderate",
      esrs_id: "S2-1",
      title: "Map value chain worker impacts",
      description:
        "No assessment of workers in your value chain (hardware suppliers, subcontractors) has been disclosed. Identify salient human rights risks in your supply chain.",
      regulatory_reference: "ESRS S2-1, DR S2-1.01–S2-1.04",
    },
    {
      id: "rec-9",
      priority: "moderate",
      esrs_id: "E4-1",
      title: "Screen biodiversity and ecosystems impact",
      description:
        "No biodiversity assessment disclosed. Screen operational sites for proximity to Natura 2000 areas or biodiversity-sensitive zones and report material findings.",
      regulatory_reference: "ESRS E4-1, DR E4-1.04–E4-1.06",
    },
    {
      id: "rec-10",
      priority: "low",
      esrs_id: "S1-6",
      title: "Enhance workforce diversity data granularity",
      description:
        "Employee characteristics are disclosed, but could be improved with more granular breakdown by contract type, gender pay gap, and disability representation for best-practice reporting.",
      regulatory_reference: "ESRS S1-6, DR S1-6.48–S1-6.54",
    },
    {
      id: "rec-11",
      priority: "low",
      esrs_id: "ESRS 2",
      title: "Strengthen governance disclosures on sustainability oversight",
      description:
        "General disclosures on governance bodies' sustainability competencies and oversight processes are present but could be enriched with specific meeting frequency and decision records.",
      regulatory_reference: "ESRS 2, DR 2-GOV-1.01–2-GOV-1.06",
    },
    {
      id: "rec-12",
      priority: "low",
      esrs_id: "E5-1",
      title: "Report on resource use and circular economy metrics",
      description:
        "Circular economy metrics (waste generation, recycling rate, material inflows) are not yet disclosed. Consider reporting server hardware lifecycle and e-waste recycling rates.",
      regulatory_reference: "ESRS E5-1, DR E5-1.04–E5-1.06",
    },
    {
      id: "rec-13",
      priority: "low",
      esrs_id: "S3-1",
      title: "Assess impacts on affected communities",
      description:
        "No community impact assessment is disclosed. For data center operations, consider noise, electromagnetic field exposure, and local infrastructure strain as potential material topics.",
      regulatory_reference: "ESRS S3-1, DR S3-1.01–S3-1.04",
    },
    {
      id: "rec-14",
      priority: "low",
      esrs_id: "S4-1",
      title: "Evaluate consumer and end-user impacts",
      description:
        "No assessment of impacts on consumers/end-users of AI services is disclosed. Consider data privacy, algorithmic fairness, and digital accessibility.",
      regulatory_reference: "ESRS S4-1, DR S4-1.01–S4-1.04",
    },
    {
      id: "rec-15",
      priority: "low",
      esrs_id: "E1-9",
      title: "Quantify potential financial effects of climate risks",
      description:
        "While climate data is partially disclosed, the financial effects of physical and transition climate risks are not quantified. Perform scenario analysis per TCFD framework aligned with ESRS E1-9.",
      regulatory_reference: "ESRS E1-9, DR E1-9.66–E1-9.69",
    },
  ],

  pipeline: {
    total_duration_ms: 6_120,
    agents: [
      { agent: "extractor", duration_ms: 2_100, status: "completed" },
      { agent: "scorer", duration_ms: 820, status: "completed" },
      { agent: "advisor", duration_ms: 3_200, status: "completed" },
    ],
  },
};

// ---------------------------------------------------------------------------
// Analysis Logs — 3-agent pipeline (Extractor → Scorer → Advisor)
// ---------------------------------------------------------------------------

export const ANALYSIS_LOGS: AuditLog[] = [
  {
    timestamp: 200,
    agent: "extractor",
    message:
      "Initializing data extraction — parsing Annual Management Report (iXBRL JSON).",
  },
  {
    timestamp: 800,
    agent: "extractor",
    message:
      "Extracting ESRS disclosures from sustainability statement...",
  },
  {
    timestamp: 1400,
    agent: "extractor",
    message:
      "Found 15 ESRS data points across E1, E2, S1, G1, ESRS 2 standards.",
  },
  {
    timestamp: 2000,
    agent: "extractor",
    message:
      "Extracting financial context from EU Taxonomy table (CapEx/OpEx/Revenue).",
  },
  {
    timestamp: 2500,
    agent: "extractor",
    message:
      "Extraction complete. 15 claims, company meta, financial context ready.",
  },
  {
    timestamp: 3000,
    agent: "scorer",
    message:
      "Loading knowledge base — matching company inputs against CSRD thresholds.",
  },
  {
    timestamp: 3400,
    agent: "scorer",
    message:
      "Size category: Large Undertaking (500 employees, EUR 85M revenue).",
  },
  {
    timestamp: 3800,
    agent: "scorer",
    message:
      "18 ESRS standards applicable for reporting year 2025.",
  },
  {
    timestamp: 4200,
    agent: "scorer",
    message:
      "Disclosure assessment: 11 disclosed, 4 partial, 3 missing.",
  },
  {
    timestamp: 4600,
    agent: "scorer",
    message:
      "Compliance score computed: 72/100. Handing off to Advisor.",
  },
  {
    timestamp: 5000,
    agent: "advisor",
    message:
      "Generating recommendations for 7 standards with gaps...",
  },
  {
    timestamp: 5600,
    agent: "advisor",
    message:
      "2 critical, 3 high, 4 moderate, 6 low priority recommendations generated.",
  },
  {
    timestamp: 6200,
    agent: "advisor",
    message:
      "Financial context enriched — CapEx/revenue figures added to recommendations.",
  },
  {
    timestamp: 6800,
    agent: "advisor",
    message:
      "Compliance analysis complete. Score and recommendations ready.",
  },
];

// ---------------------------------------------------------------------------
// Free Text Analysis Logs — 3-agent pipeline
// ---------------------------------------------------------------------------

export const FREE_TEXT_ANALYSIS_LOGS: AuditLog[] = [
  {
    timestamp: 200,
    agent: "extractor",
    message:
      "Initializing extraction — parsing free-text sustainability description.",
  },
  {
    timestamp: 800,
    agent: "extractor",
    message:
      "Identifying sustainability claims in unstructured text...",
  },
  {
    timestamp: 1600,
    agent: "extractor",
    message:
      "Mapped 8 claims to ESRS standards (E1, E2, S1). Confidence: 0.3–0.9.",
  },
  {
    timestamp: 2200,
    agent: "extractor",
    message:
      "Company metadata extracted. Financial context: not available (free text mode).",
  },
  {
    timestamp: 2800,
    agent: "scorer",
    message:
      "Loading knowledge base — matching company inputs against CSRD thresholds.",
  },
  {
    timestamp: 3200,
    agent: "scorer",
    message:
      "18 ESRS standards applicable. Comparing against extracted claims...",
  },
  {
    timestamp: 3600,
    agent: "scorer",
    message:
      "Disclosure assessment: 5 disclosed, 3 partial, 10 missing.",
  },
  {
    timestamp: 4000,
    agent: "scorer",
    message:
      "Compliance score computed: 36/100. Significant gaps identified.",
  },
  {
    timestamp: 4400,
    agent: "advisor",
    message:
      "Generating recommendations for 13 standards with gaps...",
  },
  {
    timestamp: 5000,
    agent: "advisor",
    message:
      "5 critical, 4 high, 3 moderate, 1 low priority recommendations generated.",
  },
  {
    timestamp: 5600,
    agent: "advisor",
    message:
      "Compliance analysis complete. Score and recommendations ready.",
  },
];
