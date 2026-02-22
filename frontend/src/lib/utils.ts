import type { Priority } from "./types";

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
/* Compliance Score (v5.0)                                            */
/* ------------------------------------------------------------------ */

/** Returns hex color for compliance score: green >= 70, amber >= 40, red < 40 */
export function scoreColor(score: number): string {
  if (score >= 70) return "#10B981"; // emerald — good
  if (score >= 40) return "#F59E0B"; // amber — needs work
  return "#EF4444"; // red — critical gaps
}

/** Returns Tailwind classes for score badge background + text */
export function scoreStyle(score: number): { bg: string; text: string; label: string } {
  if (score >= 70)
    return { bg: "bg-emerald-50 border-emerald-200", text: "text-emerald-700", label: "Good" };
  if (score >= 40)
    return { bg: "bg-amber-50 border-amber-200", text: "text-amber-700", label: "Needs Improvement" };
  return { bg: "bg-red-50 border-red-200", text: "text-red-700", label: "Critical Gaps" };
}

/** Returns Tailwind classes for recommendation priority tier header */
export function priorityTierStyle(priority: Priority): {
  bg: string;
  text: string;
  border: string;
  dot: string;
  label: string;
} {
  switch (priority) {
    case "critical":
      return { bg: "bg-red-50", text: "text-red-700", border: "border-red-200", dot: "bg-red-500", label: "Critical" };
    case "high":
      return { bg: "bg-amber-50", text: "text-amber-700", border: "border-amber-200", dot: "bg-amber-500", label: "High" };
    case "moderate":
      return { bg: "bg-yellow-50", text: "text-yellow-700", border: "border-yellow-200", dot: "bg-yellow-500", label: "Moderate" };
    case "low":
      return { bg: "bg-emerald-50", text: "text-emerald-700", border: "border-emerald-200", dot: "bg-emerald-500", label: "Low" };
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
