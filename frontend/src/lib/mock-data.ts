import type { AuditLog, CSRDAudit, ComplianceCheckResult } from "./types";

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
