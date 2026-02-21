"use client";

import { useState, useRef, useCallback } from "react";
import { config } from "@/lib/config";
import {
  MOCK_AUDIT,
  AUDIT_LOGS,
  MOCK_COMPLIANCE_CHECK,
  COMPLIANCE_CHECK_LOGS,
} from "@/lib/mock-data";
import {
  startAuditRun,
  startComplianceCheck as apiStartComplianceCheck,
  streamAuditEvents,
} from "@/lib/api";
import type {
  AuditLog,
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
  audit: CSRDAudit | null;
  complianceCheck: ComplianceCheckResult | null;
  error: string | null;
  progress: number;
  totalLogs: number;
  startAudit: (entity: string, reportFile: File | null) => void;
  startComplianceCheck: (entity: string, freeText: string) => void;
  skipToComplete: (mode?: "full_audit" | "compliance_check") => void;
  reset: () => void;
}

/* ------------------------------------------------------------------ */
/* Hook                                                                */
/* ------------------------------------------------------------------ */

export function useAuditStream(): AuditStreamState {
  const [step, setStep] = useState<Step>("idle");
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [audit, setAudit] = useState<CSRDAudit | null>(null);
  const [complianceCheck, setComplianceCheck] =
    useState<ComplianceCheckResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [completedNodes, setCompletedNodes] = useState(0);
  const [activeMode, setActiveMode] = useState<
    "full_audit" | "compliance_check"
  >("full_audit");

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

  /* ---- mock flow (full audit) ---- */
  const startMockAudit = useCallback(() => {
    setLogs([]);
    setAudit(null);
    setComplianceCheck(null);
    setError(null);
    setCompletedNodes(0);
    setActiveMode("full_audit");
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
  }, []);

  /* ---- mock flow (compliance check) ---- */
  const startMockComplianceCheck = useCallback(() => {
    setLogs([]);
    setAudit(null);
    setComplianceCheck(null);
    setError(null);
    setCompletedNodes(0);
    setActiveMode("compliance_check");
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
  }, []);

  /* ---- SSE event handler (shared by both modes) ---- */
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

  /* ---- real flow (full audit) ---- */
  const startRealAudit = useCallback(
    async (entity: string, reportFile: File) => {
      setLogs([]);
      setAudit(null);
      setComplianceCheck(null);
      setError(null);
      setCompletedNodes(0);
      setActiveMode("full_audit");
      setStep("analyzing");

      let runId: string;
      try {
        runId = await startAuditRun(entity, reportFile);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to start audit.");
        setStep("idle");
        return;
      }

      const closeSse = streamAuditEvents(
        runId,
        handleSSEEvent,
        (errMsg: string) => {
          setError(errMsg);
          setStep("idle");
        }
      );

      sseCleanup.current = closeSse;
    },
    [handleSSEEvent]
  );

  /* ---- real flow (compliance check) ---- */
  const startRealComplianceCheck = useCallback(
    async (entity: string, freeText: string) => {
      setLogs([]);
      setAudit(null);
      setComplianceCheck(null);
      setError(null);
      setCompletedNodes(0);
      setActiveMode("compliance_check");
      setStep("analyzing");

      let runId: string;
      try {
        runId = await apiStartComplianceCheck(entity, freeText);
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : "Failed to start compliance check."
        );
        setStep("idle");
        return;
      }

      const closeSse = streamAuditEvents(
        runId,
        handleSSEEvent,
        (errMsg: string) => {
          setError(errMsg);
          setStep("idle");
        }
      );

      sseCleanup.current = closeSse;
    },
    [handleSSEEvent]
  );

  /* ---- public API ---- */
  const startAudit = useCallback(
    (entity: string, reportFile: File | null) => {
      cleanup();
      if (config.useMock) {
        startMockAudit();
      } else {
        if (!reportFile) {
          return;
        }
        startRealAudit(entity, reportFile);
      }
    },
    [cleanup, startMockAudit, startRealAudit]
  );

  const startComplianceCheck = useCallback(
    (entity: string, freeText: string) => {
      cleanup();
      if (config.useMock) {
        startMockComplianceCheck();
      } else {
        startRealComplianceCheck(entity, freeText);
      }
    },
    [cleanup, startMockComplianceCheck, startRealComplianceCheck]
  );

  const skipToComplete = useCallback(
    (mode?: "full_audit" | "compliance_check") => {
      cleanup();
      const effectiveMode = mode ?? activeMode;
      if (config.useMock) {
        if (effectiveMode === "compliance_check") {
          setComplianceCheck(MOCK_COMPLIANCE_CHECK);
        } else {
          setAudit(MOCK_AUDIT);
        }
      }
      setStep("complete");
    },
    [cleanup, activeMode]
  );

  const reset = useCallback(() => {
    cleanup();
    setStep("idle");
    setLogs([]);
    setAudit(null);
    setComplianceCheck(null);
    setError(null);
    setCompletedNodes(0);
  }, [cleanup]);

  /* ---- progress ---- */
  const agentCount = activeMode === "compliance_check" ? 3 : 4;
  const mockLogs =
    activeMode === "compliance_check" ? COMPLIANCE_CHECK_LOGS : AUDIT_LOGS;

  const progress = config.useMock
    ? mockLogs.length > 0
      ? logs.length / mockLogs.length
      : 0
    : completedNodes / agentCount;

  const totalLogs = config.useMock ? mockLogs.length : -1;

  return {
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
  };
}
