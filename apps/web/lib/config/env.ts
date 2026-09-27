/**
 * Browser-safe configuration. Only NEXT_PUBLIC_-prefixed variables may be
 * read here — anything server-only (API keys, secrets) must never be
 * imported into client components. See docs/AI_CONTEXT.md INV-5.
 */
export const env = {
  apiBaseUrl: process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000",
  appName: process.env.NEXT_PUBLIC_APP_NAME ?? "LocaLens",
  appVersion: process.env.NEXT_PUBLIC_APP_VERSION ?? "0.1.0",
  // No-API-key OSM-derived vector style by default (OpenFreeMap). Keep
  // this the single place the style URL is read from — see
  // lib/config/map.ts and docs/DECISIONS.md ADR-025.
  mapStyleUrl: process.env.NEXT_PUBLIC_MAP_STYLE_URL ?? "https://tiles.openfreemap.org/styles/liberty",
} as const;
