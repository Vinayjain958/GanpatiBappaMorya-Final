import type { NextConfig } from "next";
import { resolveApiProxyTarget } from "./lib/config/apiProxyTarget";

// Server-only (not NEXT_PUBLIC_): where /api/v1/* is proxied to. In
// production the browser talks to the frontend's own origin and Next
// forwards to the FastAPI backend, so the HttpOnly refresh cookie is
// first-party on the frontend domain (and visible to proxy.ts).
const apiProxyTarget = resolveApiProxyTarget();

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
