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

        <div className="space-y-3">
          {(["critical", "high", "moderate", "low"] as Priority[]).map(
            (priority) => {
              const recs = grouped[priority];
              if (!recs || recs.length === 0) return null;
              return (
                <RecommendationTier
                  key={priority}
                  priority={priority}
                  recommendations={recs}
                  defaultExpanded={
                    priority === "critical" || priority === "high"
                  }
                />
              );
            }
          )}
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
/* Recommendation Tier — Collapsible group by priority                 */
/* ================================================================= */

function RecommendationTier({
  priority,
  recommendations,
  defaultExpanded,
}: {
  priority: Priority;
  recommendations: Recommendation[];
  defaultExpanded: boolean;
}) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const tier = priorityTierStyle(priority);

  return (
    <div className={`card overflow-hidden border ${tier.border}`}>
      {/* Tier Header — clickable toggle */}
      <button
        onClick={() => setExpanded(!expanded)}
        className={`flex w-full items-center justify-between px-5 py-3 text-left transition-colors hover:brightness-95 ${tier.bg}`}
      >
        <div className="flex items-center gap-2.5">
          <span className={`h-2.5 w-2.5 rounded-full ${tier.dot}`} />
          <span className={`text-sm font-semibold ${tier.text}`}>
            {tier.label}
          </span>
          <span
            className={`rounded-full border px-2 py-0.5 font-mono text-[10px] font-bold ${tier.border} ${tier.text}`}
          >
            {recommendations.length}
          </span>
        </div>
        <svg
          className={`h-4 w-4 transition-transform ${tier.text} ${
            expanded ? "rotate-180" : ""
          }`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2.5}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M19 9l-7 7-7-7"
          />
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
  return (
    <div className="px-5 py-4 transition-colors hover:bg-slate-50/50">
      <div className="flex items-start gap-3">
        {/* ESRS Badge */}
        <span className="mt-0.5 shrink-0 rounded bg-accent/10 px-2 py-0.5 font-mono text-[11px] font-bold text-accent">
          {recommendation.esrs_id}
        </span>

        <div className="min-w-0 flex-1">
          {/* Title */}
          <h3 className="font-display text-[15px] font-medium leading-snug text-slate-900">
            {recommendation.title}
          </h3>

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
            <span className="font-mono text-[11px] text-slate-500">
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
