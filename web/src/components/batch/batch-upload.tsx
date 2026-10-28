"use client";

import { AlertTriangle, Download, FileSpreadsheet, Loader2, Upload, X } from "lucide-react";
import { useState } from "react";

import { ApiErrorAlert } from "@/components/api-state";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { predictBatch, templateUrl, type BatchResult } from "@/lib/api";
import { toCsv } from "@/lib/csv";
import { scoreBand } from "@/lib/format";
import { useMeta } from "@/lib/hooks";
import { cn } from "@/lib/utils";

const PREVIEW_ROWS = 50;
// Columns shown first in the preview table, when present
const PREVIEW_COLUMNS = ["student_id", "predicted_score", "range_low", "range_high", "study_hours_per_day", "attendance_percentage", "sleep_hours"];

export function BatchUpload() {
  const { data: meta } = useMeta();
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<BatchResult | null>(null);
  const [error, setError] = useState<unknown>(null);

  async function upload(f: File) {
    setFile(f);
    setResult(null);
    setError(null);
    setLoading(true);
    try {
      setResult(await predictBatch(f));
    } catch (e) {
      setError(e);
    } finally {
      setLoading(false);
    }
  }

  function download() {
    if (!result) return;
    const url = URL.createObjectURL(new Blob([toCsv(result.columns, result.rows)], { type: "text/csv" }));
    const a = Object.assign(document.createElement("a"), { href: url, download: "predictions.csv" });
    a.click();
    URL.revokeObjectURL(url);
  }

  const columns = result ? [...PREVIEW_COLUMNS.filter((c) => result.columns.includes(c))] : [];

  return (
    <div className="space-y-8">
      <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <label
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            const f = e.dataTransfer.files[0];
            if (f) upload(f);
          }}
          className={cn(
            "ruled flex min-h-56 cursor-pointer flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed bg-paper p-8 text-center transition-colors",
            "focus-within:border-primary hover:border-primary/60",
            dragging && "border-primary bg-accent",
          )}
        >
          <input
            type="file"
            accept=".csv,text/csv"
            className="sr-only"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) upload(f);
              e.target.value = "";
            }}
          />
          <span className="grid size-12 place-items-center rounded-full bg-card shadow-sm ring-1 ring-foreground/10">
            {loading ? <Loader2 className="size-5 animate-spin text-primary" aria-hidden /> : <Upload className="size-5 text-primary" aria-hidden />}
          </span>
          <span className="font-heading text-lg font-semibold">
            {loading ? "Checking and predicting…" : "Drop a CSV here, or click to choose"}
          </span>
          <span className="text-sm text-muted-foreground">
            Up to {meta?.max_batch_rows.toLocaleString() ?? "10,000"} rows · 5 MB
          </span>
          {file && !loading && (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-card px-3 py-1 text-xs ring-1 ring-foreground/10">
              <FileSpreadsheet className="size-3.5" aria-hidden /> {file.name}
            </span>
          )}
        </label>

        <Card className="rounded-2xl">
          <CardContent className="space-y-4 text-sm">
            <h2 className="font-heading text-lg font-semibold">File format</h2>
            <p className="text-muted-foreground">
              One row per student with these columns. Extra columns such as <code className="font-mono">student_id</code> are kept.
            </p>
            <div className="flex flex-wrap gap-1.5">
              {(meta?.features ?? []).map((f) => (
                <code key={f} className="rounded bg-muted px-1.5 py-0.5 font-mono text-[11px]">{f}</code>
              ))}
            </div>
            <p className="text-muted-foreground">Empty cells are filled the same way as during training.</p>
            <a href={templateUrl} className={cn(buttonVariants({ variant: "outline" }), "w-full")} download>
              <Download data-icon="inline-start" aria-hidden /> Download template CSV
            </a>
          </CardContent>
        </Card>
      </div>

      {error != null && <ApiErrorAlert error={error} title="The file has problems" />}

      {result && (
        <section aria-labelledby="results-title" className="space-y-5">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <h2 id="results-title" className="font-heading text-2xl font-semibold tracking-tight">Results</h2>
            <div className="flex gap-2">
              <Button variant="ghost" size="sm" onClick={() => { setResult(null); setFile(null); }}>
                <X data-icon="inline-start" aria-hidden /> Clear
              </Button>
              <Button onClick={download}>
                <Download data-icon="inline-start" aria-hidden /> Download predictions
              </Button>
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-3">
            <Stat label="Students" value={result.summary.count.toLocaleString()} />
            <Stat label="Average predicted score" value={result.summary.mean_score.toFixed(1)} />
            <Stat label="Predicted below 50" value={result.summary.below_50.toLocaleString()} tone={result.summary.below_50 ? "text-danger" : undefined} />
          </div>

          {result.warnings.length > 0 && (
            <div className="space-y-1.5 rounded-xl bg-warning/10 p-4 text-sm text-warning">
              {result.warnings.map((w) => (
                <p key={w} className="flex gap-2"><AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden /> {w}</p>
              ))}
            </div>
          )}

          <Card className="rounded-2xl py-0">
            <Table>
              <TableHeader>
                <TableRow>
                  {columns.map((c) => (
                    <TableHead key={c} className="font-mono text-xs">{c}</TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {result.rows.slice(0, PREVIEW_ROWS).map((row, i) => (
                  <TableRow key={i}>
                    {columns.map((c) => (
                      <TableCell key={c} className={cn("font-mono tabular-nums", c === "predicted_score" && cn("font-semibold", scoreBand(Number(row[c])).tone))}>
                        {row[c] ?? "–"}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
          {result.rows.length > PREVIEW_ROWS && (
            <p className="text-sm text-muted-foreground">
              Showing the first {PREVIEW_ROWS} of {result.rows.length.toLocaleString()} rows. Download the CSV for all columns and rows.
            </p>
          )}
        </section>
      )}
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="rounded-2xl border bg-card p-5">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className={cn("mt-1 font-heading text-3xl font-semibold tabular-nums", tone)}>{value}</p>
    </div>
  );
}
