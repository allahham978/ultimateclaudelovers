import type {
  AuditLog,
  CSRDAudit,
  ComplianceCheckResult,
  ComplianceResult,
} from "./types";

export const MOCK_AUDIT: CSRDAudit = {
  audit_id: "eu-c4d7a1b2-88f3-4e01-bc9d-a7e312f56789",
  generated_at: "2026-02-21T14:32:07Z",
  schema_version: "2.0",

  company: {
    name: "Lumiere Systemes SA",
    lei: "969500XXXXXXXXXXXXXX",
    sector: "AI Infrastructure / Cloud Computing",
    fiscal_year: 2025,
    jurisdiction: "France",
    report_title: "Rapport de Durabilite CSRD — Exercice 2025",
  },

  taxonomy_alignment: {
    capex_aligned_pct: 31,
    status: "partially_aligned",
    label: "Partially Aligned",
  },

  compliance_cost: {
    projected_fine_eur: 4_200_000,
    basis:
      "Art. 51 CSRD Directive (EU) 2022/2464 — up to EUR 10M or 5% of net worldwide turnover",
  },

  esrs_ledger: [
    {
      id: "esrs-1",
      esrs_id: "E1-1",
      data_point:
        "Transition plan for climate change mitigation aligned with 1.5C pathway",
      impact_materiality: "high",
      financial_materiality: "high",
      status: "partial",
      evidence_source: "transition_plan",
      registry_evidence: "Infogreffe — Rapport de gestion 2025, Section 4.1",
    },
    {
      id: "esrs-2",
      esrs_id: "E1-5",
      data_point:
        "Energy consumption and mix — breakdown by renewable vs. non-renewable sources",
      impact_materiality: "high",
      financial_materiality: "medium",
      status: "disclosed",
      evidence_source: "taxonomy_table",
      registry_evidence: "Infogreffe — Bilan energetique 2025, Annexe III",
    },
    {
      id: "esrs-3",
      esrs_id: "E1-6",
      data_point:
        "Gross Scope 1, 2, and 3 GHG emissions with methodology disclosure",
      impact_materiality: "high",
      financial_materiality: "high",
      status: "missing",
      evidence_source: "management_report",
      registry_evidence:
        "BRIS cross-reference — no Scope 3 filing found in EU registry",
    },
    {
      id: "esrs-4",
      esrs_id: "E2-4",
      data_point:
        "Pollution of air, water and soil — data center coolant and waste reporting",
      impact_materiality: "medium",
      financial_materiality: "low",
      status: "non_compliant",
      evidence_source: "management_report",
      registry_evidence:
        "Infogreffe — Declaration de performance extra-financiere 2025, absent",
    },
    {
      id: "esrs-5",
      esrs_id: "S1-6",
      data_point:
        "Characteristics of undertaking's employees — diversity, pay equity, working conditions",
      impact_materiality: "medium",
      financial_materiality: "medium",
      status: "disclosed",
      evidence_source: "management_report",
      registry_evidence:
        "Infogreffe — Index egalite professionnelle 2025, p.2",
    },
    {
      id: "esrs-6",
      esrs_id: "G1-1",
      data_point:
        "Business conduct policies — anti-corruption, lobbying disclosure, whistleblower channels",
      impact_materiality: "low",
      financial_materiality: "high",
      status: "partial",
      evidence_source: "management_report",
      registry_evidence:
        "Infogreffe — Rapport du conseil d'administration 2025, Section 7",
    },
  ],

  roadmap: {
    hardware: {
      title: "Infrastructure Upgrades",
      summary:
        "Migrate Tier-1 facilities to liquid-cooled GPU racks (B200/GB300). EU Taxonomy Delegated Act recognises PUE < 1.3 as substantially contributing to climate mitigation. Current fleet PUE averages 1.58.",
      priority: "critical",
      alignment_increase_pct: 18,
    },
    power: {
      title: "Power Procurement",
      summary:
        "Execute long-term Corporate PPAs with EU-certified renewable generators under Guarantee of Origin (GO) scheme. Current renewable mix is 29% — reaching 70% qualifies for Taxonomy 'Do No Significant Harm' criteria.",
      priority: "high",
      alignment_increase_pct: 12,
    },
    workload: {
      title: "Workload Optimization",
      summary:
        "Deploy cluster-wide scheduling and mixed-precision training to raise GPU utilization from 41% to 70%+. Lower energy-per-FLOP directly improves the CapEx intensity ratio reported under ESRS E1-5.",
      priority: "moderate",
      alignment_increase_pct: 7,
    },
  },

  registry_source: {
    name: "Infogreffe - France",
    registry_type: "national",
    jurisdiction: "France",
  },

  sources: [
    {
      id: "src-1",
      document_name: "Rapport de Durabilite CSRD — Exercice 2025",
      document_type: "csrd_report",
      url: null,
    },
    {
      id: "src-2",
      document_name: "Infogreffe — Registre du Commerce et des Societes",
      document_type: "eu_registry",
      url: null,
    },
    {
      id: "src-3",
      document_name: "BRIS — Business Registers Interconnection System",
      document_type: "eu_registry",
      url: null,
    },
    {
      id: "src-4",
      document_name:
        "Declaration de Performance Extra-Financiere (DPEF) 2025",
      document_type: "national_filing",
      url: null,
    },
    {
      id: "src-5",
      document_name: "EU Taxonomy Compass — Delegated Regulation 2021/2139",
      document_type: "third_party",
      url: null,
    },
  ],

  pipeline: {
    total_duration_ms: 16_540,
    agents: [
      { agent: "extractor", duration_ms: 4_810, status: "completed" },
      { agent: "fetcher", duration_ms: 6_290, status: "completed" },
      { agent: "auditor", duration_ms: 3_740, status: "completed" },
      { agent: "consultant", duration_ms: 1_700, status: "completed" },
    ],
  },
};

// ---------------------------------------------------------------------------
// Audit Logs — references the three Golden Source uploads explicitly
// ---------------------------------------------------------------------------

export const AUDIT_LOGS: AuditLog[] = [
  {
    timestamp: 200,
    agent: "extractor",
    message:
      "Initializing CSRD document parser — 3 Golden Sources detected.",
  },
  {
    timestamp: 800,
    agent: "extractor",
    message:
      "Parsing ESRS E1 interim targets from Climate Transition Plan...",
  },
  {
    timestamp: 1600,
    agent: "extractor",
    message:
      "Parsing sustainability statement from Integrated Management Report...",
  },
  {
    timestamp: 2400,
    agent: "extractor",
    message:
      "Identified 6 ESRS data points: E1-1, E1-5, E1-6, E2-4, S1-6, G1-1.",
  },
  {
    timestamp: 3000,
    agent: "extractor",
    message:
      "Double materiality matrix extracted. Handing off to Fetcher.",
  },
  {
    timestamp: 3600,
    agent: "fetcher",
    message:
      "Extracting iXBRL CapEx tags from EU Taxonomy Table...",
  },
  {
    timestamp: 4400,
    agent: "fetcher",
    message:
      "Taxonomy-eligible CapEx: 31% of total. Parsing activity codes...",
  },
  {
    timestamp: 5200,
    agent: "fetcher",
    message:
      "Querying Infogreffe (RCS) for Lumiere Systemes SA registry filings...",
  },
  {
    timestamp: 6200,
    agent: "fetcher",
    message:
      "Retrieved Rapport de gestion, DPEF, and Bilan energetique.",
  },
  {
    timestamp: 7000,
    agent: "fetcher",
    message:
      "Cross-referencing via BRIS. Registry evidence matched 5/6 data points.",
  },
  {
    timestamp: 7600,
    agent: "auditor",
    message:
      "Cross-referencing Management Report financials against ESRS disclosures...",
  },
  {
    timestamp: 8200,
    agent: "auditor",
    message:
      "E1-1 Transition plan: PARTIAL — no 1.5C pathway alignment found.",
  },
  {
    timestamp: 8700,
    agent: "auditor",
    message:
      "E1-6 GHG emissions: MISSING — Scope 3 not disclosed in Management Report.",
  },
  {
    timestamp: 9200,
    agent: "auditor",
    message:
      "E2-4 Pollution reporting: NON-COMPLIANT — DPEF section absent.",
  },
  {
    timestamp: 9700,
    agent: "auditor",
    message:
      "CapEx Taxonomy alignment computed: 31%. Status: Partially Aligned.",
  },
  {
    timestamp: 10200,
    agent: "auditor",
    message:
      "Projected Art. 51 CSRD fine: EUR 4.2M based on reported net turnover.",
  },
  {
    timestamp: 10800,
    agent: "consultant",
    message:
      "Generating Taxonomy alignment roadmap (three-pillar)...",
  },
  {
    timestamp: 11400,
    agent: "consultant",
    message:
      "Infrastructure pillar: +18% alignment — CRITICAL priority.",
  },
  {
    timestamp: 12000,
    agent: "consultant",
    message:
      "Power pillar: +12% alignment — PPA gap under GO scheme.",
  },
  {
    timestamp: 12500,
    agent: "consultant",
    message:
      "Workload pillar: +7% alignment — utilization lever.",
  },
  {
    timestamp: 13000,
    agent: "consultant",
    message:
      "CSRD audit complete. Compliance report ready.",
  },
];

// ---------------------------------------------------------------------------
// Compliance Check Mock Data
// ---------------------------------------------------------------------------

export const MOCK_COMPLIANCE_CHECK: ComplianceCheckResult = {
  audit_id: "eu-cc-a1b2c3d4-5678-90ab-cdef-123456789abc",
  generated_at: "2026-02-21T15:10:22Z",
  schema_version: "2.0",
  mode: "compliance_check",

  company: {
    name: "Lumiere Systemes SA",
    lei: null,
    sector: "AI Infrastructure / Cloud Computing",
    fiscal_year: 2025,
    jurisdiction: "France",
    report_title: "User-Provided Sustainability Description",
  },

  extracted_goals: [
    {
      id: "goal-1",
      description:
        "Net-zero emissions target by 2040 across all data center operations.",
      esrs_relevance: "E1-1",
      confidence: 0.7,
    },
    {
      id: "goal-2",
      description:
        "Data centers consume approximately 120 GWh annually with 29% from renewable sources.",
      esrs_relevance: "E1-5",
      confidence: 0.9,
    },
    {
      id: "goal-3",
      description:
        "Plan to increase renewable energy procurement to 60% by 2028 through corporate PPAs.",
      esrs_relevance: "E1-5",
      confidence: 0.7,
    },
    {
      id: "goal-4",
      description:
        "No Scope 3 emissions inventory has been conducted to date.",
      esrs_relevance: "E1-6",
      confidence: 0.5,
    },
  ],

  esrs_coverage: [
    {
      esrs_id: "E1-1",
      standard_name: "Transition Plan for Climate Change Mitigation",
      coverage: "partial",
      details:
        "Net-zero target year (2040) is stated, but no interim milestones, CapEx commitment, or 1.5°C pathway reference found.",
    },
    {
      esrs_id: "E1-5",
      standard_name: "Energy Consumption and Mix",
      coverage: "partial",
      details:
        "Total energy consumption (120 GWh) and renewable percentage (29%) disclosed. Missing: breakdown by source and year-on-year trend.",
    },
    {
      esrs_id: "E1-6",
      standard_name: "Gross Scopes 1, 2, 3 GHG Emissions",
      coverage: "not_covered",
      details:
        "No Scope 1, 2, or 3 emissions data disclosed. No GHG intensity metric or base year. Scope 3 inventory explicitly absent.",
    },
  ],

  todo_list: [
    {
      id: "todo-1",
      priority: "critical",
      esrs_id: "E1-6",
      title: "Conduct Scope 1 & 2 GHG inventory",
      description:
        "Commission a verified GHG inventory covering Scope 1 (direct) and Scope 2 (market-based and location-based) emissions across all data center facilities. This is the most critical gap — CSRD requires quantitative disclosure with methodology.",
      regulatory_reference: "ESRS E1-6, DR E1-6.44–E1-6.53",
      estimated_effort: "high",
    },
    {
      id: "todo-2",
      priority: "critical",
      esrs_id: "E1-6",
      title: "Initiate Scope 3 emissions screening",
      description:
        "Begin a Scope 3 category screening to identify material upstream and downstream emission sources. At minimum, Category 1 (purchased goods), Category 2 (capital goods), and Category 11 (use of sold products) should be assessed.",
      regulatory_reference: "ESRS E1-6, DR E1-6.51–E1-6.53",
      estimated_effort: "high",
    },
    {
      id: "todo-3",
      priority: "critical",
      esrs_id: "CSRD",
      title: "Prepare XHTML/iXBRL Annual Management Report",
      description:
        "Your company currently lacks a properly formatted CSRD-compliant Annual Management Report. Engage an XBRL tagging provider to produce the machine-readable XHTML/iXBRL filing required under ESEF regulation.",
      regulatory_reference: "CSRD Art. 29d, ESEF Regulation (EU) 2019/815",
      estimated_effort: "high",
    },
    {
      id: "todo-4",
      priority: "critical",
      esrs_id: "CSRD",
      title: "Engage CSRD-qualified auditor for limited assurance",
      description:
        "Under Art. 34 of CSRD, sustainability reporting must be subject to limited assurance by a qualified auditor. Begin the engagement process early to allow time for gap remediation before the filing deadline.",
      regulatory_reference: "CSRD Art. 34, Directive (EU) 2022/2464",
      estimated_effort: "high",
    },
    {
      id: "todo-5",
      priority: "high",
      esrs_id: "E1-1",
      title: "Develop quantified transition plan with interim milestones",
      description:
        "Your 2040 net-zero target lacks interim decarbonisation milestones and quantified CapEx commitments. Define 2025/2028/2030 reduction targets (vs. a stated base year) and link them to specific EU Taxonomy activities.",
      regulatory_reference: "ESRS E1-1, DR E1-1.01–E1-1.09",
      estimated_effort: "medium",
    },
    {
      id: "todo-6",
      priority: "high",
      esrs_id: "E1-5",
      title: "Disclose energy consumption breakdown by source",
      description:
        "While total consumption (120 GWh) and renewable share (29%) are stated, CSRD requires a breakdown by energy source: grid electricity, natural gas, on-site renewables, and year-on-year energy intensity trend.",
      regulatory_reference: "ESRS E1-5, DR E1-5.30–E1-5.37",
      estimated_effort: "low",
    },
  ],

  estimated_compliance_cost: {
    estimated_range_low_eur: 1_500_000,
    estimated_range_high_eur: 6_000_000,
    basis:
      "Art. 51 CSRD Directive (EU) 2022/2464 — indicative range based on disclosure gaps",
    caveat:
      "This estimate is based on incomplete, unstructured data and should not be used for financial planning. A full audit with structured XHTML/iXBRL management report data is required for accurate compliance cost assessment.",
  },

  pipeline: {
    total_duration_ms: 9_820,
    agents: [
      { agent: "extractor", duration_ms: 3_410, status: "completed" },
      { agent: "auditor", duration_ms: 4_120, status: "completed" },
      { agent: "consultant", duration_ms: 2_290, status: "completed" },
    ],
  },
};

export const COMPLIANCE_CHECK_LOGS: AuditLog[] = [
  {
    timestamp: 200,
    agent: "extractor",
    message:
      "Initializing compliance check — parsing free-text sustainability description.",
  },
  {
    timestamp: 800,
    agent: "extractor",
    message:
      "Identifying sustainability claims and goals in unstructured text...",
  },
  {
    timestamp: 1400,
    agent: "extractor",
    message:
      "Found 4 sustainability goals. Mapping to ESRS E1 standards...",
  },
  {
    timestamp: 2000,
    agent: "extractor",
    message:
      "Company metadata extracted: AI Infrastructure sector, France jurisdiction.",
  },
  {
    timestamp: 2600,
    agent: "extractor",
    message:
      "Extraction complete. Handing off to Auditor (Fetcher skipped — no structured data).",
  },
  {
    timestamp: 3200,
    agent: "auditor",
    message:
      "Assessing ESRS E1 coverage from extracted claims...",
  },
  {
    timestamp: 3800,
    agent: "auditor",
    message:
      "E1-1 Transition Plan: PARTIAL — target year found, interim milestones missing.",
  },
  {
    timestamp: 4400,
    agent: "auditor",
    message:
      "E1-5 Energy: PARTIAL — consumption and renewable % found, breakdown missing.",
  },
  {
    timestamp: 5000,
    agent: "auditor",
    message:
      "E1-6 GHG Emissions: NOT COVERED — no emissions data disclosed.",
  },
  {
    timestamp: 5600,
    agent: "auditor",
    message:
      "Compliance cost range estimated: EUR 1.5M – 6.0M (indicative, data insufficient).",
  },
  {
    timestamp: 6200,
    agent: "consultant",
    message:
      "Generating prioritized compliance to-do list...",
  },
  {
    timestamp: 6800,
    agent: "consultant",
    message:
      "6 action items generated across E1-1, E1-5, E1-6, and CSRD foundational requirements.",
  },
  {
    timestamp: 7400,
    agent: "consultant",
    message:
      "2 critical items: GHG inventory + XHTML report preparation.",
  },
  {
    timestamp: 8000,
    agent: "consultant",
    message:
      "Compliance check complete. To-do list ready.",
  },
];

// ============================================================================
// v5.0 — Unified ComplianceResult Mock Data (Iteration 11+)
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
// v5.0 Analysis Logs — 3-agent pipeline (Extractor → Scorer → Advisor)
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
// v5.0 Free Text Analysis Logs — 3-agent pipeline
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
