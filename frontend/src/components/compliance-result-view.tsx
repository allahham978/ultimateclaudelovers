"use client";

import { useState } from "react";
import type { ComplianceResult, Priority, Recommendation } from "@/lib/types";
import {
  formatDuration,
  formatEUR,
  scoreColor,
  scoreStyle,
  priorityTierStyle,
} from "@/lib/utils";

/* ================================================================= */
/* EU Flag SVG (12-star ring)                                          */
/* ================================================================= */

function EUFlag({ className }: { className?: string }) {
  const stars = Array.from({ length: 12 }, (_, i) => {
    const angle = (i * 30 - 90) * (Math.PI / 180);
    const cx = 12 + 8 * Math.cos(angle);
    const cy = 12 + 8 * Math.sin(angle);
    return <circle key={i} cx={cx} cy={cy} r={1.2} fill="#FFD617" />;
  });
  return (
    <svg viewBox="0 0 24 24" className={className} aria-label="EU flag">
      <rect width="24" height="24" rx="4" fill="#003399" />
      {stars}
    </svg>
  );
}

/* ================================================================= */
/* Section Heading                                                     */
/* ================================================================= */

function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="text-xs font-semibold uppercase tracking-widest text-muted">
      {children}
    </h2>
  );
}

/* ================================================================= */
/* Compliance Result View — Unified component for both modes           */
/* ================================================================= */

export default function ComplianceResultView({
  result,
}: {
  result: ComplianceResult;
}) {
  const { company, company_inputs, score, recommendations, pipeline } = result;

  // Group recommendations by priority
  const grouped = groupByPriority(recommendations);

  return (
    <div className="animate-results space-y-12">
      {/* ----- Company Header ----- */}
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

          {/* Company Details Badge */}
          <div className="flex items-center gap-3 rounded-card border border-slate-200 bg-white px-4 py-2.5">
            <div className="text-right">
              <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">
                {score.size_category.replace(/_/g, " ")}
              </p>
              <p className="mt-0.5 font-mono text-[11px] text-muted">
                {company_inputs.number_of_employees.toLocaleString()} employees
                &middot; {formatEUR(company_inputs.revenue_eur)} revenue
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ----- Compliance Score ----- */}
      <section className="reveal reveal-1">
        <ScoreCard score={score} />
      </section>

      {/* ----- Recommendations ----- */}
      <section className="reveal reveal-2 space-y-4">
        <div className="flex items-baseline justify-between">
          <SectionHeading>Recommendations</SectionHeading>
          <span className="font-mono text-xs text-muted">
            {recommendations.length} total
          </span>
        </div>

        {/* Priority summary */}
        <div className="grid grid-cols-4 gap-2">
          {(["critical", "high", "moderate", "low"] as Priority[]).map((p) => {
            const count = grouped[p]?.length ?? 0;
            const tier = priorityTierStyle(p);
            return (
              <div key={p} className={`rounded-lg border px-3 py-2 text-center ${tier.border} ${tier.bg}`}>
                <p className={`font-mono text-lg font-bold ${tier.text}`}>{count}</p>
                <p className={`text-[10px] font-semibold uppercase tracking-wider ${tier.text}`}>{tier.label}</p>
              </div>
            );
          })}
        </div>

        {/* Group by category */}
        <div className="space-y-3">
          {groupByCategory(recommendations).map(({ category, recs }) => (
            <CategoryGroup
              key={category}
              category={category}
              recommendations={recs}
              defaultExpanded={recs.some(r => r.priority === "critical" || r.priority === "high")}
            />
          ))}
        </div>
      </section>

      {/* ----- Pipeline Trace ----- */}
      <section className="reveal reveal-4 space-y-4">
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
              const opacity = [1, 0.75, 0.55][i] ?? 0.4;
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
          <p className="mt-3 text-center text-[11px] text-muted">
            3-agent pipeline: Extractor → Scorer → Advisor
          </p>
        </div>
      </section>
    </div>
  );
}

/* ================================================================= */
/* Score Card — Large prominent score display with gauge               */
/* ================================================================= */

function ScoreCard({ score }: { score: ComplianceResult["score"] }) {
  const size = 200;
  const stroke = 12;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - score.overall / 100);
  const color = scoreColor(score.overall);
  const badge = scoreStyle(score.overall);

  return (
    <div className="card overflow-hidden">
      <div className="grid sm:grid-cols-3">
        {/* Gauge */}
        <div className="flex flex-col items-center justify-center border-b border-slate-100 px-6 py-10 sm:col-span-2 sm:border-b-0 sm:border-r">
          <p className="mb-6 text-xs font-semibold uppercase tracking-widest text-muted">
            Sustainability Compliance Score
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
                className="font-display text-6xl leading-none"
                style={{ color }}
              >
                {score.overall}
              </span>
              <span className="mt-1 font-mono text-sm text-muted">/ 100</span>
            </div>
          </div>
          <span
            className={`mt-5 inline-block rounded-full border px-3 py-1 text-xs font-bold uppercase tracking-wider ${badge.bg} ${badge.text}`}
          >
            {badge.label}
          </span>
        </div>

        {/* KPI Panel */}
        <div className="flex flex-col justify-center gap-5 p-6">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">
              Applicable Standards
            </p>
            <p className="mt-1 font-mono text-2xl font-bold text-slate-700">
              {score.applicable_standards_count}
            </p>
          </div>
          <div className="space-y-2">
            <ScoreBreakdownBar
              label="Disclosed"
              count={score.disclosed_count}
              total={score.applicable_standards_count}
              color="bg-emerald-500"
            />
            <ScoreBreakdownBar
              label="Partial"
              count={score.partial_count}
              total={score.applicable_standards_count}
              color="bg-amber-400"
            />
            <ScoreBreakdownBar
              label="Missing"
              count={score.missing_count}
              total={score.applicable_standards_count}
              color="bg-red-400"
            />
          </div>
          <p className="text-[11px] leading-relaxed text-muted">
            {score.disclosed_count} of {score.applicable_standards_count}{" "}
            applicable standards fully addressed
          </p>
        </div>
      </div>
    </div>
  );
}

/* ================================================================= */
/* Score Breakdown Bar                                                  */
/* ================================================================= */

function ScoreBreakdownBar({
  label,
  count,
  total,
  color,
}: {
  label: string;
  count: number;
  total: number;
  color: string;
}) {
  const pct = total > 0 ? (count / total) * 100 : 0;
  return (
    <div className="flex items-center gap-2">
      <span className="w-16 text-[10px] font-medium uppercase tracking-wider text-slate-500">
        {label}
      </span>
      <div className="flex-1">
        <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
          <div
            className={`h-full rounded-full ${color} score-bar`}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>
      <span className="w-6 text-right font-mono text-[11px] font-semibold text-slate-600">
        {count}
      </span>
    </div>
  );
}

/* ================================================================= */
/* Category Group — Collapsible group by topic category                */
/* ================================================================= */

const CATEGORY_ICONS: Record<string, string> = {
  "Climate & Energy": "M12 3v2.25m6.364.386l-1.591 1.591M21 12h-2.25m-.386 6.364l-1.591-1.591M12 18.75V21m-4.773-4.227l-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0z",
  "Pollution & Resources": "M12 3c2.755 0 5.455.232 8.083.678.533.09.917.556.917 1.096v1.044a2.25 2.25 0 01-.659 1.591l-5.432 5.432a2.25 2.25 0 00-.659 1.591v2.927a2.25 2.25 0 01-1.244 2.013L9.75 21v-6.568a2.25 2.25 0 00-.659-1.591L3.659 7.409A2.25 2.25 0 013 5.818V4.774c0-.54.384-1.006.917-1.096A48.32 48.32 0 0112 3z",
  "Biodiversity & Ecosystems": "M12.75 3.03v.568c0 .334.148.65.405.864l1.068.89c.442.369.535 1.01.216 1.49l-.51.766a2.25 2.25 0 01-1.161.886l-.143.048a1.107 1.107 0 00-.57 1.664c.369.555.169 1.307-.427 1.605L9 13.125l.423 1.059a.956.956 0 01-1.652.928l-.679-.906a1.125 1.125 0 00-1.906.172L4.5 15.75l-.612.153M12.75 3.031a9 9 0 00-8.862 12.872M12.75 3.031a9 9 0 016.69 14.036m0 0l-.177-.529A2.25 2.25 0 0017.128 15H16.5l-.324-.324a1.453 1.453 0 00-2.328.377l-.036.073a1.586 1.586 0 01-.982.816l-.99.282c-.55.157-.894.702-.8 1.267l.073.438c.081.486-.18.96-.643 1.137A8.97 8.97 0 019 21.75",
  "Workforce & Social": "M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z",
  "Communities & Consumers": "M18 18.72a9.094 9.094 0 003.741-.479 3 3 0 00-4.682-2.72m.94 3.198l.001.031c0 .225-.012.447-.037.666A11.944 11.944 0 0112 21c-2.17 0-4.207-.576-5.963-1.584A6.062 6.062 0 016 18.719m12 0a5.971 5.971 0 00-.941-3.197m0 0A5.995 5.995 0 0012 12.75a5.995 5.995 0 00-5.058 2.772m0 0a3 3 0 00-4.681 2.72 8.986 8.986 0 003.74.477m.94-3.197a5.971 5.971 0 00-.94 3.197M15 6.75a3 3 0 11-6 0 3 3 0 016 0zm6 3a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0zm-13.5 0a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0z",
  "Governance": "M12 21v-8.25M15.75 21v-8.25M8.25 21v-8.25M3 9l9-6 9 6m-1.5 12V10.332A48.36 48.36 0 0012 9.75c-2.551 0-5.056.2-7.5.582V21M3 21h18M12 6.75h.008v.008H12V6.75z",
  "General Disclosures": "M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z",
};

function CategoryGroup({
  category,
  recommendations,
  defaultExpanded,
}: {
  category: string;
  recommendations: Recommendation[];
  defaultExpanded: boolean;
}) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const iconPath = CATEGORY_ICONS[category] || CATEGORY_ICONS["General Disclosures"];

  // Count priorities within this category
  const criticalCount = recommendations.filter(r => r.priority === "critical").length;
  const highCount = recommendations.filter(r => r.priority === "high").length;

  return (
    <div className="card overflow-hidden border border-slate-200">
      {/* Category Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center justify-between bg-slate-50/80 px-5 py-3.5 text-left transition-colors hover:bg-slate-100/80"
      >
        <div className="flex items-center gap-3">
          <svg className="h-5 w-5 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d={iconPath} />
          </svg>
          <span className="text-sm font-semibold text-slate-800">{category}</span>
          <span className="rounded-full bg-slate-200/80 px-2 py-0.5 font-mono text-[10px] font-bold text-slate-600">
            {recommendations.length}
          </span>
          {criticalCount > 0 && (
            <span className="rounded-full bg-red-100 px-2 py-0.5 font-mono text-[10px] font-bold text-red-600">
              {criticalCount} critical
            </span>
          )}
          {highCount > 0 && (
            <span className="rounded-full bg-amber-100 px-2 py-0.5 font-mono text-[10px] font-bold text-amber-600">
              {highCount} high
            </span>
          )}
        </div>
        <svg
          className={`h-4 w-4 text-slate-400 transition-transform ${expanded ? "rotate-180" : ""}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2.5}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {/* Recommendation Cards */}
      {expanded && (
        <div className="divide-y divide-slate-100">
          {recommendations.map((rec) => (
            <RecommendationCard key={rec.id} recommendation={rec} />
          ))}
        </div>
      )}
    </div>
  );
}

/* ================================================================= */
/* Recommendation Card                                                 */
/* ================================================================= */

function RecommendationCard({
  recommendation,
}: {
  recommendation: Recommendation;
}) {
  const tier = priorityTierStyle(recommendation.priority);

  return (
    <div className="px-5 py-4 transition-colors hover:bg-slate-50/50">
      <div className="flex items-start gap-3">
        {/* Priority + ESRS Badge */}
        <div className="mt-0.5 flex shrink-0 flex-col items-center gap-1">
          <span className={`rounded px-2 py-0.5 font-mono text-[10px] font-bold uppercase ${tier.bg} ${tier.text} border ${tier.border}`}>
            {recommendation.priority}
          </span>
          <span className="rounded bg-accent/10 px-2 py-0.5 font-mono text-[10px] font-bold text-accent">
            {recommendation.esrs_id}
          </span>
        </div>

        <div className="min-w-0 flex-1">
          {/* Title */}
          <h3 className="font-display text-[15px] font-medium leading-snug text-slate-900">
            {recommendation.title}
          </h3>

          {/* Impact */}
          {recommendation.impact && (
            <p className="mt-1.5 rounded-lg border border-amber-100 bg-amber-50/50 px-3 py-2 text-[13px] leading-relaxed text-amber-800">
              {recommendation.impact}
            </p>
          )}

          {/* Description */}
          <p className="mt-1.5 text-sm leading-relaxed text-muted">
            {recommendation.description}
          </p>

          {/* Regulatory Reference */}
          <div className="mt-2 flex items-center gap-1.5">
            <svg
              className="h-3 w-3 shrink-0 text-slate-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
              />
            </svg>
            <span className="text-[11px] text-slate-500">
              {recommendation.regulatory_reference}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ================================================================= */
/* Utility — Group recommendations by priority                         */
/* ================================================================= */

function groupByPriority(
  recommendations: Recommendation[]
): Record<Priority, Recommendation[]> {
  const groups: Record<Priority, Recommendation[]> = {
    critical: [],
    high: [],
    moderate: [],
    low: [],
  };

  for (const rec of recommendations) {
    groups[rec.priority].push(rec);
  }

  return groups;
}

/* ================================================================= */
/* Utility — Group recommendations by category                         */
/* ================================================================= */

const CATEGORY_ORDER = [
  "Climate & Energy",
  "Governance",
  "General Disclosures",
  "Workforce & Social",
  "Pollution & Resources",
  "Biodiversity & Ecosystems",
  "Communities & Consumers",
  "General",
];

const PRIORITY_SORT: Record<Priority, number> = {
  critical: 0,
  high: 1,
  moderate: 2,
  low: 3,
};

function groupByCategory(
  recommendations: Recommendation[]
): { category: string; recs: Recommendation[] }[] {
  const map = new Map<string, Recommendation[]>();

  for (const rec of recommendations) {
    const cat = rec.category || "General";
    if (!map.has(cat)) map.set(cat, []);
    map.get(cat)!.push(rec);
  }

  // Sort recommendations within each category by priority
  for (const recs of map.values()) {
    recs.sort((a, b) => PRIORITY_SORT[a.priority] - PRIORITY_SORT[b.priority]);
  }

  // Sort categories by predefined order, then alphabetically for unknown
  return Array.from(map.entries())
    .sort(([a], [b]) => {
      const ai = CATEGORY_ORDER.indexOf(a);
      const bi = CATEGORY_ORDER.indexOf(b);
      return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
    })
    .map(([category, recs]) => ({ category, recs }));
}
