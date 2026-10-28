export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

export type Student = {
  age: number;
  gender: string;
  study_hours_per_day: number;
  social_media_hours: number;
  netflix_hours: number;
  part_time_job: string;
  attendance_percentage: number;
  sleep_hours: number;
  diet_quality: string;
  exercise_frequency: number;
  parental_education_level: string;
  internet_quality: string;
  mental_health_rating: number;
  extracurricular_participation: string;
};

export type FeatureName = keyof Student;

export type NumericSpec = {
  label: string;
  unit: string;
  integer: boolean;
  step: number;
  min: number;
  max: number;
  median: number;
};

export type CategoricalSpec = { label: string; options: string[] };

export type Interval = { low: number; high: number; level: number };

export type Meta = {
  model: {
    name: string | null;
    tuned: boolean | null;
    trained_at: string | null;
    test_metrics: { rmse: number; r2: number; interval_coverage: number } | null;
    interval: { level: number; half_width: number } | null;
    sklearn_version_matches: boolean;
  };
  features: FeatureName[];
  numeric: Record<string, NumericSpec>;
  categorical: Record<string, CategoricalSpec>;
  habits: { feature: FeatureName; label: string }[];
  diet_order: string[];
  max_batch_rows: number;
};

export type Tip = {
  feature: FeatureName;
  label: string;
  current: number | string;
  suggested: number | string;
  unit: string;
  gain: number;
};

export type Prediction = {
  score: number;
  interval: Interval | null;
  edge_features: FeatureName[];
  tips: Tip[];
};

export type WhatIfResult = {
  base_score: number;
  new_score: number;
  delta: number;
  interval: Interval | null;
};

export type BatchResult = {
  columns: string[];
  rows: Record<string, string | number | null>[];
  summary: { count: number; mean_score: number; below_50: number };
  warnings: string[];
};

export type Insights = {
  count: number;
  summary: { mean: number; median: number; std: number; min: number; max: number };
  histogram: { start: number; end: number; count: number }[];
  correlations: { feature: string; label: string; r: number }[];
  category_means: Record<string, { value: string; mean: number; count: number }[]>;
  scatter: Record<string, { x: number; y: number }[]>;
  predicted_vs_actual: { actual: number; predicted: number }[];
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
