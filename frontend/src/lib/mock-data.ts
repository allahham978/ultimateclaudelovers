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
      title: "Set Up Greenhouse Gas Emissions Tracking",
      description:
        "Your report does not include any Scope 1, 2, or 3 greenhouse gas emissions data. As a large EU company, this is a mandatory disclosure — without it, your CSRD report is incomplete. Start by engaging an environmental consultant to conduct a baseline GHG inventory across all data center facilities.",
      regulatory_reference: "Climate Change — GHG Emissions (ESRS E1-6)",
      category: "Climate & Energy",
      impact: "Without emissions data, Lumiere Systemes cannot demonstrate climate accountability to investors and faces potential regulatory penalties.",
    },
    {
      id: "rec-2",
      priority: "critical",
      esrs_id: "S1-1",
      title: "Assess Your Workforce's Sustainability Impact",
      description:
        "No workforce materiality assessment was found in your report. As a company with 500 employees, you must assess how your operations affect workers — covering working conditions, equal treatment, and health & safety. Begin with a double materiality assessment involving employee representatives.",
      regulatory_reference: "Own Workforce — Materiality Assessment (ESRS S1-1)",
      category: "Workforce & Social",
      impact: "Missing workforce data means Lumiere Systemes cannot show it meets basic EU labor and social responsibility standards.",
    },
    {
      id: "rec-3",
      priority: "high",
      esrs_id: "E1-1",
      title: "Create a Climate Transition Plan with Clear Milestones",
      description:
        "Your 2040 net-zero target lacks interim milestones and investment commitments. Define reduction targets for 2025, 2028, and 2030, and link them to specific capital expenditure plans. With green CapEx of EUR 12M (18% of total), consider targeting the 30% threshold to demonstrate serious commitment.",
      regulatory_reference: "Climate Change — Transition Plan (ESRS E1-1)",
      category: "Climate & Energy",
      impact: "Without a credible transition plan, investors may question the company's long-term climate strategy and resilience.",
    },
    {
      id: "rec-4",
      priority: "high",
      esrs_id: "E2-4",
      title: "Report on Pollution from Operations",
      description:
        "Your data center operations generate coolant waste and electronic waste, but none of this is reported. Disclose pollutant emissions from cooling systems, e-waste handling, and any hazardous substance releases to meet EU reporting requirements.",
      regulatory_reference: "Pollution — Substances of Concern (ESRS E2-4)",
      category: "Pollution & Resources",
      impact: "Unreported pollution data could expose the company to environmental compliance risks and stakeholder scrutiny.",
    },
    {
      id: "rec-5",
      priority: "high",
      esrs_id: "G1-1",
      title: "Publish Comprehensive Business Ethics Policies",
      description:
        "Your anti-corruption, lobbying, and whistleblower policies are only partially documented. Consolidate these into a comprehensive business conduct policy with clear board-level oversight and publish it for stakeholder transparency.",
      regulatory_reference: "Governance — Business Conduct (ESRS G1-1)",
      category: "Governance",
      impact: "Incomplete governance disclosures can undermine trust with investors, regulators, and business partners.",
    },
    {
      id: "rec-6",
      priority: "moderate",
      esrs_id: "E1-5",
      title: "Break Down Energy Consumption by Source",
      description:
        "Your total energy consumption (120 GWh) is disclosed, but you need to show the breakdown by source — grid electricity, natural gas, and on-site renewables — plus year-over-year intensity trends.",
      regulatory_reference: "Climate Change — Energy Consumption (ESRS E1-5)",
      category: "Climate & Energy",
      impact: "Without an energy source breakdown, stakeholders cannot assess the company's renewable energy progress.",
    },
    {
      id: "rec-7",
      priority: "moderate",
      esrs_id: "E3-1",
      title: "Measure and Report Water Usage",
      description:
        "Water consumption for data center cooling is not disclosed. Provide total water withdrawal, consumption, and discharge volumes with a breakdown by source to address this gap.",
      regulatory_reference: "Water & Marine Resources — Impact Assessment (ESRS E3-1)",
      category: "Pollution & Resources",
      impact: "Data centers are significant water consumers — unreported usage may attract regulatory and community attention.",
    },
    {
      id: "rec-8",
      priority: "moderate",
      esrs_id: "S2-1",
      title: "Map Human Rights Risks in Your Supply Chain",
      description:
        "No assessment of workers in your supply chain (hardware suppliers, subcontractors) has been disclosed. Identify where human rights risks are highest and describe your due diligence processes.",
      regulatory_reference: "Value Chain Workers — Impact Assessment (ESRS S2-1)",
      category: "Workforce & Social",
      impact: "Supply chain labor risks can lead to reputational damage and regulatory action under EU due diligence rules.",
    },
    {
      id: "rec-9",
      priority: "moderate",
      esrs_id: "E4-1",
      title: "Check If Your Sites Affect Protected Nature Areas",
      description:
        "No biodiversity assessment was found. Screen your operational sites for proximity to Natura 2000 areas or other biodiversity-sensitive zones and report any material findings.",
      regulatory_reference: "Biodiversity — Impact Assessment (ESRS E4-1)",
      category: "Biodiversity & Ecosystems",
      impact: "Unassessed biodiversity impacts could delay site permits and attract environmental compliance actions.",
    },
    {
      id: "rec-10",
      priority: "low",
      esrs_id: "S1-6",
      title: "Add More Detail to Workforce Diversity Data",
      description:
        "Employee characteristics are disclosed, but adding breakdowns by contract type, gender pay gap, and disability representation would strengthen your report and meet best-practice expectations.",
      regulatory_reference: "Own Workforce — Diversity Metrics (ESRS S1-6)",
      category: "Workforce & Social",
      impact: "More granular diversity data demonstrates genuine commitment to inclusion and can improve employer brand.",
    },
    {
      id: "rec-11",
      priority: "low",
      esrs_id: "ESRS 2",
      title: "Detail How Your Board Oversees Sustainability",
      description:
        "General governance disclosures are present but could be strengthened by adding specific meeting frequencies, decision records, and sustainability competency details for board members.",
      regulatory_reference: "General Disclosures — Governance (ESRS 2 GOV-1)",
      category: "Governance",
      impact: "Stronger governance disclosures build investor confidence in sustainability oversight.",
    },
    {
      id: "rec-12",
      priority: "low",
      esrs_id: "E5-1",
      title: "Track Waste and Circular Economy Metrics",
      description:
        "Circular economy metrics like waste generation, recycling rates, and material inflows are not yet disclosed. For an AI infrastructure company, server hardware lifecycle and e-waste recycling rates are particularly relevant.",
      regulatory_reference: "Circular Economy — Resource Use (ESRS E5-1)",
      category: "Pollution & Resources",
      impact: "E-waste is a growing concern for tech companies — proactive reporting shows environmental responsibility.",
    },
    {
      id: "rec-13",
      priority: "low",
      esrs_id: "S3-1",
      title: "Assess Impact on Local Communities",
      description:
        "No community impact assessment was found. For data center operations, consider impacts like noise, local infrastructure strain, and job creation opportunities in surrounding communities.",
      regulatory_reference: "Affected Communities — Impact Assessment (ESRS S3-1)",
      category: "Communities & Consumers",
      impact: "Community concerns can delay expansion plans and affect local operating permits.",
    },
    {
      id: "rec-14",
      priority: "low",
      esrs_id: "S4-1",
      title: "Evaluate How Your AI Services Affect End Users",
      description:
        "No assessment of impacts on consumers or end-users of your AI services was found. Consider data privacy, algorithmic fairness, and digital accessibility as potential material topics.",
      regulatory_reference: "Consumers & End-Users — Impact Assessment (ESRS S4-1)",
      category: "Communities & Consumers",
      impact: "AI ethics and user impact are increasingly scrutinized by regulators and the public.",
    },
    {
      id: "rec-15",
      priority: "low",
      esrs_id: "E1-9",
      title: "Quantify the Financial Risks of Climate Change",
      description:
        "While some climate data exists, the financial effects of physical and transition climate risks are not quantified. Conduct a scenario analysis to understand how climate events could affect your operations and finances.",
      regulatory_reference: "Climate Change — Financial Effects (ESRS E1-9)",
      category: "Climate & Energy",
      impact: "Unquantified climate risks may lead investors to undervalue the company's climate resilience.",
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
