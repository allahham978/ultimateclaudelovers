import type {
  CSRDAudit,
  ESRSLedgerItem,
  EvidenceSource,
  RoadmapPillar,
  Source,
} from "@/lib/types";
import {
  formatDuration,
  formatEUR,
  taxonomyColor,
  taxonomyStatusStyle,
  esrsStatusStyle,
  materialityStyle,
  priorityColor,
} from "@/lib/utils";

/* ================================================================= */
/* EU Flag SVG (12-star ring)                                         */
/* ================================================================= */

function EUFlag({ className }: { className?: string }) {
  const stars = Array.from({ length: 12 }, (_, i) => {
    const angle = (i * 30 - 90) * (Math.PI / 180);
    const cx = 12 + 8 * Math.cos(angle);
    const cy = 12 + 8 * Math.sin(angle);
    return (
      <circle key={i} cx={cx} cy={cy} r={1.2} fill="#FFD617" />
    );
  });
  return (
    <svg
      viewBox="0 0 24 24"
      className={className}
      aria-label="EU flag"
    >
      <rect width="24" height="24" rx="4" fill="#003399" />
      {stars}
    </svg>
  );
}

/* ================================================================= */
/* Results View                                                       */
/* ================================================================= */

export default function ResultsView({ audit }: { audit: CSRDAudit }) {
  const {
    company,
    taxonomy_alignment,
    compliance_cost,
    esrs_ledger,
    roadmap,
    registry_source,
    sources,
    pipeline,
  } = audit;

  return (
    <div className="animate-results space-y-12">
      {/* ----- Company Header with EU Authority ----- */}
      <section className="reveal">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <div className="flex items-center gap-2.5">
              <EUFlag className="h-5 w-5 shrink-0" />
              <span className="text-[10px] font-bold uppercase tracking-widest text-accent">
                CSRD Compliance Report
              </span>
            </div>
            <h1 className="mt-2 font-display text-4xl tracking-tight text-slate-900">
              {company.name}
            </h1>
            <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-muted">
              {company.lei && (
                <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs font-medium text-slate-600">
                  LEI {company.lei.slice(0, 8)}...
                </span>
              )}
              <span>{company.sector}</span>
              <span className="text-slate-300">|</span>
              <span>{company.jurisdiction}</span>
              <span className="text-slate-300">|</span>
              <span>FY{company.fiscal_year}</span>
            </div>
          </div>
          <div className="flex items-center gap-2 rounded-card border border-slate-200 bg-white px-3 py-2 text-xs text-muted">
            <svg
              className="h-3.5 w-3.5 text-slate-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"
              />
            </svg>
            <span>
              Registry:{" "}
              <span className="font-medium text-slate-700">
                {registry_source.name}
              </span>
            </span>
          </div>
        </div>
      </section>

      {/* ----- Taxonomy Verdict ----- */}
      <section className="reveal reveal-1">
        <TaxonomyVerdict
          alignment={taxonomy_alignment}
          cost={compliance_cost}
        />
      </section>

      {/* ----- ESRS Ledger ----- */}
      <section className="reveal reveal-2 space-y-4">
        <SectionHeading>ESRS Double Materiality Ledger</SectionHeading>
        <div className="card overflow-hidden">
          {/* Table Header */}
          <div className="hidden border-b border-slate-100 bg-slate-50/60 px-5 py-2.5 sm:grid sm:grid-cols-12 sm:gap-3">
            <span className="col-span-1 text-[10px] font-bold uppercase tracking-widest text-slate-400">
              ESRS
            </span>
            <span className="col-span-3 text-[10px] font-bold uppercase tracking-widest text-slate-400">
              Data Point
            </span>
            <span className="col-span-1 text-center text-[10px] font-bold uppercase tracking-widest text-slate-400">
              Impact
            </span>
            <span className="col-span-1 text-center text-[10px] font-bold uppercase tracking-widest text-slate-400">
              Financial
            </span>
            <span className="col-span-1 text-center text-[10px] font-bold uppercase tracking-widest text-slate-400">
              Status
            </span>
            <span className="col-span-2 text-[10px] font-bold uppercase tracking-widest text-slate-400">
              Evidence
            </span>
            <span className="col-span-3 text-[10px] font-bold uppercase tracking-widest text-slate-400">
              Registry
            </span>
          </div>

          {/* Table Rows */}
          {esrs_ledger.map((item) => (
            <ESRSRow key={item.id} item={item} />
          ))}
        </div>
      </section>

      {/* ----- Taxonomy Roadmap ----- */}
      <section className="reveal reveal-4 space-y-4">
        <SectionHeading>Taxonomy Alignment Roadmap</SectionHeading>
        <div className="grid gap-4 sm:grid-cols-3">
          <RoadmapCard pillar={roadmap.hardware} />
          <RoadmapCard pillar={roadmap.power} />
          <RoadmapCard pillar={roadmap.workload} />
        </div>

        {/* Projected total */}
        <div className="card flex items-center justify-between px-5 py-3">
          <span className="text-sm text-muted">
            Projected alignment if all pillars implemented
          </span>
          <div className="flex items-baseline gap-1.5">
            <span className="font-mono text-sm text-muted">
              {taxonomy_alignment.capex_aligned_pct}%
            </span>
            <svg
              className="h-3 w-3 text-slate-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M13 7l5 5m0 0l-5 5m5-5H6"
              />
            </svg>
            <span className="font-mono text-sm font-bold text-emerald-600">
              {taxonomy_alignment.capex_aligned_pct +
                roadmap.hardware.alignment_increase_pct +
                roadmap.power.alignment_increase_pct +
                roadmap.workload.alignment_increase_pct}
              %
            </span>
          </div>
        </div>
      </section>

      {/* ----- Pipeline Trace ----- */}
      <section className="reveal reveal-6 space-y-4">
        <div className="flex items-baseline justify-between">
          <SectionHeading>Agent Pipeline</SectionHeading>
          <span className="font-mono text-xs text-muted">
            {formatDuration(pipeline.total_duration_ms)} total
          </span>
        </div>
        <div className="card overflow-hidden p-4">
          <div className="flex h-9 w-full overflow-hidden rounded-lg">
            {pipeline.agents.map((agent, i) => {
              const pct =
                (agent.duration_ms / pipeline.total_duration_ms) * 100;
              const opacity = [1, 0.75, 0.55, 0.4][i] ?? 0.4;
              return (
                <div
                  key={agent.agent}
                  className="pipeline-segment flex items-center justify-center overflow-hidden"
                  style={{
                    width: `${pct}%`,
                    backgroundColor: `rgba(79, 70, 229, ${opacity})`,
                    animationDelay: `${0.8 + i * 0.12}s`,
                  }}
                  title={`${agent.agent}: ${formatDuration(agent.duration_ms)}`}
                >
                  <span className="truncate px-2 text-[11px] font-medium capitalize text-white">
                    {agent.agent}
                  </span>
                </div>
              );
            })}
          </div>
          <div className="mt-2.5 flex">
            {pipeline.agents.map((agent) => {
              const pct =
                (agent.duration_ms / pipeline.total_duration_ms) * 100;
              return (
                <div
                  key={agent.agent}
                  className="text-center"
                  style={{ width: `${pct}%` }}
                >
                  <span className="font-mono text-[10px] text-muted">
                    {formatDuration(agent.duration_ms)}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* ----- Sources ----- */}
      <section className="reveal reveal-7 space-y-4">
        <SectionHeading>Sources</SectionHeading>
        <div className="grid gap-3 sm:grid-cols-2">
          {sources.map((src) => (
            <SourceCard key={src.id} source={src} />
          ))}
        </div>
      </section>
    </div>
  );
}

/* ================================================================= */
/* Section Heading                                                    */
/* ================================================================= */

function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="text-xs font-semibold uppercase tracking-widest text-muted">
      {children}
    </h2>
  );
}

/* ================================================================= */
/* Taxonomy Verdict — Primary Metric + Status Badge + Fine KPI        */
/* ================================================================= */

function TaxonomyVerdict({
  alignment,
  cost,
}: {
  alignment: CSRDAudit["taxonomy_alignment"];
  cost: CSRDAudit["compliance_cost"];
}) {
  const size = 180;
  const stroke = 10;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - alignment.capex_aligned_pct / 100);
  const color = taxonomyColor(alignment.capex_aligned_pct);
  const badge = taxonomyStatusStyle(alignment.status);

  return (
    <div className="card overflow-hidden">
      <div className="grid sm:grid-cols-3">
        {/* Gauge */}
        <div className="flex flex-col items-center justify-center border-b border-slate-100 px-6 py-10 sm:col-span-2 sm:border-b-0 sm:border-r">
          <p className="mb-6 text-xs font-semibold uppercase tracking-widest text-muted">
            EU Taxonomy CapEx Alignment
          </p>
          <div className="relative inline-flex items-center justify-center">
            <svg
              width={size}
              height={size}
              className="-rotate-90"
              aria-hidden="true"
            >
              <circle
                cx={size / 2}
                cy={size / 2}
                r={radius}
                fill="none"
                stroke="#E2E8F0"
                strokeWidth={stroke}
              />
              <circle
                cx={size / 2}
                cy={size / 2}
                r={radius}
                fill="none"
                stroke={color}
                strokeWidth={stroke}
                strokeLinecap="round"
                strokeDasharray={circumference}
                strokeDashoffset={offset}
                className="gauge-arc"
                style={
                  {
                    "--circumference": circumference,
                  } as React.CSSProperties
                }
              />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span
                className="font-display text-5xl leading-none"
                style={{ color }}
              >
                {alignment.capex_aligned_pct}
              </span>
              <span className="mt-0.5 font-mono text-xs text-muted">%</span>
            </div>
          </div>
          <span
            className={`mt-5 inline-block rounded-full border px-3 py-1 text-xs font-bold uppercase tracking-wider ${badge.bg} ${badge.text}`}
          >
            {badge.label}
          </span>
        </div>

        {/* KPI Panel */}
        <div className="flex flex-col justify-center gap-6 p-6">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">
              Status
            </p>
            <p className="mt-1 text-sm font-medium text-slate-700">
              {alignment.label}
            </p>
          </div>
          <div>
            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">
              Cost of Non-Compliance
            </p>
            <p className="mt-1 font-mono text-2xl font-bold text-red-600">
              {formatEUR(cost.projected_fine_eur)}
            </p>
            <p className="mt-1 text-[11px] leading-relaxed text-muted">
              {cost.basis}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ================================================================= */
/* ESRS Ledger Row                                                    */
/* ================================================================= */

const EVIDENCE_LABELS: Record<EvidenceSource, string> = {
  management_report: "Mgmt Report",
  taxonomy_table: "Taxonomy Table",
  transition_plan: "Transition Plan",
};

function ESRSRow({ item }: { item: ESRSLedgerItem }) {
  const status = esrsStatusStyle(item.status);
  const impact = materialityStyle(item.impact_materiality);
  const financial = materialityStyle(item.financial_materiality);

  return (
    <div className="grid grid-cols-1 gap-2 border-b border-slate-100 px-5 py-3.5 last:border-b-0 sm:grid-cols-12 sm:items-center sm:gap-3">
      {/* ESRS ID */}
      <div className="sm:col-span-1">
        <span className="rounded bg-accent/10 px-1.5 py-0.5 font-mono text-xs font-bold text-accent">
          {item.esrs_id}
        </span>
      </div>

      {/* Data Point */}
      <div className="sm:col-span-3">
        <p className="text-sm leading-snug text-slate-700">
          {item.data_point}
        </p>
      </div>

      {/* Impact Materiality */}
      <div className="sm:col-span-1 sm:text-center">
        <span
          className={`inline-block rounded px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${impact.bg} ${impact.text}`}
        >
          {item.impact_materiality === "not_material"
            ? "N/M"
            : item.impact_materiality}
        </span>
      </div>

      {/* Financial Materiality */}
      <div className="sm:col-span-1 sm:text-center">
        <span
          className={`inline-block rounded px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${financial.bg} ${financial.text}`}
        >
          {item.financial_materiality === "not_material"
            ? "N/M"
            : item.financial_materiality}
        </span>
      </div>

      {/* Status */}
      <div className="sm:col-span-1 sm:text-center">
        <span
          className={`inline-block rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${status.bg} ${status.text}`}
        >
          {status.label}
        </span>
      </div>

      {/* Evidence Source */}
      <div className="sm:col-span-2">
        <span className="inline-block rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] font-medium text-slate-600">
          {EVIDENCE_LABELS[item.evidence_source]}
        </span>
      </div>

      {/* Registry Evidence */}
      <div className="sm:col-span-3">
        <p className="text-[11px] leading-snug text-muted">
          {item.registry_evidence}
        </p>
      </div>
    </div>
  );
}

/* ================================================================= */
/* Roadmap Pillar Card                                                */
/* ================================================================= */

function RoadmapCard({ pillar }: { pillar: RoadmapPillar }) {
  const { bg, text } = priorityColor(pillar.priority);

  return (
    <div className="card flex flex-col justify-between p-5">
      <div>
        <div className="flex items-center justify-between">
          <span
            className={`inline-block rounded-full border px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider ${bg} ${text}`}
          >
            {pillar.priority}
          </span>
          <span className="font-mono text-lg font-bold text-emerald-600">
            +{pillar.alignment_increase_pct}%
          </span>
        </div>
        <h3 className="mt-3 font-display text-lg text-slate-900">
          {pillar.title}
        </h3>
        <p className="mt-2 text-sm leading-relaxed text-muted">
          {pillar.summary}
        </p>
      </div>
      <div className="mt-4 flex items-center gap-1.5 border-t border-slate-100 pt-3">
        <svg
          className="h-3 w-3 text-emerald-500"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2.5}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"
          />
        </svg>
        <span className="text-[11px] font-medium text-emerald-600">
          +{pillar.alignment_increase_pct}% Taxonomy Alignment
        </span>
      </div>
    </div>
  );
}

/* ================================================================= */
/* Source Card                                                        */
/* ================================================================= */

function SourceCard({ source }: { source: Source }) {
  const typeLabels: Record<string, string> = {
    csrd_report: "CSRD Report",
    eu_registry: "EU Registry",
    national_filing: "National Filing",
    third_party: "Third Party",
  };

  return (
    <div className="flex items-start gap-3 rounded-card border border-slate-200 bg-white px-4 py-3">
      <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded bg-slate-100">
        <svg
          className="h-3 w-3 text-slate-500"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
          />
        </svg>
      </div>
      <div>
        <p className="text-sm font-medium text-slate-800">
          {source.document_name}
        </p>
        <p className="text-[11px] text-muted">
          {typeLabels[source.document_type] ?? source.document_type}
        </p>
      </div>
    </div>
  );
}
