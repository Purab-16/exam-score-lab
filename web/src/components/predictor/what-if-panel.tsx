"use client";

import { Loader2, RotateCcw } from "lucide-react";
import { useMemo, useState } from "react";
import useSWR from "swr";

import { ApiErrorAlert } from "@/components/api-state";
import { NumberField, SelectField } from "@/components/fields";
import { ScoreGauge } from "@/components/predictor/score-gauge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { whatIf, type Meta, type Student, type WhatIfResult } from "@/lib/api";
import { useDebounced } from "@/lib/hooks";
import { cn } from "@/lib/utils";

export function WhatIfPanel({ meta, student, baseScore }: { meta: Meta; student: Student; baseScore: number }) {
  const [draft, setDraft] = useState<Student>(student);

  const changes = useMemo(() => {
    const out: Partial<Student> = {};
    for (const { feature } of meta.habits) {
      if (draft[feature] !== student[feature]) (out as Record<string, unknown>)[feature] = draft[feature];
    }
    return out;
  }, [draft, student, meta.habits]);

  const debouncedChanges = useDebounced(changes, 250);
  const hasChanges = Object.keys(debouncedChanges).length > 0;

  // SWR keys the request on the changes, drops stale responses and keeps the last result while loading
  const { data: result, error, isValidating: loading } = useSWR<WhatIfResult>(
    hasChanges ? ["what-if", JSON.stringify(student), JSON.stringify(debouncedChanges)] : null,
    () => whatIf(student, debouncedChanges),
    { keepPreviousData: true, revalidateOnFocus: false, shouldRetryOnError: false },
  );

  const newScore = hasChanges && result ? result.new_score : baseScore;
  const delta = newScore - baseScore;

  return (
    <section aria-labelledby="whatif-title" className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 id="whatif-title" className="font-heading text-2xl font-semibold tracking-tight">
            What-if simulator
          </h2>
          <p className="text-sm text-muted-foreground">Move the sliders to see how changing habits could shift the score.</p>
        </div>
        <Button variant="ghost" size="sm" onClick={() => setDraft(student)} disabled={!Object.keys(changes).length}>
          <RotateCcw data-icon="inline-start" aria-hidden /> Reset
        </Button>
      </div>

      <Card className="rounded-2xl">
        <CardContent className="grid gap-8 py-2 lg:grid-cols-[1.5fr_1fr]">
          <div className="grid gap-x-8 gap-y-7 sm:grid-cols-2">
            {meta.habits.map(({ feature }) =>
              meta.numeric[feature] ? (
                <NumberField
                  key={feature}
                  spec={meta.numeric[feature]}
                  value={draft[feature] as number}
                  onChange={(v) => setDraft((d) => ({ ...d, [feature]: v }))}
                />
              ) : (
                <SelectField
                  key={feature}
                  spec={meta.categorical[feature]}
                  value={draft[feature] as string}
                  options={feature === "diet_quality" ? meta.diet_order : undefined}
                  onChange={(v) => setDraft((d) => ({ ...d, [feature]: v }))}
                />
              ),
            )}
          </div>

          <div className="flex flex-col items-center justify-center gap-4 rounded-xl bg-paper p-5" aria-live="polite">
            <ScoreGauge score={newScore} interval={hasChanges ? result?.interval ?? null : null} compareTo={hasChanges ? baseScore : undefined} />
            <div className="flex items-center gap-3 font-mono text-sm tabular-nums">
              <span className="text-muted-foreground">was {baseScore.toFixed(1)}</span>
              <span
                className={cn(
                  "rounded-full px-2.5 py-1 font-semibold",
                  !hasChanges || Math.abs(delta) < 0.05
                    ? "bg-muted text-muted-foreground"
                    : delta > 0
                      ? "bg-success/12 text-success"
                      : "bg-danger/12 text-danger",
                )}
              >
                {delta >= 0 ? "+" : ""}
                {delta.toFixed(1)}
              </span>
              {hasChanges && loading && <Loader2 className="size-4 animate-spin text-muted-foreground" aria-label="Updating" />}
            </div>
            {error != null && <ApiErrorAlert error={error} title="Could not run what-if" />}
          </div>
        </CardContent>
      </Card>
    </section>
  );
}
