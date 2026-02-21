import type { AuditLog, CSRDAudit } from "./types";

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
