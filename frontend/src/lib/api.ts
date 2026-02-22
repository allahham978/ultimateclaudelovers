import { config } from "./config";
import type { CompanyInputs, SSEEvent } from "./types";

// ============================================================================
// Analysis API — Unified for both modes
// ============================================================================

export interface AnalysisParams {
  entity: string;
  mode: "structured_document" | "free_text";
  companyInputs: CompanyInputs;
  reportFile?: File | null;
  freeText?: string;
}

/**
 * POST /audit/run — starts a unified analysis (structured document or free text)
 * and returns the audit_id for SSE streaming.
 *
 * Sends entity_id, mode, company inputs, and either a report JSON file or free text.
 */
export async function startAnalysis(params: AnalysisParams): Promise<string> {
  const form = new FormData();
  form.append("entity_id", params.entity);
  form.append("mode", params.mode);

  // Company inputs (always required)
  form.append(
    "number_of_employees",
    String(params.companyInputs.number_of_employees)
  );
  form.append("revenue_eur", String(params.companyInputs.revenue_eur));
  form.append(
    "total_assets_eur",
    String(params.companyInputs.total_assets_eur)
  );
  form.append("reporting_year", String(params.companyInputs.reporting_year));

  // Mode-specific input
  if (params.mode === "structured_document" && params.reportFile) {
    form.append("report_json", params.reportFile);
  } else if (params.mode === "free_text" && params.freeText) {
    form.append("free_text", params.freeText);
  }

  const res = await fetch(`${config.apiUrl}/audit/run`, {
    method: "POST",
    body: form,
  });

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`POST /audit/run failed (${res.status}): ${body}`);
  }

  const data: { audit_id: string } = await res.json();
  return data.audit_id;
}

// ============================================================================
// SSE Streaming
// ============================================================================

/**
 * GET /audit/{id}/stream — opens an EventSource for real-time SSE events.
 * Calls `onEvent` for each parsed event; calls `onError` on failure.
 * Returns a cleanup function that closes the connection.
 */
export function streamAuditEvents(
  auditId: string,
  onEvent: (event: SSEEvent) => void,
  onError: (err: string) => void
): () => void {
  const url = `${config.apiUrl}/audit/${auditId}/stream`;
  const source = new EventSource(url);

  source.onmessage = (e) => {
    try {
      const parsed: SSEEvent = JSON.parse(e.data);
      onEvent(parsed);
    } catch {
      onError(`Failed to parse SSE event: ${e.data}`);
    }
  };

  source.onerror = () => {
    if (source.readyState === EventSource.CLOSED) return;
    onError("Lost connection to audit stream.");
    source.close();
  };

  return () => source.close();
}
