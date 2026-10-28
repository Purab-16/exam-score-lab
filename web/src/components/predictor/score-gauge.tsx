import type { Interval } from "@/lib/api";
import { scoreBand } from "@/lib/format";
import { cn } from "@/lib/utils";

// Semicircle from 180° (score 0) to 0° (score 100)
const CX = 120;
const CY = 120;
const R = 96;

function point(score: number) {
  const angle = Math.PI * (1 - Math.min(Math.max(score, 0), 100) / 100);
  return [CX + R * Math.cos(angle), CY - R * Math.sin(angle)] as const;
}

function arc(from: number, to: number) {
  const [x1, y1] = point(from);
  const [x2, y2] = point(to);
  return `M ${x1} ${y1} A ${R} ${R} 0 0 1 ${x2} ${y2}`;
}

export function ScoreGauge({ score, interval, compareTo }: { score: number; interval: Interval | null; compareTo?: number }) {
  const band = scoreBand(score);
  const [mx, my] = compareTo != null ? point(compareTo) : [0, 0];

  return (
    <figure className="relative mx-auto w-full max-w-[300px]">
      <svg viewBox="0 0 240 142" className="w-full" role="img"
        aria-label={`Predicted score ${score.toFixed(1)} out of 100${interval ? `, likely between ${interval.low.toFixed(0)} and ${interval.high.toFixed(0)}` : ""}`}>
        <path d={arc(0, 100)} className="stroke-muted" strokeWidth={18} fill="none" strokeLinecap="round" />
        {interval && (
          <path d={arc(interval.low, interval.high)} className="stroke-primary/25" strokeWidth={18} fill="none" />
        )}
        <path
          d={arc(0, Math.max(score, 0.5))}
          className="stroke-primary transition-all duration-700 ease-out"
          strokeWidth={8}
          fill="none"
          strokeLinecap="round"
        />
        {compareTo != null && (
          <circle cx={mx} cy={my} r={5} className="fill-background stroke-foreground/60" strokeWidth={2} />
        )}
        {[0, 100].map((tick) => {
          const [x, y] = point(tick);
          return (
            <text key={tick} x={x} y={y + 19} textAnchor="middle" className="fill-muted-foreground font-mono text-[9px]">
              {tick}
            </text>
          );
        })}
      </svg>
      <figcaption className="absolute inset-x-0 bottom-3 text-center">
        <div className="font-heading text-5xl leading-none font-semibold tabular-nums">{score.toFixed(1)}</div>
        <div className={cn("mt-1 text-sm font-medium", band.tone)}>{band.label}</div>
      </figcaption>
    </figure>
  );
}
