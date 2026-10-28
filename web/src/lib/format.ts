import type { NumericSpec } from "@/lib/api";

export function formatValue(value: number | string, unit = ""): string {
  if (typeof value === "string") return value;
  const text = Number.isInteger(value) ? String(value) : value.toFixed(1);
  if (!unit) return text;
  return unit === "%" || unit === "h" || unit.startsWith("/") ? `${text}${unit}` : `${text} ${unit}`;
}

export const formatSpec = (value: number, spec: NumericSpec) => formatValue(value, spec.unit);

export const prettyModelName = (name: string | null | undefined) =>
  (name ?? "unknown").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

/** Score band used for colour and wording. */
export function scoreBand(score: number) {
  if (score >= 85) return { label: "Excellent", tone: "text-success" };
  if (score >= 70) return { label: "Good", tone: "text-primary" };
  if (score >= 50) return { label: "Borderline", tone: "text-warning" };
  return { label: "At risk", tone: "text-danger" };
}
