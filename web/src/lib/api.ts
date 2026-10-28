import type { components } from "@/lib/api-types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

// These shapes come from the API's OpenAPI file (api/openapi.json), through src/lib/api-types.ts.
// Do not edit them by hand. After changing an endpoint or a model in the API, run
// `python -m api.export_openapi` (project root) and then `npm run gen:api` (this folder).
type Schemas = components["schemas"];

export type Student = Schemas["Student"];
export type FeatureName = keyof Student;
export type NumericSpec = Schemas["NumericSpec"];
export type CategoricalSpec = Schemas["CategoricalSpec"];
export type Interval = Schemas["Interval"];
export type Meta = Schemas["MetaResponse"];
export type Tip = Schemas["Tip"];
export type Prediction = Schemas["PredictResponse"];
export type WhatIfResult = Schemas["WhatIfResponse"];
export type Insights = Schemas["InsightsResponse"];

// A cell of an uploaded CSV can be text, a number or empty. The API documents the row values as
// unknown, so this is the one shape kept here.
export type BatchResult = Omit<Schemas["BatchResponse"], "rows"> & {
  rows: Record<string, string | number | null>[];
};

/** Error from the API. `messages` holds every validation message the server sent. */
export class ApiError extends Error {
  constructor(public status: number, public messages: string[]) {
    super(messages.join("\n"));
  }
}

function detailToMessages(detail: unknown): string[] {
  if (Array.isArray(detail)) {
    return detail.map((d) =>
      typeof d === "string" ? d : `${(d?.loc ?? []).slice(1).join(".")}: ${d?.msg ?? JSON.stringify(d)}`,
    );
  }
  if (typeof detail === "string") return [detail];
  return ["Unexpected error from the server."];
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, init);
  } catch {
    throw new ApiError(0, [`Cannot reach the API at ${API_URL}. Is it running?`]);
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiError(res.status, detailToMessages(body?.detail ?? `HTTP ${res.status}`));
  }
  return res.json() as Promise<T>;
}

export const fetcher = <T,>(path: string) => request<T>(path);

const postJson = <T,>(path: string, body: unknown) =>
  request<T>(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export const predict = (student: Student) => postJson<Prediction>("/predict", student);

export const whatIf = (student: Student, changes: Partial<Student>) =>
  postJson<WhatIfResult>("/what-if", { student, changes });

export function predictBatch(file: File) {
  const form = new FormData();
  form.append("file", file);
  return request<BatchResult>("/predict/batch", { method: "POST", body: form });
}

export const templateUrl = `${API_URL}/template.csv`;
