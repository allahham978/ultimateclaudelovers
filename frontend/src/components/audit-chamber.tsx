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
  /* Render: Idle — Cinematic Single-Column                             */
  /* ================================================================= */

  return (
    <IdleView
      mode={mode}
      setMode={setMode}
      entity={entity}
      setEntity={setEntity}
      employees={employees}
      setEmployees={setEmployees}
      revenue={revenue}
      setRevenue={setRevenue}
      assets={assets}
      setAssets={setAssets}
      reportingYear={reportingYear}
      setReportingYear={setReportingYear}
      freeText={freeText}
      setFreeText={setFreeText}
      reportFileName={reportFileName}
      setReportFile={setReportFile}
      canRun={canRun}
      handleRun={handleRun}
      skipToComplete={skipToComplete}
      error={error}
    />
  );
}

/* ================================================================= */
/* Idle View — Cinematic single-column hero + scroll-reveal form       */
/* ================================================================= */

function IdleView({
  mode,
  setMode,
  entity,
  setEntity,
  employees,
  setEmployees,
  revenue,
  setRevenue,
  assets,
  setAssets,
  reportingYear,
  setReportingYear,
  freeText,
  setFreeText,
  reportFileName,
  setReportFile,
  canRun,
  handleRun,
  skipToComplete,
  error,
}: {
  mode: "structured_document" | "free_text";
  setMode: (m: "structured_document" | "free_text") => void;
  entity: string;
  setEntity: (v: string) => void;
  employees: string;
  setEmployees: (v: string) => void;
  revenue: string;
  setRevenue: (v: string) => void;
  assets: string;
  setAssets: (v: string) => void;
  reportingYear: string;
  setReportingYear: (v: string) => void;
  freeText: string;
  setFreeText: (v: string) => void;
  reportFileName: string | null;
  setReportFile: (name: string, file: File) => void;
  canRun: boolean;
  handleRun: () => void;
  skipToComplete: (m?: "structured_document" | "free_text") => void;
  error: string | null;
}) {
  /* ---- Scroll-triggered card reveal ---- */
  const cardRef = useRef<HTMLDivElement>(null);
  const [cardVisible, setCardVisible] = useState(false);

  useEffect(() => {
    const el = cardRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setCardVisible(true);
          observer.disconnect();
        }
      },
      { threshold: 0.15 }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return (
    <div className="-mx-8 -mt-12">
      {/* ============================================================ */}
      {/* Section 1: Cinematic Hero Viewport                            */}
      {/* ============================================================ */}
      <section className="flex min-h-[85vh] flex-col items-center justify-center px-8 text-center">
        {/* Badge */}
        <div className="hero-stagger-1 mb-8 inline-flex items-center gap-2.5 rounded-full border border-zinc-200 bg-white/80 px-4 py-1.5">
          <EUFlag className="h-3.5 w-3.5" />
          <span className="text-[11px] font-semibold uppercase tracking-[0.15em] text-zinc-500">
            EU Directive 2022/2464
          </span>
        </div>

        {/* Headline */}
        <h1 className="hero-stagger-2 text-[3.5rem] font-extrabold leading-[1.05] tracking-[-0.04em] text-zinc-900 md:text-[5rem]">
          Seamless ESRS
          <br />
          Reporting
        </h1>

        {/* Subtitle */}
        <p className="hero-stagger-3 mx-auto mt-7 max-w-2xl text-xl leading-relaxed text-zinc-500">
          Upload your management report and company details to receive a
          compliance score with prioritized recommendations.
        </p>
      </section>

      {/* ============================================================ */}
      {/* Section 2: Scroll-Revealed Form Card                          */}
      {/* ============================================================ */}
      <section className="flex justify-center px-8 pb-32">
        <div className="w-full max-w-4xl">
          {/* Error display */}
          {error && (
            <div className="mb-4 rounded-2xl border border-red-200/60 bg-red-50/50 px-5 py-4 text-sm text-red-600/80">
              {error}
            </div>
          )}

          <div
            ref={cardRef}
            className={`card-reveal overflow-hidden rounded-3xl border border-zinc-100 bg-white p-8 shadow-[0_8px_30px_rgb(0,0,0,0.04)] ${
              cardVisible ? "is-visible" : ""
            }`}
          >
            {/* Segmented Control */}
            <div className="mb-8 flex justify-center">
              <div className="relative rounded-xl bg-zinc-100/70 p-1">
                <div className="relative grid grid-cols-2">
                  <div
                    className="absolute inset-y-0 w-1/2 rounded-[10px] bg-white transition-transform duration-300 ease-[cubic-bezier(0.4,0,0.2,1)]"
                    style={{
                      transform: `translateX(${mode === "structured_document" ? "0%" : "100%"})`,
                      boxShadow: "0 1px 3px rgb(0 0 0 / 0.06)",
                    }}
                  />
                  <button
                    onClick={() => setMode("structured_document")}
                    className={`relative z-10 rounded-[10px] px-6 py-2 text-[13px] font-medium transition-colors duration-200 ${
                      mode === "structured_document"
                        ? "text-zinc-900"
                        : "text-zinc-400 hover:text-zinc-500"
                    }`}
                  >
                    Structured Document
                  </button>
                  <button
                    onClick={() => setMode("free_text")}
                    className={`relative z-10 rounded-[10px] px-6 py-2 text-[13px] font-medium transition-colors duration-200 ${
                      mode === "free_text"
                        ? "text-zinc-900"
                        : "text-zinc-400 hover:text-zinc-500"
                    }`}
                  >
                    Free Text
                  </button>
                </div>
              </div>
            </div>

            {/* Entity */}
            <div className="mb-7">
              <label
                htmlFor="entity-input"
                className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.1em] text-zinc-400"
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
                className="h-11 w-full border-b border-zinc-200 bg-transparent px-0 text-[15px] text-zinc-900 placeholder:text-zinc-300 transition-colors focus:border-zinc-900 focus:outline-none"
              />
            </div>

            {/* Company Details */}
            <div className="mb-7">
              <label className="mb-3 block text-[11px] font-semibold uppercase tracking-[0.1em] text-zinc-400">
                Company Details
              </label>
              <div className="grid grid-cols-2 gap-x-8 gap-y-5 md:grid-cols-4">
                <UnderlineInput
                  id="employees"
                  label="Employees"
                  value={employees}
                  onChange={setEmployees}
                  placeholder="e.g., 250"
                  type="number"
                />
                <UnderlineInput
                  id="revenue"
                  label="Revenue (EUR)"
                  value={revenue}
                  onChange={setRevenue}
                  placeholder="e.g., 85M"
                  type="number"
                />
                <UnderlineInput
                  id="assets"
                  label="Total Assets (EUR)"
                  value={assets}
                  onChange={setAssets}
                  placeholder="e.g., 42M"
                  type="number"
                />
                <UnderlineInput
                  id="reporting-year"
                  label="Reporting Year"
                  value={reportingYear}
                  onChange={setReportingYear}
                  placeholder="e.g., 2025"
                  type="number"
                />
              </div>
            </div>

            {/* Separator */}
            <div className="mb-7 border-t border-zinc-100" />

            {/* Content Area */}
            <div className="mb-8">
              {mode === "structured_document" ? (
                <>
                  <div className="mb-3 flex items-center justify-between">
                    <label className="text-[11px] font-semibold uppercase tracking-[0.1em] text-zinc-400">
                      Document Vault
                    </label>
                    <span className="text-[11px] text-zinc-300">
                      <span className="font-mono font-semibold text-zinc-500">
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
                  <label className="mb-3 block text-[11px] font-semibold uppercase tracking-[0.1em] text-zinc-400">
                    Sustainability Description
                  </label>
                  <textarea
                    value={freeText}
                    onChange={(e) => setFreeText(e.target.value)}
                    placeholder="Describe your current sustainability situation, goals, emissions data, energy consumption, transition plans..."
                    rows={5}
                    className="w-full resize-none border-b border-zinc-200 bg-transparent px-0 py-2 text-[15px] text-zinc-900 placeholder:text-zinc-300 transition-colors focus:border-zinc-900 focus:outline-none"
                  />
                  <p className="mt-2 text-[11px] text-zinc-300">
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
                h-14 w-full rounded-xl text-[15px] font-medium transition-all duration-200
                focus:outline-none focus:ring-2 focus:ring-zinc-400 focus:ring-offset-2
                ${
                  canRun
                    ? "bg-zinc-900 text-white hover:bg-zinc-800"
                    : "bg-zinc-100 text-zinc-300 cursor-not-allowed"
                }
              `}
            >
              Analyze Report
            </button>
          </div>

          {/* Dev shortcut */}
          <button
            onClick={() => skipToComplete(mode)}
            className="mt-6 w-full text-center text-[11px] text-zinc-300 transition-colors hover:text-zinc-500"
          >
            Skip to results
          </button>
        </div>
      </section>
    </div>
  );
}

/* ================================================================= */
/* Underline Input Field                                               */
/* ================================================================= */

function UnderlineInput({
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
        className="mb-1 block text-[11px] font-medium text-zinc-400"
      >
        {label}
      </label>
      <input
        id={id}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="h-10 w-full border-b border-zinc-200 bg-transparent px-0 font-mono text-sm text-zinc-900 placeholder:text-zinc-300 placeholder:font-sans transition-colors focus:border-zinc-900 focus:outline-none"
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
            ? "border-2 border-dashed border-zinc-400 bg-zinc-50 scale-[1.01]"
            : isFilled
              ? "border border-zinc-200 bg-zinc-50/50"
              : "border border-dashed border-zinc-200 bg-zinc-50/30 hover:bg-zinc-50/80 hover:border-zinc-300"
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
          <p className="max-w-[280px] truncate text-sm font-medium text-zinc-600">
            {fileName}
          </p>
          <p className="mt-1 text-xs font-medium text-emerald-600">Ready</p>
        </>
      ) : (
        <>
          <div className="mb-3 transition-transform duration-200 group-hover:-translate-y-0.5">
            <UploadCloudIcon className="h-10 w-10 text-zinc-300" />
          </div>
          <p className="text-sm font-medium text-zinc-500">
            Annual Management Report
          </p>
          <p className="mt-1 text-xs text-zinc-300">
            Drop file here or click to browse
          </p>
          <p className="mt-3 text-[10px] font-medium uppercase tracking-wider text-zinc-300">
            .json &nbsp; .xhtml
          </p>
        </>
      )}
    </div>
  );
}
