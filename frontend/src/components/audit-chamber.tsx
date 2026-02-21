"use client";

import {
  useState,
  useEffect,
  useRef,
  useCallback,
  type DragEvent,
} from "react";
import { useAuditStream } from "@/hooks/useAuditStream";
import type { AgentName } from "@/lib/types";
import ResultsView from "@/components/results-view";
import ComplianceCheckView from "@/components/compliance-check-view";

/* ================================================================= */
/* Constants                                                          */
/* ================================================================= */

const AGENT_COLORS: Record<AgentName, string> = {
  extractor: "text-cyan-400",
  fetcher: "text-amber-400",
  auditor: "text-violet-400",
  consultant: "text-emerald-400",
};

const AGENT_BG: Record<AgentName, string> = {
  extractor: "bg-cyan-400/10",
  fetcher: "bg-amber-400/10",
  auditor: "bg-violet-400/10",
  consultant: "bg-emerald-400/10",
};

/* ================================================================= */
/* EU Flag SVG                                                        */
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
/* Orchestrator                                                       */
/* ================================================================= */

export default function AuditChamber() {
  const [entity, setEntity] = useState("");
  const [reportFileName, setReportFileName] = useState<string | null>(null);
  const reportFileRef = useRef<File | null>(null);
  const [mode, setMode] = useState<"full_audit" | "compliance_check">(
    "full_audit"
  );
  const [freeText, setFreeText] = useState("");

  const {
    step,
    logs,
    audit,
    complianceCheck,
    error,
    progress,
    totalLogs,
    startAudit,
    startComplianceCheck,
    skipToComplete,
    reset,
  } = useAuditStream();

  const logEndRef = useRef<HTMLDivElement>(null);

  /* ---- auto-scroll logs ---- */
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  /* ---- handlers ---- */
  const handleRun = () => {
    if (!canRun) return;
    if (mode === "full_audit") {
      startAudit(entity, reportFileRef.current);
    } else {
      startComplianceCheck(entity, freeText);
    }
  };

  const setReportFile = useCallback((name: string, file: File) => {
    setReportFileName(name);
    reportFileRef.current = file;
  }, []);

  const canRun =
    entity.trim().length > 0 &&
    (mode === "full_audit"
      ? reportFileName !== null
      : freeText.trim().length > 0);

  /* ================================================================= */
  /* Render: Complete                                                   */
  /* ================================================================= */

  if (step === "complete") {
    if (complianceCheck) {
      return <ComplianceCheckView result={complianceCheck} />;
    }
    if (audit) {
      return <ResultsView audit={audit} />;
    }
    return (
      <div className="flex min-h-[calc(100vh-8rem)] items-center justify-center">
        <div className="text-center">
          <p className="text-sm text-muted">No data available.</p>
          <button
            onClick={reset}
            className="mt-4 rounded-card bg-accent px-5 py-2 text-sm font-semibold text-white hover:bg-indigo-700"
          >
            Start Over
          </button>
        </div>
      </div>
    );
  }

  /* ================================================================= */
  /* Render: Analyzing                                                  */
  /* ================================================================= */

  if (step === "analyzing") {
    const label =
      mode === "compliance_check"
        ? "Compliance Check"
        : "CSRD Compliance Audit";

    return (
      <div className="flex min-h-[calc(100vh-8rem)] items-center justify-center">
        <div className="animate-fade-in w-full max-w-2xl">
          <div className="card overflow-hidden">
            {/* Progress bar */}
            <div className="h-1 w-full bg-slate-100">
              <div
                className="h-full bg-accent transition-all duration-500 ease-out"
                style={{ width: `${Math.min(progress, 1) * 100}%` }}
              />
            </div>

            {/* Header — click to skip */}
            <button
              onClick={() => skipToComplete()}
              className="flex w-full items-center justify-between border-b border-slate-100 px-5 py-3 text-left transition-colors hover:bg-slate-50"
            >
              <div className="flex items-center gap-2.5">
                <div className="h-2 w-2 animate-pulse rounded-full bg-accent" />
                <span className="text-sm font-medium text-slate-700">
                  {label}{" "}
                  <span className="font-mono font-semibold text-accent">
                    {entity.toUpperCase() || "ENTITY"}
                  </span>
                </span>
              </div>
              <span className="font-mono text-xs text-muted">
                {totalLogs > 0
                  ? `${logs.length}/${totalLogs}`
                  : `${logs.length}`}{" "}
                &middot; skip
              </span>
            </button>

            {/* Terminal */}
            <div className="bg-slate-900 p-5">
              <div className="h-80 overflow-y-auto pr-2 scrollbar-thin">
                {logs.map((log, i) => (
                  <div key={i} className="mb-1.5 flex gap-2 animate-log-line">
                    <span
                      className={`inline-flex shrink-0 items-center rounded px-1.5 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider ${AGENT_COLORS[log.agent]} ${AGENT_BG[log.agent]}`}
                    >
                      {log.agent}
                    </span>
                    <span className="font-mono text-xs leading-relaxed text-slate-400">
                      {log.message}
                    </span>
                  </div>
                ))}

                {progress < 1 && (
                  <div className="mt-1 flex items-center gap-2">
                    <span className="inline-block h-3.5 w-1.5 animate-blink bg-accent/70" />
                  </div>
                )}
                <div ref={logEndRef} />
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  /* ================================================================= */
  /* Render: Idle — Document Vault                                     */
  /* ================================================================= */

  return (
    <div className="flex min-h-[calc(100vh-8rem)] items-center justify-center">
      <div className="animate-fade-in w-full max-w-3xl">
        {/* Headline */}
        <div className="mb-8 text-center">
          <div className="mb-3 flex items-center justify-center gap-2">
            <EUFlag className="h-5 w-5" />
            <span className="text-[10px] font-bold uppercase tracking-widest text-accent">
              EU Directive 2022/2464
            </span>
          </div>
          <h1 className="font-display text-3xl tracking-tight text-slate-900 sm:text-4xl">
            CSRD Compliance Engine
          </h1>
          <p className="mt-2 text-sm text-muted">
            {mode === "full_audit"
              ? "Upload a pre-parsed Annual Management Report (JSON) to audit EU Taxonomy alignment against ESRS disclosures."
              : "Describe your current sustainability situation to receive a prioritized CSRD compliance to-do list."}
          </p>
        </div>

        {/* Error display */}
        {error && (
          <div className="mb-4 rounded-card border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {/* Chamber Card */}
        <div className="card overflow-hidden">
          {/* Mode Toggle */}
          <div className="flex items-center justify-center gap-1 border-b border-slate-100 px-5 py-3">
            <button
              onClick={() => setMode("full_audit")}
              className={`rounded-full px-4 py-1.5 text-xs font-semibold transition-all ${
                mode === "full_audit"
                  ? "bg-accent text-white"
                  : "bg-slate-100 text-slate-500 hover:bg-slate-200"
              }`}
            >
              Full Audit
            </button>
            <button
              onClick={() => setMode("compliance_check")}
              className={`rounded-full px-4 py-1.5 text-xs font-semibold transition-all ${
                mode === "compliance_check"
                  ? "bg-accent text-white"
                  : "bg-slate-100 text-slate-500 hover:bg-slate-200"
              }`}
            >
              Compliance Check
            </button>
          </div>

          {/* Entity Search + Run Button */}
          <div className="flex items-center gap-3 border-b border-slate-100 p-5">
            <label
              htmlFor="entity-input"
              className="shrink-0 text-xs font-medium uppercase tracking-widest text-muted"
            >
              Entity
            </label>
            <input
              id="entity-input"
              type="text"
              value={entity}
              onChange={(e) => setEntity(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleRun()}
              placeholder="LEI or company name"
              className="h-9 flex-1 rounded-card border border-slate-200 bg-slate-50 px-3 font-mono text-sm text-slate-800 placeholder:text-slate-400 transition-colors focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20"
            />
            <button
              onClick={handleRun}
              disabled={!canRun}
              className={`
                h-9 shrink-0 rounded-card px-5 text-sm font-semibold transition-all focus:outline-none focus:ring-2 focus:ring-accent/30 focus:ring-offset-2
                ${
                  canRun
                    ? "bg-accent text-white hover:bg-indigo-700"
                    : "border border-slate-200 bg-white text-slate-400 cursor-not-allowed"
                }
              `}
            >
              {mode === "full_audit"
                ? "Run Engine Audit"
                : "Run Compliance Check"}
            </button>
          </div>

          {/* Content Area — conditional on mode */}
          <div className="p-5">
            {mode === "full_audit" ? (
              <>
                <div className="mb-3 flex items-center justify-between">
                  <p className="text-xs font-medium uppercase tracking-widest text-muted">
                    Document Vault
                  </p>
                  <p className="text-xs text-muted">
                    <span className="font-mono font-semibold text-slate-700">
                      {reportFileName ? "1" : "0"}
                    </span>
                    /1 uploaded
                  </p>
                </div>
                <ReportUploadCard
                  fileName={reportFileName}
                  onFile={setReportFile}
                />
              </>
            ) : (
              <>
                <div className="mb-3">
                  <p className="text-xs font-medium uppercase tracking-widest text-muted">
                    Sustainability Description
                  </p>
                </div>
                <textarea
                  value={freeText}
                  onChange={(e) => setFreeText(e.target.value)}
                  placeholder="Paste or describe your current sustainability situation, goals, emissions data, energy consumption, transition plans — whatever information you have available..."
                  rows={8}
                  className="w-full rounded-card border border-slate-200 bg-slate-50 px-4 py-3 font-mono text-sm text-slate-800 placeholder:text-slate-400 transition-colors focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20"
                />
                <p className="mt-2 text-[11px] text-muted">
                  The more detail you provide, the more accurate the compliance
                  assessment will be. Include any emissions figures, energy data,
                  targets, and transition plans you have.
                </p>
              </>
            )}
          </div>
        </div>

        {/* Dev shortcut */}
        <button
          onClick={() => skipToComplete(mode)}
          className="mt-6 w-full text-center text-xs text-slate-400 transition-colors hover:text-accent"
        >
          Skip to results
        </button>
      </div>
    </div>
  );
}

/* ================================================================= */
/* Report Upload Card                                                  */
/* ================================================================= */

function ReportUploadCard({
  fileName,
  onFile,
}: {
  fileName: string | null;
  onFile: (name: string, file: File) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const handleDrop = useCallback(
    (e: DragEvent) => {
      e.preventDefault();
      setDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) {
        onFile(file.name, file);
      }
    },
    [onFile]
  );

  const handleSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) onFile(file.name, file);
    },
    [onFile]
  );

  const isFilled = fileName !== null;

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      onClick={() => inputRef.current?.click()}
      className={`
        flex cursor-pointer flex-col justify-between rounded-card p-6 transition-all
        ${
          dragging
            ? "border-2 border-accent bg-indigo-50/40"
            : isFilled
              ? "border border-slate-200 bg-white shadow-card"
              : "border-2 border-dashed border-slate-200 bg-white hover:border-slate-300"
        }
      `}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".json,.xhtml"
        onChange={handleSelect}
        className="hidden"
      />

      {/* Number */}
      <span className="font-mono text-[10px] font-semibold text-slate-300">
        01
      </span>

      {/* Title */}
      <p className="mt-3 text-sm font-medium leading-snug text-slate-800">
        Annual Management Report
      </p>

      {/* Subtitle or file feedback */}
      {isFilled ? (
        <div className="mt-3">
          <p className="truncate font-mono text-xs text-slate-600">
            {fileName}
          </p>
          <p className="mt-1 text-[11px] font-semibold text-accent">
            File Ready
          </p>
        </div>
      ) : (
        <p className="mt-3 text-xs leading-relaxed text-muted">
          Pre-parsed XHTML/iXBRL management report (JSON format). Contains ESRS
          sustainability statement, EU Taxonomy table, and audited financials.
        </p>
      )}
    </div>
  );
}
