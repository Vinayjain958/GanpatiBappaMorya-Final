/**
 * Browser-safe configuration. Only NEXT_PUBLIC_-prefixed variables may be
 * read here — anything server-only (API keys, secrets) must never be
 * imported into client components. See docs/AI_CONTEXT.md INV-5.
 */
import { resolveApiProxyTarget } from "@/lib/config/apiProxyTarget";

export const env = {
  // Production is ALWAYS same-origin (""): the browser calls /api/v1/* on the
  // frontend host and next.config.ts proxies it to the backend. This keeps the
  // HttpOnly refresh cookie first-party, so proxy.ts can see it — calling the
  // backend's own domain directly would store the cookie there instead and
  // every protected page would bounce to /login. NEXT_PUBLIC_API_BASE_URL is
  // only honored in local development (and as a proxy target fallback).
  // Server-side rendering has no origin to resolve a relative URL against,
  // so it calls the backend directly (only public, cookie-less reads happen
  // there — e.g. the /discover/[id] detail page).
  apiBaseUrl:
    process.env.NODE_ENV !== "production"
      ? (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000")
      : typeof window === "undefined"
        ? resolveApiProxyTarget()
        : "",
  appName: process.env.NEXT_PUBLIC_APP_NAME ?? "LocaLens",
  appVersion: process.env.NEXT_PUBLIC_APP_VERSION ?? "0.1.0",
  // No-API-key OSM-derived vector style by default (OpenFreeMap). Keep
  // this the single place the style URL is read from — see
  // lib/config/map.ts and docs/DECISIONS.md ADR-025.
  mapStyleUrl: process.env.NEXT_PUBLIC_MAP_STYLE_URL ?? "https://tiles.openfreemap.org/styles/liberty",
} as const;
