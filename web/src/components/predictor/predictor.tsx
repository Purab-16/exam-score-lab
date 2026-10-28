"use client";

import { AlertTriangle, ArrowLeft, ArrowRight, Loader2, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { ApiErrorAlert, PageSkeleton } from "@/components/api-state";
import { NumberField, SelectField } from "@/components/fields";
import { ScoreGauge } from "@/components/predictor/score-gauge";
import { TipList } from "@/components/predictor/tip-list";
import { WhatIfPanel } from "@/components/predictor/what-if-panel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { predict, type FeatureName, type Meta, type Prediction, type Student } from "@/lib/api";
import { useMeta } from "@/lib/hooks";
import { cn } from "@/lib/utils";

const STEPS: { title: string; description: string; fields: FeatureName[] }[] = [
  { title: "About", description: "Who the student is.", fields: ["age", "gender", "parental_education_level"] },
  {
    title: "Study",
    description: "Time spent on school and commitments outside it.",
    fields: ["study_hours_per_day", "attendance_percentage", "part_time_job", "extracurricular_participation"],
  },
  {
    title: "Lifestyle",
    description: "Daily habits outside class.",
    fields: ["sleep_hours", "social_media_hours", "netflix_hours", "exercise_frequency", "diet_quality"],
  },
  { title: "Wellbeing", description: "How the student feels and their setup at home.", fields: ["mental_health_rating", "internet_quality"] },
];

function defaultStudent(meta: Meta): Student {
  const values: Record<string, number | string> = {};
  for (const [name, spec] of Object.entries(meta.numeric)) {
    values[name] = spec.integer ? Math.round(spec.median) : Math.round(spec.median * 10) / 10;
  }
  for (const [name, spec] of Object.entries(meta.categorical)) {
    values[name] = spec.options[0];
  }
  // A middle-of-the-road starting point reads better than alphabetical first options
  values.diet_quality = meta.diet_order[1] ?? values.diet_quality;
  if (meta.categorical.internet_quality.options.includes("Average")) values.internet_quality = "Average";
  return values as Student;
}

const sameStudent = (a: Student | null, b: Student | null) => !!a && !!b && JSON.stringify(a) === JSON.stringify(b);

export function Predictor() {
  const { data: meta, error: metaError, isLoading } = useMeta();

  if (metaError) return <ApiErrorAlert error={metaError} />;
  if (isLoading || !meta) return <PageSkeleton />;
  return <PredictorForm meta={meta} />;
}

function PredictorForm({ meta }: { meta: Meta }) {
  const [student, setStudent] = useState<Student>(() => defaultStudent(meta));
  const [step, setStep] = useState(0);
  const [result, setResult] = useState<{ prediction: Prediction; student: Student } | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(false);

  const stale = result != null && !sameStudent(result.student, student);
  const edge = useMemo(() => new Set(result?.prediction.edge_features ?? []), [result]);

  const update = (name: FeatureName, value: number | string) => setStudent((s) => ({ ...s, [name]: value }));

  async function runPrediction() {
    setLoading(true);
    setError(null);
    try {
      const snapshot = { ...student };
      setResult({ prediction: await predict(snapshot), student: snapshot });
    } catch (e) {
      setError(e);
    } finally {
      setLoading(false);
    }
  }

  // On small screens the result is below the form, so scroll to it after predicting
  useEffect(() => {
    if (result && window.innerWidth < 1024) {
      document.getElementById("result")?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [result]);

  const current = STEPS[step];
  const isLast = step === STEPS.length - 1;

  return (
    <div className="space-y-10">
      <div className="grid items-start gap-6 lg:grid-cols-[1.25fr_1fr]">
        {/* ---------- Profile form ---------- */}
        <Card className="rounded-2xl">
          <CardHeader className="gap-4">
            <ol className="grid grid-cols-4 gap-2" aria-label="Profile steps">
              {STEPS.map((s, i) => (
                <li key={s.title}>
                  <button
                    type="button"
                    onClick={() => setStep(i)}
                    aria-current={i === step ? "step" : undefined}
                    className={cn(
                      "group w-full rounded-lg border px-2 py-2 text-left transition-colors",
                      i === step ? "border-primary bg-accent" : "hover:bg-muted",
                    )}
                  >
                    <span className={cn("block font-mono text-[11px] text-muted-foreground", i === step && "text-primary")}>
                      0{i + 1}
                    </span>
                    <span className="block truncate text-xs font-medium sm:text-sm">{s.title}</span>
                  </button>
                </li>
              ))}
            </ol>
            <div>
              <CardTitle className="font-heading text-xl">{current.title}</CardTitle>
              <CardDescription>{current.description}</CardDescription>
            </div>
          </CardHeader>

          <CardContent className="space-y-8">
            <div className="grid gap-x-8 gap-y-7 sm:grid-cols-2">
              {current.fields.map((name) =>
                meta.numeric[name] ? (
                  <NumberField
                    key={name}
                    spec={meta.numeric[name]}
                    value={student[name] as number}
                    onChange={(v) => update(name, v)}
                    highlight={!stale && edge.has(name)}
                  />
                ) : (
                  <SelectField
                    key={name}
                    spec={meta.categorical[name]}
                    value={student[name] as string}
                    options={name === "diet_quality" ? meta.diet_order : undefined}
                    onChange={(v) => update(name, v)}
                  />
                ),
              )}
            </div>

            <div className="flex flex-wrap items-center gap-2 border-t pt-5">
              <Button variant="ghost" onClick={() => setStep(step - 1)} disabled={step === 0}>
                <ArrowLeft data-icon="inline-start" aria-hidden /> Back
              </Button>
              {!isLast && (
                <Button variant="outline" onClick={() => setStep(step + 1)}>
                  Next <ArrowRight data-icon="inline-end" aria-hidden />
                </Button>
              )}
              <Button size="lg" className="ml-auto px-4" onClick={runPrediction} disabled={loading}>
                {loading ? <Loader2 className="animate-spin" aria-hidden /> : <Sparkles aria-hidden />}
                {result ? "Update prediction" : "Predict score"}
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* ---------- Result ---------- */}
        <section id="result" aria-live="polite" className="scroll-mt-20 lg:sticky lg:top-20">
          <Card className="ruled rounded-2xl bg-paper">
            <CardHeader>
              <CardTitle className="font-heading text-xl">Predicted exam score</CardTitle>
              <CardDescription>
                {result ? "Based on the profile you entered." : "Fill in the profile, then press Predict."}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              {error != null && <ApiErrorAlert error={error} title="Could not predict" />}

              {result ? (
                <div className={cn("space-y-5 transition-opacity", stale && "opacity-60")}>
                  <ScoreGauge score={result.prediction.score} interval={result.prediction.interval} />
                  {result.prediction.interval && (
                    <p className="text-center text-sm text-muted-foreground">
                      Likely between{" "}
                      <span className="font-mono font-medium text-foreground">{result.prediction.interval.low.toFixed(0)}</span>{" "}
                      and{" "}
                      <span className="font-mono font-medium text-foreground">{result.prediction.interval.high.toFixed(0)}</span>{" "}
                      ({Math.round(result.prediction.interval.level * 100)}% of similar students)
                    </p>
                  )}
                  {stale && (
                    <Badge variant="outline" className="mx-auto flex">
                      Profile changed. Press Update to refresh.
                    </Badge>
                  )}
                  {result.prediction.edge_features.length > 0 && (
                    <div className="flex gap-2 rounded-lg bg-warning/10 p-3 text-sm text-warning">
                      <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
                      <p>
                        Less certain: {result.prediction.edge_features.map((f) => meta.numeric[f]?.label ?? f).join(", ")}{" "}
                        {result.prediction.edge_features.length === 1 ? "is" : "are"} at the edge of what the model has seen.
                      </p>
                    </div>
                  )}
                </div>
              ) : (
                <EmptyGauge />
              )}
            </CardContent>
          </Card>
        </section>
      </div>

      {result && (
        <>
          <TipList tips={result.prediction.tips} meta={meta} />
          <WhatIfPanel key={JSON.stringify(result.student)} meta={meta} student={result.student} baseScore={result.prediction.score} />
        </>
      )}
    </div>
  );
}

function EmptyGauge() {
  return (
    <div className="grid place-items-center py-10 text-center">
      <div className="font-heading text-6xl font-semibold text-muted-foreground/40">?</div>
      <p className="mt-3 max-w-xs text-sm text-muted-foreground">
        The score, a likely range, and personal tips will appear here.
      </p>
    </div>
  );
}
