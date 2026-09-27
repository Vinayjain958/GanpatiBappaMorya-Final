"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { ApiError } from "@/lib/api/client";
import { getMe, login as apiLogin, logout as apiLogout, refreshSession, registerAccount } from "@/lib/api/auth";
import { setAccessToken } from "@/lib/auth/tokenStore";
import type { AuthUser, LoginPayload, ProviderProfileSummary, RegisterPayload, TravelerProfile } from "@/types/auth";

interface AuthContextValue {
  user: AuthUser | null;
  traveler: TravelerProfile | null;
  provider: ProviderProfileSummary | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (payload: LoginPayload) => Promise<AuthUser>;
  register: (payload: RegisterPayload) => Promise<AuthUser>;
  logout: () => Promise<void>;
  refreshSession: () => Promise<boolean>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

/**
 * Owns the client-side auth state. The access token itself is never
 * stored in this component's state — it lives only in
 * lib/auth/tokenStore.ts (module memory) so it can't leak into
 * localStorage/sessionStorage via a devtools inspection of React state,
 * and so lib/api/client.ts can read it without a React dependency.
 * This context just tracks *who* is signed in for rendering purposes.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [traveler, setTraveler] = useState<TravelerProfile | null>(null);
  const [provider, setProvider] = useState<ProviderProfileSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // React Strict Mode (dev only) runs this effect mount -> cleanup ->
    // mount again. A `cancelled` flag set by the first cleanup must not
    // suppress the *second* run's own completion — each effect
    // invocation needs its own independent cancellation flag, not one
    // shared via a `bootstrapped` ref that made the second invocation a
    // no-op while the first invocation's in-flight request was the only
    // one that could ever set isLoading, and that one always saw
    // cancelled=true by the time it resolved. Net effect: isLoading got
    // stuck true forever on every fresh full-page load in dev.
    let cancelled = false;

    async function bootstrap() {
      try {
        const session = await refreshSession();
        if (cancelled) return;
        setAccessToken(session.access_token);
        setUser(session.user);
        setTraveler(session.traveler);
        setProvider(session.provider);
      } catch {
        // No valid refresh cookie — a normal signed-out visit, not an error.
        if (!cancelled) {
          setAccessToken(null);
          setUser(null);
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    void bootstrap();
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (payload: LoginPayload) => {
    const session = await apiLogin(payload);
    setAccessToken(session.access_token);
    setUser(session.user);
    setTraveler(session.traveler);
    setProvider(session.provider);
    return session.user;
  }, []);

  const register = useCallback(async (payload: RegisterPayload) => {
    const session = await registerAccount(payload);
    setAccessToken(session.access_token);
    setUser(session.user);
    setTraveler(session.traveler);
    setProvider(session.provider);
    return session.user;
  }, []);

  const logout = useCallback(async () => {
    try {
      await apiLogout();
    } catch {
      // Best-effort — clear local state regardless of network outcome.
    } finally {
      setAccessToken(null);
      setUser(null);
      setTraveler(null);
      setProvider(null);
    }
  }, []);

  const refresh = useCallback(async () => {
    try {
      const session = await refreshSession();
      setAccessToken(session.access_token);
      setUser(session.user);
      setTraveler(session.traveler);
      setProvider(session.provider);
      return true;
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        setAccessToken(null);
        setUser(null);
        setTraveler(null);
        setProvider(null);
      }
      return false;
    }
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      traveler,
      provider,
      isAuthenticated: user !== null,
      isLoading,
      login,
      register,
      logout,
      refreshSession: refresh,
    }),
    [user, traveler, provider, isLoading, login, register, logout, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}

/** Convenience helper that also fetches the /auth/me detail — used
 * where fresher data than the auth-response snapshot is useful. */
export async function fetchCurrentUser() {
  return getMe();
}
