"use client";

import { useId } from "react";

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import type { CategoricalSpec, NumericSpec } from "@/lib/api";
import { formatSpec } from "@/lib/format";
import { cn } from "@/lib/utils";

export function NumberField({
  spec,
  value,
  onChange,
  highlight,
  className,
}: {
  spec: NumericSpec;
  value: number;
  onChange: (value: number) => void;
  /** Marks the field, e.g. when the value is at the edge of the training data. */
  highlight?: boolean;
  className?: string;
}) {
  return (
    <div className={cn("space-y-3", className)}>
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-sm font-medium">{spec.label}</span>
        <span
          className={cn(
            "rounded-md bg-secondary px-2 py-0.5 font-mono text-sm tabular-nums",
            highlight && "bg-warning/15 text-warning",
          )}
        >
          {formatSpec(value, spec)}
        </span>
      </div>
      <Slider
        value={[value]}
        min={spec.min}
        max={spec.max}
        step={spec.step}
        thumbLabel={spec.label}
        thumbValueText={(v) => formatSpec(v, spec)}
        onValueChange={(v) => onChange(Array.isArray(v) ? v[0] : (v as number))}
      />
      <div className="flex justify-between font-mono text-[11px] text-muted-foreground tabular-nums">
        <span>{formatSpec(spec.min, spec)}</span>
        <span>{formatSpec(spec.max, spec)}</span>
      </div>
    </div>
  );
}

export function SelectField({
  spec,
  value,
  onChange,
  options,
  className,
}: {
  spec: CategoricalSpec;
  value: string;
  onChange: (value: string) => void;
  /** Override the option list (e.g. diet quality in a fixed order). */
  options?: string[];
  className?: string;
}) {
  const id = useId();
  return (
    <div className={cn("space-y-2", className)}>
      <label id={id} className="text-sm font-medium">
        {spec.label}
      </label>
      <Select value={value} onValueChange={(v) => v != null && onChange(String(v))}>
        <SelectTrigger aria-labelledby={id} className="w-full">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {(options ?? spec.options).map((option) => (
            <SelectItem key={option} value={option}>
              {option}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
