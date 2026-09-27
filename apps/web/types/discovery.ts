import type { DiscoverySort } from "@/types/api";

export type BudgetOption = "any" | "low" | "mid" | "high";
export type DurationOption = "any" | "short" | "medium" | "long";
export type DiscoveryDataSource = "all" | "source" | "demo";

export interface DiscoveryState {
  q: string;
  category: string | null;
  budget: BudgetOption;
  duration: DurationOption;
  lat: number | null;
  lng: number | null;
  locationLabel: string | null;
  radiusKm: number | null;
  sort: DiscoverySort;
  dataSource: DiscoveryDataSource;
}

export const DEFAULT_DISCOVERY_STATE: DiscoveryState = {
  q: "",
  category: null,
  budget: "any",
  duration: "any",
  lat: null,
  lng: null,
  locationLabel: null,
  radiusKm: null,
  sort: "relevance",
  dataSource: "all",
};

const BUDGET_RANGES: Record<BudgetOption, { min?: number; max?: number }> = {
  any: {},
  low: { max: 499 },
  mid: { min: 500, max: 1500 },
  high: { min: 1501 },
};

const DURATION_RANGES: Record<DurationOption, { min?: number; max?: number }> = {
  any: {},
  short: { max: 59 },
  medium: { min: 60, max: 180 },
  long: { min: 181 },
};

export function budgetToPriceRange(budget: BudgetOption) {
  return BUDGET_RANGES[budget];
}

export function durationToMinutesRange(duration: DurationOption) {
  return DURATION_RANGES[duration];
}
