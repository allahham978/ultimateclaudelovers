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

  console.log(`[API] POST ${config.apiUrl}/audit/run — mode=${params.mode}, entity=${params.entity}`);
  if (params.reportFile) {
    console.log(`[API] Uploading file: ${params.reportFile.name} (${(params.reportFile.size / 1024 / 1024).toFixed(1)} MB)`);
  }

  let res: Response;
  try {
    res = await fetch(`${config.apiUrl}/audit/run`, {
      method: "POST",
      body: form,
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    console.error(`[API] fetch() threw:`, err);
    throw new Error(`Network error connecting to ${config.apiUrl}: ${msg}`);
  }

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    console.error(`[API] POST /audit/run failed (${res.status}):`, body);
    throw new Error(`POST /audit/run failed (${res.status}): ${body}`);
  }

  console.log(`[API] POST /audit/run succeeded`);

  const data: { audit_id: string } = await res.json();
  return data.audit_id;
}

// ============================================================================
// SSE Streaming
// ============================================================================

/**
 * GET /audit/{id}/stream — consumes SSE via fetch + ReadableStream.
 * More reliable than EventSource for cross-origin streaming.
 * Calls `onEvent` for each parsed event; calls `onError` on failure.
 * Returns a cleanup function that aborts the connection.
 */
export function streamAuditEvents(
  auditId: string,
  onEvent: (event: SSEEvent) => void,
  onError: (err: string) => void
): () => void {
  const url = `${config.apiUrl}/audit/${auditId}/stream`;
  console.log(`[SSE] Opening fetch stream: ${url}`);

  const controller = new AbortController();

  (async () => {
    let res: Response;
    try {
      res = await fetch(url, { signal: controller.signal });
    } catch (err) {
      if (controller.signal.aborted) return;
      onError(`Failed to connect to audit stream: ${err}`);
      return;
    }

    if (!res.ok || !res.body) {
      onError(`Audit stream returned ${res.status}`);
      return;
    }

    console.log(`[SSE] Connection opened`);
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Process complete SSE lines from buffer
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed || trimmed.startsWith(":")) continue;

          if (trimmed.startsWith("data: ")) {
            const jsonStr = trimmed.slice(6);
            try {
              const parsed: SSEEvent = JSON.parse(jsonStr);
              console.log(`[SSE] Event:`, parsed.type, parsed.type === "log" ? (parsed as { message?: string }).message : "");
              onEvent(parsed);
            } catch {
              console.error(`[SSE] Failed to parse:`, jsonStr);
            }
          }
        }
      }
    } catch (err) {
      if (controller.signal.aborted) return;
      console.error(`[SSE] Stream read error:`, err);
      onError(`Lost connection to audit stream.`);
    }

    console.log(`[SSE] Stream ended`);
  })();

  return () => {
    console.log(`[SSE] Cleanup — aborting connection`);
    controller.abort();
  };
}
