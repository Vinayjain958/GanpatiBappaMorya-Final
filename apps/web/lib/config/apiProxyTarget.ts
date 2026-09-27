// Where the FastAPI backend actually lives. Used by next.config.ts (the
// /api/v1/* rewrite target) and by lib/config/env.ts for server-side
// rendering, which can't use the browser's same-origin relative URLs.
// Fallbacks: API_PROXY_TARGET, then NEXT_PUBLIC_API_BASE_URL (if that was set
// instead), then the deployed Render backend when running on Vercel, then
// local dev.
const DEPLOYED_API_URL = "https://ganpatibappamorya-final.onrender.com";

export function resolveApiProxyTarget(): string {
  const raw =
    [process.env.API_PROXY_TARGET, process.env.NEXT_PUBLIC_API_BASE_URL]
      .map((value) => (value ?? "").trim().replace(/\/+$/, ""))
      // Never proxy to a Vercel URL (that would be the frontend itself -> loop).
      .find((value) => value.length > 0 && !value.includes(".vercel.app")) ??
    (process.env.VERCEL ? DEPLOYED_API_URL : "http://localhost:8000");
  return /^https?:\/\//.test(raw) ? raw : `https://${raw}`;
}
