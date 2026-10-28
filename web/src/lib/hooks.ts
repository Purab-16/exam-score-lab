"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";

import { fetcher, type Insights, type Meta } from "@/lib/api";

// Model info and dataset summaries only change when the model is retrained
const STATIC = { revalidateOnFocus: false, revalidateIfStale: false, shouldRetryOnError: false };

export const useMeta = () => useSWR<Meta>("/meta", fetcher, STATIC);

export const useInsights = () => useSWR<Insights>("/insights", fetcher, STATIC);

export function useDebounced<T>(value: T, delayMs: number) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(id);
  }, [value, delayMs]);
  return debounced;
}
