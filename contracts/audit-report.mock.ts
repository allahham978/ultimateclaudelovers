import type { AuditReport } from "./audit-report.schema";

export const MOCK_AUDIT: AuditReport = {
  audit_id: "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  generated_at: "2026-02-21T14:32:07Z",
  schema_version: "1.0",

  company: {
    name: "NovaCorp AI",
    ticker: "NVCA",
    sector: "AI / Cloud Infrastructure",
    fiscal_year: 2025,
    report_title: "NovaCorp Sustainability & ESG Report FY2025",
  },

  gap_score: {
    value: 38,
    label: "Significant Gap",
  },

  ledger: [
    {
      id: "led-1",
      category: "energy",
      the_say: {
        claim: "100% renewable energy across all data centers by 2027.",
        source_ref: "ESG Report 2025, p.12",
      },
      the_do: {
        finding:
          "Only 23% of CapEx allocated to renewable procurement. No signed PPAs found for 2026-2027.",
        capex_usd: 140_000_000,
        source_ref: "10-K Filing 2025, Note 7",
      },
      alignment_score: 18,
    },
    {
      id: "led-2",
      category: "hardware",
      the_say: {
        claim: "Transitioning to energy-efficient next-gen GPU clusters.",
        source_ref: "ESG Report 2025, p.24",
      },
      the_do: {
        finding:
          "$2.1B spent on H100 clusters. No procurement of B200 or successor architectures found in filings.",
        capex_usd: 2_100_000_000,
        source_ref: "10-K Filing 2025, Note 4",
      },
      alignment_score: 34,
    },
    {
      id: "led-3",
      category: "emissions",
      the_say: {
        claim: "Scope 2 emissions reduced by 40% year-over-year.",
        source_ref: "ESG Report 2025, p.8",
      },
      the_do: {
        finding:
          "Scope 2 declined 12% due to grid mix changes, not direct investment. Compute capacity grew 3x.",
        capex_usd: null,
        source_ref: "CDP Disclosure 2025, Section C6",
      },
      alignment_score: 41,
    },
    {
      id: "led-4",
      category: "water",
      the_say: {
        claim: "Water-positive operations in all Tier-1 facilities.",
        source_ref: "ESG Report 2025, p.31",
      },
      the_do: {
        finding:
          "Tier-1 facilities use evaporative cooling. Water consumption up 28% YoY. No offset credits purchased.",
        capex_usd: 4_200_000,
        source_ref: "10-K Filing 2025, Note 12",
      },
      alignment_score: 22,
    },
    {
      id: "led-5",
      category: "energy",
      the_say: {
        claim: "AI training workloads optimized for minimal energy footprint.",
        source_ref: "ESG Report 2025, p.19",
      },
      the_do: {
        finding:
          "Average GPU utilization at 41%. No investment in workload scheduling or sparsity optimization found.",
        capex_usd: null,
        source_ref: "Earnings Call Q4 2025 Transcript",
      },
      alignment_score: 85,
    },
  ],

  recommendations: {
    hardware: {
      title: "Hardware Upgrades",
      summary:
        "Accelerate procurement of next-gen GPU architectures (B200/GB300) which deliver 4x perf-per-watt over current H100 fleet. This single move closes ~30% of the energy gap without reducing compute capacity.",
      priority: "critical",
    },
    power: {
      title: "Power Procurement",
      summary:
        "Sign 3-5 year Power Purchase Agreements for wind/solar in regions hosting Tier-1 facilities. Current renewable coverage is 23% — reaching 60% by 2027 is achievable and aligns CapEx with the stated net-zero claim.",
      priority: "high",
    },
    workload: {
      title: "Workload Optimization",
      summary:
        "Implement cluster-wide job scheduling and mixed-precision training to raise GPU utilization from 41% to 70%+. This is the highest-ROI lever — it reduces energy per FLOP without additional hardware spend.",
      priority: "moderate",
    },
  },

  sources: [
    {
      id: "src-1",
      document_name: "NovaCorp Sustainability & ESG Report FY2025",
      document_type: "esg_report",
      url: null,
    },
    {
      id: "src-2",
      document_name: "NovaCorp 10-K Annual Filing FY2025",
      document_type: "sec_filing",
      url: null,
    },
    {
      id: "src-3",
      document_name: "CDP Climate Disclosure 2025",
      document_type: "third_party",
      url: null,
    },
    {
      id: "src-4",
      document_name: "NovaCorp Q4 2025 Earnings Call Transcript",
      document_type: "press_release",
      url: null,
    },
  ],

  pipeline: {
    total_duration_ms: 14_320,
    agents: [
      { agent: "extractor", duration_ms: 4_210, status: "completed" },
      { agent: "fetcher", duration_ms: 5_890, status: "completed" },
      { agent: "auditor", duration_ms: 2_940, status: "completed" },
      { agent: "consultant", duration_ms: 1_280, status: "completed" },
    ],
  },
};
