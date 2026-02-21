import { config } from "./config";
import type { SSEEvent } from "./types";

type DocumentSlot = "management" | "taxonomy" | "transition";

/**
 * POST /audit/run — kicks off an audit and returns the run_id for SSE streaming.
 */
export async function startAuditRun(
  entity: string,
  files: Record<DocumentSlot, File | null>
): Promise<string> {
  const form = new FormData();
  form.append("entity", entity);

  if (files.management) form.append("management_report", files.management);
  if (files.taxonomy) form.append("taxonomy_table", files.taxonomy);
  if (files.transition) form.append("transition_plan", files.transition);

  const res = await fetch(`${config.apiUrl}/audit/run`, {
    method: "POST",
    body: form,
  });

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`POST /audit/run failed (${res.status}): ${body}`);
  }

  const data: { run_id: string } = await res.json();
  return data.run_id;
}

/**
 * GET /audit/stream/{run_id} — opens an EventSource for real-time SSE events.
 * Calls `onEvent` for each parsed event; calls `onError` on failure.
 * Returns a cleanup function that closes the connection.
 */
export function streamAuditEvents(
  runId: string,
  onEvent: (event: SSEEvent) => void,
  onError: (err: string) => void
): () => void {
  const url = `${config.apiUrl}/audit/stream/${runId}`;
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
    // EventSource will fire onerror for both network failures and stream-end.
    // If readyState is CLOSED the server ended the stream normally.
    if (source.readyState === EventSource.CLOSED) return;
    onError("Lost connection to audit stream.");
    source.close();
  };

  return () => source.close();
}
