"use client";

import { useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis,
} from "recharts";

import { ApiErrorAlert } from "@/components/api-state";
import { SelectField } from "@/components/fields";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { Insights, Meta } from "@/lib/api";
import { useInsights, useMeta } from "@/lib/hooks";
import { cn } from "@/lib/utils";

const AXIS = { fontSize: 11, fill: "var(--muted-foreground)", fontFamily: "var(--font-geist-mono)" };
const GRID = { stroke: "var(--border)", strokeDasharray: "3 3" };

function ChartTooltip({ active, payload, format }: {
  active?: boolean;
  payload?: { payload: Record<string, unknown> }[];
  format: (p: Record<string, unknown>) => React.ReactNode;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg bg-popover px-3 py-2 font-mono text-xs text-popover-foreground shadow-md ring-1 ring-foreground/10">
      {format(payload[0].payload)}
    </div>
  );
}

function ChartCard({ title, description, children, action, className }: {
  title: string; description: string; children: React.ReactNode; action?: React.ReactNode; className?: string;
}) {
  return (
    <Card className={cn("rounded-2xl", className)}>
      <CardHeader className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <CardTitle className="font-heading text-lg">{title}</CardTitle>
          <CardDescription>{description}</CardDescription>
        </div>
        {action}
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

export function InsightsDashboard() {
  const { data: insights, error } = useInsights();
  const { data: meta, error: metaError } = useMeta();

  if (error || metaError) return <ApiErrorAlert error={error ?? metaError} />;
  if (!insights || !meta) {
    return (
      <div className="grid gap-6 md:grid-cols-2" aria-busy="true" aria-label="Loading charts">
        {Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-80 rounded-2xl" />)}
      </div>
    );
  }
  return <Dashboard insights={insights} meta={meta} />;
}

function Dashboard({ insights, meta }: { insights: Insights; meta: Meta }) {
  const numericNames = Object.keys(meta.numeric);
  const categoricalNames = Object.keys(meta.categorical);
  const [scatterFeature, setScatterFeature] = useState("study_hours_per_day");
  const [categoryFeature, setCategoryFeature] = useState("diet_quality");

  const labelToName = (label: string, specs: Record<string, { label: string }>) =>
    Object.keys(specs).find((k) => specs[k].label === label) ?? label;

  const histogram = insights.histogram.map((b) => ({ ...b, bin: `${b.start}–${b.end}` }));
  const categoryOrder = categoryFeature === "diet_quality" ? meta.diet_order : null;
  const categoryData = [...insights.category_means[categoryFeature]].sort((a, b) =>
    categoryOrder ? categoryOrder.indexOf(a.value) - categoryOrder.indexOf(b.value) : b.mean - a.mean,
  );
  const scatterSpec = meta.numeric[scatterFeature];
  const test = meta.model.test_metrics;

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Students" value={insights.count.toLocaleString()} />
        <Stat label="Mean score" value={insights.summary.mean.toFixed(1)} />
        <Stat label="Median score" value={insights.summary.median.toFixed(1)} />
        <Stat label="Spread (std)" value={`±${insights.summary.std.toFixed(1)}`} />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <ChartCard title="Score distribution" description="How many students fall in each 5-point band.">
          <div className="h-72">
            <ResponsiveContainer>
              <BarChart data={histogram} margin={{ left: -16, right: 8 }}>
                <CartesianGrid vertical={false} {...GRID} />
                <XAxis dataKey="start" tick={AXIS} tickLine={false} axisLine={false} interval={3} />
                <YAxis tick={AXIS} tickLine={false} axisLine={false} allowDecimals={false} />
                <Tooltip cursor={{ fill: "var(--muted)" }} content={<ChartTooltip format={(p) => `${p.bin}: ${p.count} students`} />} />
                <Bar dataKey="count" fill="var(--chart-1)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </ChartCard>

        <ChartCard title="What moves the score" description="Correlation of each habit with the exam score (r, from −1 to 1).">
          <div className="h-72">
            <ResponsiveContainer>
              <BarChart data={insights.correlations} layout="vertical" margin={{ left: 8, right: 16 }}>
                <CartesianGrid horizontal={false} {...GRID} />
                <XAxis type="number" domain={[-1, 1]} tick={AXIS} tickLine={false} axisLine={false} />
                <YAxis type="category" dataKey="label" width={160} tick={{ ...AXIS, fontFamily: "var(--font-geist-sans)" }} tickLine={false} axisLine={false} />
                <ReferenceLine x={0} stroke="var(--foreground)" strokeOpacity={0.3} />
                <Tooltip cursor={{ fill: "var(--muted)" }} content={<ChartTooltip format={(p) => `${p.label}: r = ${Number(p.r).toFixed(2)}`} />} />
                <Bar dataKey="r" radius={4}>
                  {insights.correlations.map((c) => (
                    <Cell key={c.feature} fill={c.r >= 0 ? "var(--chart-1)" : "var(--chart-3)"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </ChartCard>

        <ChartCard
          title="Habit vs score"
          description="Each dot is one student."
          action={
            <SelectField
              className="w-48"
              spec={{ label: "Habit", options: numericNames.map((n) => meta.numeric[n].label) }}
              value={scatterSpec.label}
              onChange={(label) => setScatterFeature(labelToName(label, meta.numeric))}
            />
          }
        >
          <div className="h-72">
            <ResponsiveContainer>
              <ScatterChart margin={{ left: -16, right: 8 }}>
                <CartesianGrid {...GRID} />
                <XAxis type="number" dataKey="x" name={scatterSpec.label} domain={[scatterSpec.min, scatterSpec.max]} tick={AXIS} tickLine={false} axisLine={false} />
                <YAxis type="number" dataKey="y" name="Score" domain={[0, 100]} tick={AXIS} tickLine={false} axisLine={false} />
                <Tooltip content={<ChartTooltip format={(p) => `${scatterSpec.label} ${p.x}${scatterSpec.unit === "%" || scatterSpec.unit === "h" ? scatterSpec.unit : ""} · score ${p.y}`} />} />
                <Scatter data={insights.scatter[scatterFeature]} fill="var(--chart-1)" fillOpacity={0.45} shape="circle" />
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        </ChartCard>

        <ChartCard
          title="Average score by group"
          description="Dashed line is the overall mean."
          action={
            <SelectField
              className="w-48"
              spec={{ label: "Group by", options: categoricalNames.map((n) => meta.categorical[n].label) }}
              value={meta.categorical[categoryFeature].label}
              onChange={(label) => setCategoryFeature(labelToName(label, meta.categorical))}
            />
          }
        >
          <div className="h-72">
            <ResponsiveContainer>
              <BarChart data={categoryData} margin={{ left: -16, right: 8 }}>
                <CartesianGrid vertical={false} {...GRID} />
                <XAxis dataKey="value" tick={{ ...AXIS, fontFamily: "var(--font-geist-sans)" }} tickLine={false} axisLine={false} />
                <YAxis domain={[0, 100]} tick={AXIS} tickLine={false} axisLine={false} />
                <ReferenceLine y={insights.summary.mean} stroke="var(--chart-2)" strokeWidth={2} strokeDasharray="4 4" />
                <Tooltip cursor={{ fill: "var(--muted)" }} content={<ChartTooltip format={(p) => `${p.value}: ${Number(p.mean).toFixed(1)} (${p.count} students)`} />} />
                <Bar dataKey="mean" fill="var(--chart-4)" radius={[4, 4, 0, 0]} maxBarSize={64} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </ChartCard>

        <ChartCard
          className="lg:col-span-2"
          title="Predicted vs actual"
          description={`Dots on the dashed line are perfect predictions. The saved model was trained on these rows, so this view is optimistic${test ? `. On unseen students it is off by ${test.rmse.toFixed(1)} points on average (RMSE)` : ""}.`}
        >
          <div className="h-80">
            <ResponsiveContainer>
              <ScatterChart margin={{ left: -16, right: 8 }}>
                <CartesianGrid {...GRID} />
                <XAxis type="number" dataKey="actual" name="Actual" domain={[0, 100]} tick={AXIS} tickLine={false} axisLine={false} />
                <YAxis type="number" dataKey="predicted" name="Predicted" domain={[0, 100]} tick={AXIS} tickLine={false} axisLine={false} />
                <ReferenceLine segment={[{ x: 0, y: 0 }, { x: 100, y: 100 }]} stroke="var(--foreground)" strokeOpacity={0.4} strokeDasharray="5 5" />
                <Tooltip content={<ChartTooltip format={(p) => `actual ${p.actual} · predicted ${p.predicted}`} />} />
                <Scatter data={insights.predicted_vs_actual} fill="var(--chart-1)" fillOpacity={0.4} />
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        </ChartCard>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border bg-card p-5">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="mt-1 font-heading text-3xl font-semibold tabular-nums">{value}</p>
    </div>
  );
}
