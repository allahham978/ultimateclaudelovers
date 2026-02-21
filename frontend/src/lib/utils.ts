import type { ESRSStatus, MaterialityLevel, TaxonomyStatus } from "./types";

/* ------------------------------------------------------------------ */
/* Taxonomy Alignment Color                                           */
/* ------------------------------------------------------------------ */

export function taxonomyColor(pct: number): string {
  if (pct >= 60) return "#10B981"; // emerald — aligned
  if (pct >= 30) return "#F59E0B"; // amber — partial
  return "#EF4444"; // red — non-compliant
}

export function taxonomyStatusStyle(status: TaxonomyStatus): {
  bg: string;
  text: string;
  label: string;
} {
  switch (status) {
    case "aligned":
      return {
        bg: "bg-emerald-50 border-emerald-200",
        text: "text-emerald-700",
        label: "Taxonomy Aligned",
      };
    case "partially_aligned":
      return {
        bg: "bg-amber-50 border-amber-200",
        text: "text-amber-700",
        label: "Partially Aligned",
      };
    case "non_compliant":
      return {
        bg: "bg-red-50 border-red-200",
        text: "text-red-700",
        label: "Non-Compliant",
      };
  }
}

/* ------------------------------------------------------------------ */
/* ESRS Status Badges                                                 */
/* ------------------------------------------------------------------ */

export function esrsStatusStyle(status: ESRSStatus): {
  bg: string;
  text: string;
  label: string;
} {
  switch (status) {
    case "disclosed":
      return {
        bg: "bg-emerald-50 border-emerald-200",
        text: "text-emerald-700",
        label: "Disclosed",
      };
    case "partial":
      return {
        bg: "bg-amber-50 border-amber-200",
        text: "text-amber-700",
        label: "Partial",
      };
    case "missing":
      return {
        bg: "bg-red-50 border-red-200",
        text: "text-red-700",
        label: "Missing",
      };
    case "non_compliant":
      return {
        bg: "bg-rose-100 border-rose-300",
        text: "text-rose-800",
        label: "Non-Compliant",
      };
  }
}

/* ------------------------------------------------------------------ */
/* Materiality Level Badge                                            */
/* ------------------------------------------------------------------ */

export function materialityStyle(level: MaterialityLevel): {
  bg: string;
  text: string;
} {
  switch (level) {
    case "high":
      return { bg: "bg-red-50", text: "text-red-600" };
    case "medium":
      return { bg: "bg-amber-50", text: "text-amber-600" };
    case "low":
      return { bg: "bg-slate-50", text: "text-slate-500" };
    case "not_material":
      return { bg: "bg-slate-50", text: "text-slate-400" };
  }
}

/* ------------------------------------------------------------------ */
/* Priority Badge                                                     */
/* ------------------------------------------------------------------ */

export function priorityColor(priority: string): {
  bg: string;
  text: string;
} {
  switch (priority) {
    case "critical":
      return { bg: "bg-red-50 border-red-200", text: "text-red-700" };
    case "high":
      return { bg: "bg-amber-50 border-amber-200", text: "text-amber-700" };
    case "moderate":
      return {
        bg: "bg-indigo-50 border-indigo-200",
        text: "text-indigo-700",
      };
    default:
      return { bg: "bg-slate-50 border-slate-200", text: "text-slate-600" };
  }
}

/* ------------------------------------------------------------------ */
/* Formatters                                                         */
/* ------------------------------------------------------------------ */

export function formatEUR(amount: number): string {
  return new Intl.NumberFormat("de-DE", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  }).format(amount);
}

export function formatDuration(ms: number): string {
  return `${(ms / 1000).toFixed(1)}s`;
}
