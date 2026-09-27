import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Optimistic, presence-only route guard.
 *
 * This is NOT the authorization layer — it only checks whether a refresh
 * cookie exists, never verifies or decodes it (no JWT secret lives here).
 * The FastAPI backend remains the sole authority: every mutating request
 * is independently checked there via get_current_user/require_role/
 * ownership dependencies (apps/api/src/core/deps.py). Missing cookie ->
 * redirect to /login as a UX nicety, to avoid flashing a protected page
 * that immediately 401s. A present cookie proves nothing on its own
 * (could be expired/revoked); the page's own AuthContext bootstrap
 * catches that case and the API rejects unauthorized calls regardless.
 */
const PROTECTED_PREFIXES = ["/trip", "/saved", "/provider", "/contribute"];

function hasRefreshCookie(request: NextRequest): boolean {
  return request.cookies.getAll().some((cookie) => cookie.name.endsWith("localens_refresh"));
}

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const isProtected = PROTECTED_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );

  if (isProtected && !hasRefreshCookie(request)) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/trip/:path*", "/saved/:path*", "/provider/:path*", "/contribute/:path*"],
};
