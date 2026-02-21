"use client";

import { useState, useRef, useCallback } from "react";
import { config } from "@/lib/config";
import {
  MOCK_COMPLIANCE_RESULT,
  ANALYSIS_LOGS,
  FREE_TEXT_ANALYSIS_LOGS,
  // Legacy mock data — kept for old views
  MOCK_AUDIT,
  AUDIT_LOGS,
  MOCK_COMPLIANCE_CHECK,
  COMPLIANCE_CHECK_LOGS,
} from "@/lib/mock-data";
import {
  startAnalysis,
  streamAuditEvents,
} from "@/lib/api";
import type {
  AuditLog,
  CompanyInputs,
  ComplianceResult,
  // Legacy types — kept for old views
  CSRDAudit,
  ComplianceCheckResult,
  SSEEvent,
} from "@/lib/types";

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */

export type Step = "idle" | "analyzing" | "complete";

export interface AuditStreamState {
  step: Step;
  logs: AuditLog[];
  /** v5.0 unified result — used by the new ComplianceResultView */
  result: ComplianceResult | null;
  /** @deprecated Legacy audit result — kept for old ResultsView */
  audit: CSRDAudit | null;
  /** @deprecated Legacy compliance check result — kept for old ComplianceCheckView */
  complianceCheck: ComplianceCheckResult | null;
  error: string | null;
  progress: number;
  totalLogs: number;
  /** v5.0 unified start — works for both modes */
  startAnalysis: (
    entity: string,
    mode: "structured_document" | "free_text",
    companyInputs: CompanyInputs,
    reportFile?: File | null,
    freeText?: string
  ) => void;
  /** @deprecated Use startAnalysis() instead */
  startAudit: (entity: string, reportFile: File | null) => void;
  /** @deprecated Use startAnalysis() instead */
  startComplianceCheck: (entity: string, freeText: string) => void;
  skipToComplete: (mode?: "structured_document" | "free_text") => void;
  reset: () => void;
}

/* ------------------------------------------------------------------ */
/* Hook                                                                */
/* ------------------------------------------------------------------ */

export function useAuditStream(): AuditStreamState {
  const [step, setStep] = useState<Step>("idle");
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [result, setResult] = useState<ComplianceResult | null>(null);
  const [audit, setAudit] = useState<CSRDAudit | null>(null);
  const [complianceCheck, setComplianceCheck] =
    useState<ComplianceCheckResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [completedNodes, setCompletedNodes] = useState(0);
  const [activeMode, setActiveMode] = useState<
    "structured_document" | "free_text"
  >("structured_document");

  // Cleanup refs
  const mockTimers = useRef<NodeJS.Timeout[]>([]);
  const sseCleanup = useRef<(() => void) | null>(null);

  /* ---- cleanup helper ---- */
  const cleanup = useCallback(() => {
    mockTimers.current.forEach(clearTimeout);
    mockTimers.current = [];
    sseCleanup.current?.();
    sseCleanup.current = null;
  }, []);

  /* ---- reset all state ---- */
  const resetState = useCallback(() => {
    setLogs([]);
    setResult(null);
    setAudit(null);
    setComplianceCheck(null);
    setError(null);
    setCompletedNodes(0);
  }, []);

  /* ---- mock flow (v5.0 unified) ---- */
  const startMockAnalysis = useCallback(
    (mode: "structured_document" | "free_text") => {
      resetState();
      setActiveMode(mode);
      setStep("analyzing");

      const mockLogs =
        mode === "free_text" ? FREE_TEXT_ANALYSIS_LOGS : ANALYSIS_LOGS;

      const timers: NodeJS.Timeout[] = [];

      mockLogs.forEach((log) => {
        timers.push(
          setTimeout(() => {
            setLogs((prev) => [...prev, log]);
          }, log.timestamp)
        );
      });

      const lastTs = mockLogs[mockLogs.length - 1].timestamp;
      timers.push(
        setTimeout(() => {
          // For free text mode, create a variant of the mock result
          if (mode === "free_text") {
            setResult({
              ...MOCK_COMPLIANCE_RESULT,
              mode: "free_text",
              score: {
                ...MOCK_COMPLIANCE_RESULT.score,
                overall: 36,
                disclosed_count: 5,
                partial_count: 3,
                missing_count: 10,
              },
            });
          } else {
            setResult(MOCK_COMPLIANCE_RESULT);
          }
          setStep("complete");
        }, lastTs + 1400)
      );

      mockTimers.current = timers;
    },
    [resetState]
  );

  /* ---- SSE event handler ---- */
  const handleSSEEvent = useCallback((event: SSEEvent) => {
    switch (event.type) {
      case "log":
        setLogs((prev) => [
          ...prev,
          {
            timestamp: Date.now(),
            agent: event.agent,
            message: event.message,
          },
        ]);
        break;
      case "node_complete":
        setCompletedNodes((prev) => prev + 1);
        break;
      case "complete":
        // v5.0 unified result
        if (event.result) {
          setResult(event.result);
        }
        // Legacy fallbacks
        if (event.audit) {
          setAudit(event.audit);
        }
        if (event.compliance_check) {
          setComplianceCheck(event.compliance_check);
        }
        setStep("complete");
        sseCleanup.current?.();
        sseCleanup.current = null;
        break;
      case "error":
        setError(event.message);
        setStep("idle");
        sseCleanup.current?.();
        sseCleanup.current = null;
        break;
    }
  }, []);

  /* ---- real flow (v5.0 unified) ---- */
  const startRealAnalysis = useCallback(
    async (
      entity: string,
      mode: "structured_document" | "free_text",
      companyInputs: CompanyInputs,
      reportFile?: File | null,
      freeText?: string
    ) => {
      resetState();
      setActiveMode(mode);
      setStep("analyzing");

      let auditId: string;
      try {
        auditId = await startAnalysis({
          entity,
          mode,
          companyInputs,
          reportFile,
          freeText,
        });
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to start analysis."
        );
        setStep("idle");
        return;
      }

      const closeSse = streamAuditEvents(
        auditId,
        handleSSEEvent,
        (errMsg: string) => {
          setError(errMsg);
          setStep("idle");
        }
      );

      sseCleanup.current = closeSse;
    },
    [resetState, handleSSEEvent]
  );

  /* ---- public API: v5.0 unified start ---- */
  const doStartAnalysis = useCallback(
    (
      entity: string,
      mode: "structured_document" | "free_text",
      companyInputs: CompanyInputs,
      reportFile?: File | null,
      freeText?: string
    ) => {
      cleanup();
      if (config.useMock) {
        startMockAnalysis(mode);
      } else {
        startRealAnalysis(entity, mode, companyInputs, reportFile, freeText);
      }
    },
    [cleanup, startMockAnalysis, startRealAnalysis]
  );

  /* ---- deprecated: legacy start functions (mock-only) ---- */
  const doStartAudit = useCallback(
    (...args: [entity: string, reportFile: File | null]) => {
      void args; // legacy params — kept for API compatibility
      cleanup();
      if (config.useMock) {
        resetState();
        setActiveMode("structured_document");
        setStep("analyzing");

        const timers: NodeJS.Timeout[] = [];
        AUDIT_LOGS.forEach((log) => {
          timers.push(
            setTimeout(() => {
              setLogs((prev) => [...prev, log]);
            }, log.timestamp)
          );
        });
        const lastTs = AUDIT_LOGS[AUDIT_LOGS.length - 1].timestamp;
        timers.push(
          setTimeout(() => {
            setAudit(MOCK_AUDIT);
            setStep("complete");
          }, lastTs + 1400)
        );
        mockTimers.current = timers;
      }
    },
    [cleanup, resetState]
  );

  const doStartComplianceCheck = useCallback(
    (...args: [entity: string, freeText: string]) => {
      void args; // legacy params — kept for API compatibility
      cleanup();
      if (config.useMock) {
        resetState();
        setActiveMode("free_text");
        setStep("analyzing");

        const timers: NodeJS.Timeout[] = [];
        COMPLIANCE_CHECK_LOGS.forEach((log) => {
          timers.push(
            setTimeout(() => {
              setLogs((prev) => [...prev, log]);
            }, log.timestamp)
          );
        });
        const lastTs =
          COMPLIANCE_CHECK_LOGS[COMPLIANCE_CHECK_LOGS.length - 1].timestamp;
        timers.push(
          setTimeout(() => {
            setComplianceCheck(MOCK_COMPLIANCE_CHECK);
            setStep("complete");
          }, lastTs + 1400)
        );
        mockTimers.current = timers;
      }
    },
    [cleanup, resetState]
  );

  const skipToComplete = useCallback(
    (mode?: "structured_document" | "free_text") => {
      cleanup();
      const effectiveMode = mode ?? activeMode;
      if (config.useMock) {
        if (effectiveMode === "free_text") {
          setResult({
            ...MOCK_COMPLIANCE_RESULT,
            mode: "free_text",
            score: {
              ...MOCK_COMPLIANCE_RESULT.score,
              overall: 36,
              disclosed_count: 5,
              partial_count: 3,
              missing_count: 10,
            },
          });
        } else {
          setResult(MOCK_COMPLIANCE_RESULT);
        }
      }
      setStep("complete");
    },
    [cleanup, activeMode]
  );

  const reset = useCallback(() => {
    cleanup();
    setStep("idle");
    resetState();
  }, [cleanup, resetState]);

  /* ---- progress: always 3 agents in v5.0 ---- */
  const AGENT_COUNT = 3;
  const mockLogs =
    activeMode === "free_text" ? FREE_TEXT_ANALYSIS_LOGS : ANALYSIS_LOGS;

  const progress = config.useMock
    ? mockLogs.length > 0
      ? logs.length / mockLogs.length
      : 0
    : completedNodes / AGENT_COUNT;

  const totalLogs = config.useMock ? mockLogs.length : -1;

  return {
    step,
    logs,
    result,
    audit,
    complianceCheck,
    error,
    progress,
    totalLogs,
    startAnalysis: doStartAnalysis,
    startAudit: doStartAudit,
    startComplianceCheck: doStartComplianceCheck,
    skipToComplete,
    reset,
  };
}
