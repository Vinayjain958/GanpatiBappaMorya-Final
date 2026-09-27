import type { ContextStatus } from "@/types/api";

export type WeatherBadgeTone = "success" | "neutral" | "warning" | "danger" | "highlight";

const STATUS_LABELS: Record<ContextStatus, string> = {
  LIVE: "Live weather",
  CACHED: "Cached weather",
  STALE: "Weather may be out of date",
  MOCK: "Development weather",
  UNAVAILABLE: "Weather unavailable",
};

const STATUS_TONES: Record<ContextStatus, WeatherBadgeTone> = {
  LIVE: "success",
  CACHED: "neutral",
  STALE: "warning",
  MOCK: "highlight",
  UNAVAILABLE: "danger",
};

export function weatherStatusLabel(status: ContextStatus): string {
  return STATUS_LABELS[status];
}

export function weatherStatusTone(status: ContextStatus): WeatherBadgeTone {
  return STATUS_TONES[status];
}

export function formatWeatherValue(value: number | null, unit: string): string | null {
  if (value === null || !Number.isFinite(value)) return null;
  const formatted = Number.isInteger(value) ? String(value) : value.toFixed(1);
  return `${formatted}${unit}`;
}

export function formatWeatherTime(value: string | null): string | null {
  if (!value) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  return new Intl.DateTimeFormat(undefined, {
    hour: "numeric",
    minute: "2-digit",
    weekday: "short",
    day: "numeric",
    month: "short",
  }).format(parsed);
}
