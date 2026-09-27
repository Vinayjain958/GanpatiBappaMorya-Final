"use client";

import { useEffect, useState } from "react";
import { listExperiences } from "@/lib/api/experiences";
import { mapApiExperienceToUi } from "@/lib/api/experienceAdapter";
import { budgetToPriceRange, durationToMinutesRange, type DiscoveryState } from "@/types/discovery";
import type { Experience } from "@/types/experience";

export type DiscoveryLoadState = "loading" | "success" | "error";

const PAGE_SIZE = 24;

/**
 * The single place discovery search parameters turn into an API call —
 * never duplicated across components. Server-side filtering/sorting
 * (category, price, duration, radius, sort) is authoritative; this hook
 * just orchestrates the request/response and exposes typed UI state.
 */
export function useExperienceDiscovery(state: DiscoveryState, reloadToken: number) {
  const [experiences, setExperiences] = useState<Experience[]>([]);
  const [total, setTotal] = useState(0);
  const [status, setStatus] = useState<DiscoveryLoadState>("loading");

  useEffect(() => {
    const controller = new AbortController();
    const priceRange = budgetToPriceRange(state.budget);
    const durationRange = durationToMinutesRange(state.duration);

    listExperiences(
      {
        q: state.q || undefined,
        category: state.category ?? undefined,
        min_price: priceRange.min,
        max_price: priceRange.max,
        min_duration_minutes: durationRange.min,
        max_duration_minutes: durationRange.max,
        is_synthetic: state.dataSource === "all" ? undefined : state.dataSource === "demo",
        lat: state.lat ?? undefined,
        lng: state.lng ?? undefined,
        radius_km: state.lat != null && state.radiusKm != null ? state.radiusKm : undefined,
        sort: state.sort,
        limit: PAGE_SIZE,
        offset: 0,
      },
      controller.signal,
    )
      .then((response) => {
        const origin = state.lat != null && state.lng != null ? { lat: state.lat, lng: state.lng } : null;
        setExperiences(response.items.map((item) => mapApiExperienceToUi(item, origin)));
        setTotal(response.total);
        setStatus("success");
      })
      .catch(() => {
        if (!controller.signal.aborted) setStatus("error");
      });

    return () => controller.abort();
  }, [
    state.q,
    state.category,
    state.budget,
    state.duration,
    state.dataSource,
    state.lat,
    state.lng,
    state.radiusKm,
    state.sort,
    reloadToken,
  ]);

  return { experiences, total, status };
}
