"use client";

import {
  useState,
  useEffect,
  useRef,
  useCallback,
  type DragEvent,
} from "react";
import { MOCK_AUDIT, AUDIT_LOGS } from "@/lib/mock-data";
import type { AuditLog, AgentName } from "@/lib/types";
import ResultsView from "@/components/results-view";

/* ================================================================= */
/* Constants                                                          */
/* ================================================================= */

type Step = "idle" | "analyzing" | "complete";

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
  const [step, setStep] = useState<Step>("idle");
  const [ticker, setTicker] = useState("");
  const [fileName, setFileName] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [logs, setLogs] = useState<AuditLog[]>([]);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const logEndRef = useRef<HTMLDivElement>(null);

  /* ---- auto-scroll logs ---- */
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  /* ---- log playback timer ---- */
  useEffect(() => {
    if (step !== "analyzing") return;

    const timeouts: NodeJS.Timeout[] = [];

    AUDIT_LOGS.forEach((log) => {
      timeouts.push(
        setTimeout(() => {
          setLogs((prev) => [...prev, log]);
        }, log.timestamp)
      );
    });

    const lastTs = AUDIT_LOGS[AUDIT_LOGS.length - 1].timestamp;
    timeouts.push(setTimeout(() => setStep("complete"), lastTs + 1400));

    return () => timeouts.forEach(clearTimeout);
  }, [step]);

  /* ---- handlers ---- */
  const handleAudit = () => {
    if (!ticker.trim() || !fileName) return;
    setLogs([]);
    setStep("analyzing");
  };

  const handleFileDrop = useCallback((e: DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file?.type === "application/pdf") {
      setFileName(file.name);
    }
  }, []);

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) setFileName(file.name);
    },
    []
  );

  const canAudit = ticker.trim().length > 0 && fileName !== null;
  const progress =
    AUDIT_LOGS.length > 0 ? logs.length / AUDIT_LOGS.length : 0;

  /* ================================================================= */
  /* Render: Complete → Results View                                    */
  /* ================================================================= */

  if (step === "complete") {
    return <ResultsView audit={MOCK_AUDIT} />;
  }

  /* ================================================================= */
  /* Render: Analyzing → Terminal Log View                              */
  /* ================================================================= */

  if (step === "analyzing") {
    return (
      <div className="flex min-h-[calc(100vh-8rem)] items-center justify-center">
        <div className="animate-fade-in w-full max-w-2xl">
          <div className="card overflow-hidden">
            {/* Progress bar */}
            <div className="h-1 w-full bg-slate-100">
              <div
                className="h-full bg-accent transition-all duration-500 ease-out"
                style={{ width: `${progress * 100}%` }}
              />
            </div>

            {/* Header — click to skip */}
            <button
              onClick={() => setStep("complete")}
              className="flex w-full items-center justify-between border-b border-slate-100 px-5 py-3 text-left transition-colors hover:bg-slate-50"
            >
              <div className="flex items-center gap-2.5">
                <div className="h-2 w-2 animate-pulse rounded-full bg-accent" />
                <span className="text-sm font-medium text-slate-700">
                  CSRD Compliance Audit{" "}
                  <span className="font-mono font-semibold text-accent">
                    {ticker.toUpperCase() || "LUMI"}
                  </span>
                </span>
              </div>
              <span className="font-mono text-xs text-muted">
                {logs.length}/{AUDIT_LOGS.length} &middot; skip
              </span>
            </button>

            {/* Terminal */}
            <div className="bg-slate-900 p-5">
              <div className="h-72 overflow-y-auto pr-2 scrollbar-thin">
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

                {/* Blinking cursor */}
                {logs.length < AUDIT_LOGS.length && (
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
  /* Render: Idle → Audit Chamber (Hero)                               */
  /* ================================================================= */

  return (
    <div className="flex min-h-[calc(100vh-8rem)] items-center justify-center">
      <div className="animate-fade-in w-full max-w-xl">
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
            Audit EU Taxonomy alignment against ESRS disclosures and national
            registry filings.
          </p>
        </div>

        {/* Chamber Card */}
        <div className="card overflow-hidden">
          {/* LEI / Entity Search Row */}
          <div className="flex items-center gap-3 border-b border-slate-100 p-5">
            <label
              htmlFor="ticker-input"
              className="shrink-0 text-xs font-semibold uppercase tracking-widest text-muted"
            >
              Entity
            </label>
            <input
              id="ticker-input"
              type="text"
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase())}
              onKeyDown={(e) => e.key === "Enter" && handleAudit()}
              placeholder="LEI or company name"
              className="h-9 flex-1 rounded-lg border border-slate-200 bg-slate-50 px-3 font-mono text-sm text-slate-800 placeholder:text-slate-400 transition-colors focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20"
            />
            <button
              onClick={handleAudit}
              disabled={!canAudit}
              className="h-9 shrink-0 rounded-lg bg-accent px-5 text-sm font-semibold text-white transition-all hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-accent/30 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-accent"
            >
              Audit
            </button>
          </div>

          {/* PDF Dropzone */}
          <div className="p-5">
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setIsDragging(true);
              }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={handleFileDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`
                flex cursor-pointer flex-col items-center justify-center rounded-card border-2 border-dashed p-12 transition-all
                ${
                  isDragging
                    ? "border-accent bg-indigo-50"
                    : fileName
                      ? "border-emerald-300 bg-emerald-50/50"
                      : "border-slate-200 bg-indigo-50/30 hover:border-accent/40 hover:bg-indigo-50/60"
                }
              `}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf"
                onChange={handleFileSelect}
                className="hidden"
              />

              {fileName ? (
                <>
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-100">
                    <svg
                      className="h-5 w-5 text-emerald-600"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      strokeWidth={2.5}
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M5 13l4 4L19 7"
                      />
                    </svg>
                  </div>
                  <p className="mt-3 font-mono text-sm font-medium text-emerald-700">
                    {fileName}
                  </p>
                  <p className="mt-1 text-xs text-muted">Click to replace</p>
                </>
              ) : (
                <>
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-indigo-100">
                    <svg
                      className="h-5 w-5 text-accent"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      strokeWidth={2}
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"
                      />
                    </svg>
                  </div>
                  <p className="mt-3 text-sm font-medium text-slate-700">
                    Upload CSRD Sustainability Report
                  </p>
                  <p className="mt-1 text-xs text-muted">
                    Drag and drop PDF or click to browse
                  </p>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Dev shortcut */}
        <button
          onClick={() => setStep("complete")}
          className="mt-6 w-full text-center text-xs text-slate-400 transition-colors hover:text-accent"
        >
          Skip to results
        </button>
      </div>
    </div>
  );
}
