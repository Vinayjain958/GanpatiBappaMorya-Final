import type { NextConfig } from "next";

// Server-only (not NEXT_PUBLIC_): where /api/v1/* is proxied to. In
// production the browser talks to the frontend's own origin and Next
// forwards to the FastAPI backend, so the HttpOnly refresh cookie is
// first-party on the frontend domain (and visible to proxy.ts).
// Fallbacks: NEXT_PUBLIC_API_BASE_URL (if that was set instead), then the
// deployed Render backend when building on Vercel, then local dev.
const DEPLOYED_API_URL = "https://ganpatibappamorya-final.onrender.com";
const rawApiProxyTarget =
  [process.env.API_PROXY_TARGET, process.env.NEXT_PUBLIC_API_BASE_URL]
    .map((value) => (value ?? "").trim().replace(/\/+$/, ""))
    // Never proxy to a Vercel URL (that would be the frontend itself -> loop).
    .find((value) => value.length > 0 && !value.includes(".vercel.app")) ??
  (process.env.VERCEL ? DEPLOYED_API_URL : "http://localhost:8000");
const apiProxyTarget = /^https?:\/\//.test(rawApiProxyTarget) ? rawApiProxyTarget : `https://${rawApiProxyTarget}`;

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${apiProxyTarget}/api/v1/:path*`,
      },
    ];
  },
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "images.unsplash.com",
      },
      {
        protocol: "https",
        hostname: "upload.wikimedia.org",
      },
      {
        protocol: "https",
        hostname: "*.wikimedia.org",
      },
    ],
  },
};

export default nextConfig;
