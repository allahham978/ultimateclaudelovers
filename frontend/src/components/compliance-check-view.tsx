import type {
  ComplianceCheckResult,
  ComplianceTodo,
  ESRSCoverageItem,
  ExtractedGoal,
} from "@/lib/types";
import { formatDuration, formatEUR, priorityColor } from "@/lib/utils";

/* ================================================================= */
/* EU Flag SVG (12-star ring)                                         */
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
/* Compliance Check View                                              */
/* ================================================================= */

export default function ComplianceCheckView({
  result,
}: {
  result: ComplianceCheckResult;
}) {
  const {
    company,
    extracted_goals,
    esrs_coverage,
    todo_list,
    estimated_compliance_cost,
    pipeline,
  } = result;

  return (
    <div className="animate-results space-y-12">
      {/* ----- Company Header ----- */}
      <section className="reveal">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <div className="flex items-center gap-2.5">
              <EUFlag className="h-5 w-5 shrink-0" />
              <span className="text-[10px] font-bold uppercase tracking-widest text-accent">
                Compliance Check Report
              </span>
            </div>
            <h1 className="mt-2 font-display text-4xl tracking-tight text-slate-900">
              {company.name || "Unknown Company"}
            </h1>
            <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-muted">
              {company.sector && <span>{company.sector}</span>}
              {company.jurisdiction && (
                <>
                  <span className="text-slate-300">|</span>
                  <span>{company.jurisdiction}</span>
                </>
              )}
              {company.fiscal_year && (
                <>
                  <span className="text-slate-300">|</span>
                  <span>FY{company.fiscal_year}</span>
                </>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2 rounded-card border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">
            <svg
              className="h-3.5 w-3.5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4.5c-.77-.833-2.694-.833-3.464 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z"
              />
            </svg>
            <span className="font-medium">
              Based on unstructured text input
            </span>
          </div>
        </div>
      </section>

      {/* ----- Extracted Goals ----- */}
      <section className="reveal reveal-1 space-y-4">
        <SectionHeading>Extracted Sustainability Goals</SectionHeading>
        <div className="grid gap-3 sm:grid-cols-2">
          {extracted_goals.map((goal) => (
            <GoalCard key={goal.id} goal={goal} />
          ))}
        </div>
      </section>

      {/* ----- ESRS Coverage ----- */}
      <section className="reveal reveal-2 space-y-4">
        <SectionHeading>ESRS E1 Coverage Assessment</SectionHeading>
        <div className="card overflow-hidden">
          {/* Table Header */}
          <div className="hidden border-b border-slate-100 bg-slate-50/60 px-5 py-2.5 sm:grid sm:grid-cols-12 sm:gap-3">
            <span className="col-span-1 text-[10px] font-bold uppercase tracking-widest text-slate-400">
              ESRS
            </span>
            <span className="col-span-3 text-[10px] font-bold uppercase tracking-widest text-slate-400">
              Standard
            </span>
            <span className="col-span-2 text-center text-[10px] font-bold uppercase tracking-widest text-slate-400">
              Coverage
            </span>
            <span className="col-span-6 text-[10px] font-bold uppercase tracking-widest text-slate-400">
              Details
            </span>
          </div>

          {/* Rows */}
          {esrs_coverage.map((item) => (
            <CoverageRow key={item.esrs_id} item={item} />
          ))}
        </div>
      </section>

      {/* ----- Compliance To-Do List ----- */}
      <section className="reveal reveal-3 space-y-4">
        <SectionHeading>Compliance To-Do List</SectionHeading>
        <div className="space-y-3">
          {todo_list.map((todo) => (
            <TodoCard key={todo.id} todo={todo} />
          ))}
        </div>
      </section>

      {/* ----- Estimated Compliance Cost ----- */}
      <section className="reveal reveal-4 space-y-4">
        <SectionHeading>Estimated Compliance Cost</SectionHeading>
        <div className="card overflow-hidden">
          {/* Caveat Banner */}
          <div className="border-b border-amber-200 bg-amber-50 px-5 py-3">
            <div className="flex items-start gap-2">
              <svg
                className="mt-0.5 h-4 w-4 shrink-0 text-amber-500"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4.5c-.77-.833-2.694-.833-3.464 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z"
                />
              </svg>
              <p className="text-xs leading-relaxed text-amber-800">
                {estimated_compliance_cost.caveat}
              </p>
            </div>
          </div>

          {/* Cost Range */}
          <div className="p-5">
            <div className="flex items-baseline gap-3">
              <span className="font-mono text-2xl font-bold text-red-600">
                {formatEUR(estimated_compliance_cost.estimated_range_low_eur)}
              </span>
              <span className="text-sm text-muted">&mdash;</span>
              <span className="font-mono text-2xl font-bold text-red-600">
                {formatEUR(estimated_compliance_cost.estimated_range_high_eur)}
              </span>
            </div>
            <p className="mt-2 text-[11px] leading-relaxed text-muted">
              {estimated_compliance_cost.basis}
            </p>
          </div>
        </div>
      </section>

      {/* ----- Pipeline Trace ----- */}
      <section className="reveal reveal-5 space-y-4">
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
              const opacity = [1, 0.65, 0.4][i] ?? 0.4;
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
          <p className="mt-3 text-center text-[10px] text-muted">
            3-agent pipeline (Fetcher skipped &mdash; no structured financial
            data)
          </p>
        </div>
      </section>
    </div>
  );
}

/* ================================================================= */
/* Goal Card                                                          */
/* ================================================================= */

function GoalCard({ goal }: { goal: ExtractedGoal }) {
  const confidencePct = Math.round(goal.confidence * 100);
  const confidenceColor =
    goal.confidence >= 0.7
      ? "text-emerald-600"
      : goal.confidence >= 0.5
        ? "text-amber-600"
        : "text-red-500";

  return (
    <div className="card flex flex-col justify-between p-4">
      <div>
        <div className="flex items-center justify-between">
          {goal.esrs_relevance ? (
            <span className="rounded bg-accent/10 px-1.5 py-0.5 font-mono text-[10px] font-bold text-accent">
              {goal.esrs_relevance}
            </span>
          ) : (
            <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] font-bold text-slate-400">
              General
            </span>
          )}
          <span className={`font-mono text-xs font-medium ${confidenceColor}`}>
            {confidencePct}% conf.
          </span>
        </div>
        <p className="mt-2 text-sm leading-relaxed text-slate-700">
          {goal.description}
        </p>
      </div>
    </div>
  );
}

/* ================================================================= */
/* Coverage Row                                                       */
/* ================================================================= */

function coverageStyle(coverage: ESRSCoverageItem["coverage"]): {
  bg: string;
  text: string;
  label: string;
} {
  switch (coverage) {
    case "covered":
      return {
        bg: "bg-emerald-50 border-emerald-200",
        text: "text-emerald-700",
        label: "Covered",
      };
    case "partial":
      return {
        bg: "bg-amber-50 border-amber-200",
        text: "text-amber-700",
        label: "Partial",
      };
    case "not_covered":
      return {
        bg: "bg-red-50 border-red-200",
        text: "text-red-700",
        label: "Not Covered",
      };
  }
}

function CoverageRow({ item }: { item: ESRSCoverageItem }) {
  const style = coverageStyle(item.coverage);

  return (
    <div className="grid grid-cols-1 gap-2 border-b border-slate-100 px-5 py-3.5 last:border-b-0 sm:grid-cols-12 sm:items-center sm:gap-3">
      {/* ESRS ID */}
      <div className="sm:col-span-1">
        <span className="rounded bg-accent/10 px-1.5 py-0.5 font-mono text-xs font-bold text-accent">
          {item.esrs_id}
        </span>
      </div>

      {/* Standard Name */}
      <div className="sm:col-span-3">
        <p className="text-sm leading-snug text-slate-700">
          {item.standard_name}
        </p>
      </div>

      {/* Coverage */}
      <div className="sm:col-span-2 sm:text-center">
        <span
          className={`inline-block rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${style.bg} ${style.text}`}
        >
          {style.label}
        </span>
      </div>

      {/* Details */}
      <div className="sm:col-span-6">
        <p className="text-[11px] leading-snug text-muted">{item.details}</p>
      </div>
    </div>
  );
}

/* ================================================================= */
/* Todo Card                                                          */
/* ================================================================= */

const EFFORT_STYLE: Record<string, { bg: string; text: string }> = {
  low: { bg: "bg-emerald-50", text: "text-emerald-600" },
  medium: { bg: "bg-amber-50", text: "text-amber-600" },
  high: { bg: "bg-red-50", text: "text-red-600" },
};

function TodoCard({ todo }: { todo: ComplianceTodo }) {
  const { bg, text } = priorityColor(todo.priority);
  const effort = EFFORT_STYLE[todo.estimated_effort] ?? EFFORT_STYLE.medium;

  return (
    <div className="card p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <span
            className={`inline-block rounded-full border px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider ${bg} ${text}`}
          >
            {todo.priority}
          </span>
          <span className="rounded bg-accent/10 px-1.5 py-0.5 font-mono text-[10px] font-bold text-accent">
            {todo.esrs_id}
          </span>
        </div>
        <span
          className={`rounded px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${effort.bg} ${effort.text}`}
        >
          {todo.estimated_effort} effort
        </span>
      </div>
      <h3 className="mt-3 font-display text-base text-slate-900">
        {todo.title}
      </h3>
      <p className="mt-1.5 text-sm leading-relaxed text-muted">
        {todo.description}
      </p>
      <div className="mt-3 border-t border-slate-100 pt-2.5">
        <span className="font-mono text-[10px] text-slate-400">
          {todo.regulatory_reference}
        </span>
      </div>
    </div>
  );
}
