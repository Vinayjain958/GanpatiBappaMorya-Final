"use client";

import { useCallback, useRef, useState } from "react";
import { searchLocation } from "@/lib/api/location";
import type { LocationSearchResult } from "@/types/location";

export type LocationSearchStatus = "idle" | "loading" | "success" | "error";

/**
 * Wraps the backend Nominatim-backed search endpoint. `search()` is only
 * ever called from an explicit submit (a button/form, never onChange) —
 * there is deliberately no autocomplete/type-ahead here, matching
 * Nominatim's usage policy (docs/DECISIONS.md ADR-022).
 */
export function useLocationSearch() {
  const [status, setStatus] = useState<LocationSearchStatus>("idle");
  const [results, setResults] = useState<LocationSearchResult[]>([]);
  const controllerRef = useRef<AbortController | null>(null);

  const search = useCallback(async (query: string) => {
    const trimmed = query.trim();
    if (!trimmed) return;

    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;

    setStatus("loading");
    try {
      const response = await searchLocation(trimmed, controller.signal);
      setResults(response.items);
      setStatus("success");
    } catch {
      if (!controller.signal.aborted) setStatus("error");
    }
  }, []);

  const clear = useCallback(() => {
    setResults([]);
    setStatus("idle");
  }, []);

  return { status, results, search, clear };
}
