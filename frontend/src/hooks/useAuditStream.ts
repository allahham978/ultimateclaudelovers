"use client";

import { useState, useRef, useCallback } from "react";
import { config } from "@/lib/config";
import { MOCK_AUDIT, AUDIT_LOGS } from "@/lib/mock-data";
import { startAuditRun, streamAuditEvents } from "@/lib/api";
import type { AuditLog, CSRDAudit, SSEEvent } from "@/lib/types";

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */

export type Step = "idle" | "analyzing" | "complete";

export interface AuditStreamState {
  step: Step;
  logs: AuditLog[];
  audit: CSRDAudit | null;
  error: string | null;
  progress: number;
  totalLogs: number;
  startAudit: (entity: string, reportFile: File | null) => void;
  skipToComplete: () => void;
  reset: () => void;
}

/* ------------------------------------------------------------------ */
/* Hook                                                                */
/* ------------------------------------------------------------------ */

export function useAuditStream(): AuditStreamState {
  const [step, setStep] = useState<Step>("idle");
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [audit, setAudit] = useState<CSRDAudit | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [completedNodes, setCompletedNodes] = useState(0);

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

  /* ---- mock flow ---- */
  const startMock = useCallback(() => {
    setLogs([]);
    setAudit(null);
    setError(null);
    setCompletedNodes(0);
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

  /* ---- real flow ---- */
  const startReal = useCallback(
    async (entity: string, reportFile: File) => {
      setLogs([]);
      setAudit(null);
      setError(null);
      setCompletedNodes(0);
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
        (event: SSEEvent) => {
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
              setAudit(event.audit);
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
        },
        (errMsg: string) => {
          setError(errMsg);
          setStep("idle");
        }
      );

      sseCleanup.current = closeSse;
    },
    []
  );

  /* ---- public API ---- */
  const startAudit = useCallback(
    (entity: string, reportFile: File | null) => {
      cleanup();
      if (config.useMock) {
        startMock();
      } else {
        if (!reportFile) {
          return;
        }
        startReal(entity, reportFile);
      }
    },
    [cleanup, startMock, startReal]
  );

  const skipToComplete = useCallback(() => {
    cleanup();
    if (config.useMock) {
      setAudit(MOCK_AUDIT);
    }
    // In real mode, audit stays as whatever we've received so far (possibly null).
    setStep("complete");
  }, [cleanup]);

  const reset = useCallback(() => {
    cleanup();
    setStep("idle");
    setLogs([]);
    setAudit(null);
    setError(null);
    setCompletedNodes(0);
  }, [cleanup]);

  /* ---- progress ---- */
  const progress = config.useMock
    ? AUDIT_LOGS.length > 0
      ? logs.length / AUDIT_LOGS.length
      : 0
    : completedNodes / 4; // 4 agents: extractor, fetcher, auditor, consultant

  const totalLogs = config.useMock ? AUDIT_LOGS.length : -1; // -1 signals unknown total

  return {
    step,
    logs,
    audit,
    error,
    progress,
    totalLogs,
    startAudit,
    skipToComplete,
    reset,
  };
}
