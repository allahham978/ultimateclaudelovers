"use client";

import {
  useState,
  useEffect,
  useRef,
  useCallback,
  type DragEvent,
} from "react";
import { useAuditStream } from "@/hooks/useAuditStream";
import type { AgentName, CompanyInputs } from "@/lib/types";
import ComplianceResultView from "@/components/compliance-result-view";

/* ================================================================= */
/* Constants                                                           */
/* ================================================================= */

const AGENT_COLORS: Record<AgentName, string> = {
  extractor: "text-cyan-400",
  scorer: "text-blue-400",
  advisor: "text-emerald-400",
};

const AGENT_BG: Record<AgentName, string> = {
  extractor: "bg-cyan-400/10",
  scorer: "bg-blue-400/10",
  advisor: "bg-emerald-400/10",
};

const CURRENT_YEAR = new Date().getFullYear();

/* ================================================================= */
/* EU Flag SVG                                                         */
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
/* Upload Cloud Icon                                                   */
/* ================================================================= */

function UploadCloudIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242" />
      <path d="M12 12v8" />
      <path d="m16 16-4-4-4 4" />
    </svg>
  );
}

/* ================================================================= */
/* Orchestrator                                                        */
/* ================================================================= */

export default function AuditChamber() {
  const [entity, setEntity] = useState("");
  const [reportFileName, setReportFileName] = useState<string | null>(null);
  const reportFileRef = useRef<File | null>(null);
  const [mode, setMode] = useState<"structured_document" | "free_text">(
    "structured_document"
  );
  const [freeText, setFreeText] = useState("");

  // Company inputs state
  const [employees, setEmployees] = useState("");
  const [revenue, setRevenue] = useState("");
  const [assets, setAssets] = useState("");
  const [reportingYear, setReportingYear] = useState(String(CURRENT_YEAR));

  const {
    step,
    logs,
    result,
    error,
    progress,
    totalLogs,
    startAnalysis,
    skipToComplete,
    reset,
  } = useAuditStream();

  const logEndRef = useRef<HTMLDivElement>(null);

  /* ---- auto-scroll logs ---- */
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  /* ---- build CompanyInputs from form state ---- */
  const buildCompanyInputs = (): CompanyInputs | null => {
    const emp = parseInt(employees, 10);
    const rev = parseFloat(revenue);
    const ast = parseFloat(assets);
    const yr = parseInt(reportingYear, 10);

    if (isNaN(emp) || isNaN(rev) || isNaN(ast) || isNaN(yr)) return null;
    if (emp <= 0 || rev <= 0 || ast <= 0 || yr < 2020) return null;

    return {
      number_of_employees: emp,
      revenue_eur: rev,
      total_assets_eur: ast,
      reporting_year: yr,
    };
  };

  const companyInputsValid = buildCompanyInputs() !== null;

  /* ---- handlers ---- */
  const handleRun = () => {
    if (!canRun) return;
    const companyInputs = buildCompanyInputs();
    if (!companyInputs) return;

    startAnalysis(
      entity,
      mode,
      companyInputs,
      mode === "structured_document" ? reportFileRef.current : null,
      mode === "free_text" ? freeText : undefined
    );
  };

  const setReportFile = useCallback((name: string, file: File) => {
    setReportFileName(name);
    reportFileRef.current = file;
  }, []);

  const canRun =
    entity.trim().length > 0 &&
    companyInputsValid &&
    (mode === "structured_document"
      ? reportFileName !== null
      : freeText.trim().length > 0);

  /* ================================================================= */
  /* Render: Complete                                                   */
  /* ================================================================= */

  if (step === "complete") {
    if (result) {
      return <ComplianceResultView result={result} />;
    }
    return (
      <div className="flex min-h-[calc(100vh-10rem)] items-center justify-center">
        <div className="text-center">
          <p className="text-sm text-stone-400">No data available.</p>
          <button
            onClick={reset}
            className="mt-4 rounded-full bg-accent px-6 py-2.5 text-sm font-semibold text-white hover:bg-blue-600"
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
    return (
      <div className="flex min-h-[calc(100vh-10rem)] items-center justify-center">
        <div className="animate-fade-in w-full max-w-2xl">
          <div className="card overflow-hidden">
            {/* Progress bar */}
            <div className="h-0.5 w-full bg-stone-100">
              <div
                className="h-full bg-accent transition-all duration-500 ease-out"
                style={{ width: `${Math.min(progress, 1) * 100}%` }}
              />
            </div>

            {/* Header — click to skip */}
            <button
              onClick={() => skipToComplete()}
              className="flex w-full items-center justify-between border-b border-stone-100 px-6 py-4 text-left transition-colors hover:bg-stone-50/50"
            >
              <div className="flex items-center gap-3">
                <div className="h-2 w-2 animate-pulse rounded-full bg-accent" />
                <span className="text-sm font-medium text-stone-600">
                  Compliance Analysis{" "}
                  <span className="font-mono font-semibold text-accent">
                    {entity.toUpperCase() || "ENTITY"}
                  </span>
                </span>
              </div>
              <span className="font-mono text-xs text-stone-400">
                {totalLogs > 0
                  ? `${logs.length}/${totalLogs}`
                  : `${logs.length}`}{" "}
                &middot; skip
              </span>
            </button>

            {/* Terminal */}
            <div className="bg-stone-900 p-6">
              <div className="h-80 overflow-y-auto pr-2 scrollbar-thin">
                {logs.map((log, i) => (
                  <div key={i} className="mb-1.5 flex gap-2 animate-log-line">
                    <span
                      className={`inline-flex shrink-0 items-center rounded px-1.5 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider ${AGENT_COLORS[log.agent]} ${AGENT_BG[log.agent]}`}
                    >
                      {log.agent}
                    </span>
                    <span className="font-mono text-xs leading-relaxed text-stone-400">
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
  /* Render: Idle — Input Form                                          */
  /* ================================================================= */

  return (
    <div className="flex min-h-[calc(100vh-10rem)] flex-col items-center justify-center">
      <div className="animate-fade-in w-full max-w-[700px]">
        {/* ---- Hero Section ---- */}
        <div className="mb-16 text-center">
          <div className="mb-4 flex items-center justify-center gap-2">
            <EUFlag className="h-4 w-4" />
            <span className="text-[10px] font-semibold uppercase tracking-[0.2em] text-stone-400">
              EU Directive 2022/2464
            </span>
          </div>
          <h1 className="text-[2.5rem] font-medium leading-tight tracking-[-0.02em] text-stone-800">
            ESGateway
          </h1>
          <p className="mx-auto mt-4 max-w-md text-[15px] font-light leading-relaxed text-stone-400">
            {mode === "structured_document"
              ? "Upload your management report and company details to receive a compliance score with prioritized recommendations."
              : "Describe your sustainability situation and company details to receive a compliance score with prioritized recommendations."}
          </p>
        </div>

        {/* ---- Error display ---- */}
        {error && (
          <div className="mb-6 rounded-2xl border border-red-200/60 bg-red-50/50 px-5 py-4 text-sm text-red-600/80">
            {error}
          </div>
        )}

        {/* ---- Chamber Card ---- */}
        <div className="card overflow-hidden">
          {/* Pill Toggle */}
          <div className="flex justify-center px-8 pt-8 pb-2">
            <div className="relative rounded-full bg-stone-100/80 p-1">
              <div className="relative grid grid-cols-2">
                {/* Sliding indicator */}
                <div
                  className="absolute inset-y-0 w-1/2 rounded-full bg-white transition-transform duration-300 ease-[cubic-bezier(0.4,0,0.2,1)]"
                  style={{
                    transform: `translateX(${mode === "structured_document" ? "0%" : "100%"})`,
                    boxShadow: "0 1px 3px rgb(0 0 0 / 0.08)",
                  }}
                />
                <button
                  onClick={() => setMode("structured_document")}
                  className={`relative z-10 rounded-full px-6 py-2.5 text-[13px] font-medium transition-colors duration-200 ${
                    mode === "structured_document"
                      ? "text-stone-800"
                      : "text-stone-400"
                  }`}
                >
                  Structured Document
                </button>
                <button
                  onClick={() => setMode("free_text")}
                  className={`relative z-10 rounded-full px-6 py-2.5 text-[13px] font-medium transition-colors duration-200 ${
                    mode === "free_text"
                      ? "text-stone-800"
                      : "text-stone-400"
                  }`}
                >
                  Free Text
                </button>
              </div>
            </div>
          </div>

          {/* Form Content */}
          <div className="px-8 pb-8 pt-6">
            {/* Entity Input */}
            <div className="mb-8">
              <label
                htmlFor="entity-input"
                className="mb-2 block text-[11px] font-medium uppercase tracking-[0.12em] text-stone-400"
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
                className="h-11 w-full rounded-xl border-0 bg-stone-50 px-4 text-sm text-stone-700 placeholder:text-stone-300 transition-all focus:bg-white focus:outline-none focus:ring-1 focus:ring-accent/25"
              />
            </div>

            {/* Company Details */}
            <div className="mb-8">
              <label className="mb-3 block text-[11px] font-medium uppercase tracking-[0.12em] text-stone-400">
                Company Details
              </label>
              <div className="grid grid-cols-2 gap-4">
                <CompanyInput
                  id="employees"
                  label="Employees"
                  value={employees}
                  onChange={setEmployees}
                  placeholder="500"
                  type="number"
                />
                <CompanyInput
                  id="revenue"
                  label="Revenue (EUR)"
                  value={revenue}
                  onChange={setRevenue}
                  placeholder="85000000"
                  type="number"
                />
                <CompanyInput
                  id="assets"
                  label="Total Assets (EUR)"
                  value={assets}
                  onChange={setAssets}
                  placeholder="42000000"
                  type="number"
                />
                <CompanyInput
                  id="reporting-year"
                  label="Reporting Year"
                  value={reportingYear}
                  onChange={setReportingYear}
                  placeholder="2025"
                  type="number"
                />
              </div>
            </div>

            {/* Subtle Separator */}
            <div className="mb-8 border-t border-stone-100/80" />

            {/* Content Area — conditional on mode */}
            <div className="mb-10">
              {mode === "structured_document" ? (
                <>
                  <div className="mb-3 flex items-center justify-between">
                    <label className="text-[11px] font-medium uppercase tracking-[0.12em] text-stone-400">
                      Document Vault
                    </label>
                    <span className="text-[11px] text-stone-300">
                      <span className="font-mono font-semibold text-stone-500">
                        {reportFileName ? "1" : "0"}
                      </span>
                      /1
                    </span>
                  </div>
                  <ReportUploadCard
                    fileName={reportFileName}
                    onFile={setReportFile}
                  />
                </>
              ) : (
                <>
                  <label className="mb-3 block text-[11px] font-medium uppercase tracking-[0.12em] text-stone-400">
                    Sustainability Description
                  </label>
                  <textarea
                    value={freeText}
                    onChange={(e) => setFreeText(e.target.value)}
                    placeholder="Describe your current sustainability situation, goals, emissions data, energy consumption, transition plans..."
                    rows={6}
                    className="w-full resize-none rounded-xl border-0 bg-stone-50 px-4 py-3 text-sm text-stone-700 placeholder:text-stone-300 transition-all focus:bg-white focus:outline-none focus:ring-1 focus:ring-accent/25"
                  />
                  <p className="mt-2 text-[11px] text-stone-300">
                    The more detail you provide, the more accurate the
                    assessment will be.
                  </p>
                </>
              )}
            </div>

            {/* CTA */}
            <button
              onClick={handleRun}
              disabled={!canRun}
              className={`
                h-12 w-full rounded-full text-[15px] font-semibold transition-all duration-200
                focus:outline-none focus:ring-2 focus:ring-accent/30 focus:ring-offset-2
                ${
                  canRun
                    ? "bg-accent text-white hover:bg-blue-600 hover:shadow-lg hover:shadow-accent/20"
                    : "bg-stone-100 text-stone-300 cursor-not-allowed"
                }
              `}
            >
              Run Analysis
            </button>
          </div>
        </div>

        {/* Dev shortcut */}
        <button
          onClick={() => skipToComplete(mode)}
          className="mt-8 w-full text-center text-xs text-stone-300 transition-colors hover:text-accent"
        >
          Skip to results
        </button>
      </div>
    </div>
  );
}

/* ================================================================= */
/* Company Input Field                                                 */
/* ================================================================= */

function CompanyInput({
  id,
  label,
  value,
  onChange,
  placeholder,
  type = "text",
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  type?: string;
}) {
  return (
    <div>
      <label
        htmlFor={id}
        className="mb-1.5 block text-[11px] font-medium text-stone-400"
      >
        {label}
      </label>
      <input
        id={id}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="h-10 w-full rounded-xl border-0 bg-stone-50 px-4 font-mono text-sm text-stone-700 placeholder:text-stone-300 transition-all focus:bg-white focus:outline-none focus:ring-1 focus:ring-accent/25"
      />
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
        group flex cursor-pointer flex-col items-center justify-center rounded-2xl p-8 text-center transition-all duration-200
        ${
          dragging
            ? "border-2 border-accent bg-blue-50/30 scale-[1.01]"
            : isFilled
              ? "border border-stone-200/80 bg-stone-50/50"
              : "border border-stone-200/60 bg-stone-50/30 hover:bg-stone-50 hover:border-stone-200"
        }
      `}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".json,.xhtml"
        onChange={handleSelect}
        onClick={(e) => e.stopPropagation()}
        className="sr-only"
      />

      {isFilled ? (
        <>
          <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-emerald-50">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              className="h-5 w-5 text-emerald-500"
            >
              <path d="M20 6L9 17l-5-5" />
            </svg>
          </div>
          <p className="max-w-[280px] truncate text-sm font-medium text-stone-600">
            {fileName}
          </p>
          <p className="mt-1 text-xs font-medium text-emerald-600">Ready</p>
        </>
      ) : (
        <>
          <div className="mb-3 transition-transform duration-200 group-hover:-translate-y-0.5">
            <UploadCloudIcon className="h-10 w-10 text-stone-300" />
          </div>
          <p className="text-sm font-medium text-stone-500">
            Annual Management Report
          </p>
          <p className="mt-1 text-xs text-stone-300">
            Drop file here or click to browse
          </p>
          <p className="mt-3 text-[10px] font-medium uppercase tracking-wider text-stone-300">
            .json &nbsp; .xhtml
          </p>
        </>
      )}
    </div>
  );
}
