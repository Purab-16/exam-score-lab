import { ArrowRight, PartyPopper } from "lucide-react";

import type { Meta, Tip } from "@/lib/api";
import { formatValue } from "@/lib/format";

export function TipList({ tips, meta }: { tips: Tip[]; meta: Meta }) {
  const maxGain = Math.max(...tips.map((t) => t.gain), 1);

  return (
    <section aria-labelledby="tips-title" className="space-y-4">
      <div>
        <h2 id="tips-title" className="font-heading text-2xl font-semibold tracking-tight">
          Personal tips
        </h2>
        <p className="text-sm text-muted-foreground">
          Habits pulling this score down, and what one realistic change could add.
        </p>
      </div>

      {tips.length === 0 ? (
        <div className="flex items-center gap-3 rounded-2xl border bg-card p-5 text-sm">
          <PartyPopper className="size-5 text-success" aria-hidden />
          No changeable habit is pulling this score below average. Keep it up!
        </div>
      ) : (
        <ol className="grid gap-4 md:grid-cols-3">
          {tips.map((tip, i) => {
            const unit = meta.numeric[tip.feature]?.unit ?? tip.unit.trim();
            return (
              <li key={tip.feature} className="flex flex-col gap-4 rounded-2xl border bg-card p-5">
                <div className="flex items-start justify-between gap-3">
                  <span className="font-heading text-3xl leading-none font-semibold text-muted-foreground/50">{i + 1}</span>
                  <span className="rounded-full bg-success/12 px-2.5 py-1 font-mono text-sm font-semibold text-success tabular-nums">
                    +{tip.gain.toFixed(1)} pts
                  </span>
                </div>
                <p className="font-medium text-pretty">{tip.label}</p>
                <div className="mt-auto space-y-3">
                  <div className="flex items-center gap-2 font-mono text-sm tabular-nums">
                    <span className="rounded bg-muted px-1.5 py-0.5">{formatValue(tip.current, unit)}</span>
                    <ArrowRight className="size-3.5 text-muted-foreground" aria-label="to" />
                    <span className="rounded bg-accent px-1.5 py-0.5 text-accent-foreground">{formatValue(tip.suggested, unit)}</span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-muted" aria-hidden>
                    <div className="h-full rounded-full bg-success" style={{ width: `${(tip.gain / maxGain) * 100}%` }} />
                  </div>
                </div>
              </li>
            );
          })}
        </ol>
      )}
      {tips.length > 0 && (
        <p className="text-xs text-muted-foreground">
          Estimates come from the model and show association, not guaranteed cause and effect.
        </p>
      )}
    </section>
  );
}
