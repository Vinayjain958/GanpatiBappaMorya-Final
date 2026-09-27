/**
 * In-memory-only access token holder.
 *
 * Deliberately NOT backed by localStorage/sessionStorage/IndexedDB — a
 * page reload always starts with no token and relies on the HttpOnly
 * refresh cookie (via AuthProvider's bootstrap refresh) to get a new
 * one. This is a plain module-level store (not a React hook) so the
 * typed API client (lib/api/client.ts) can read/write it without
 * depending on React or creating a circular import with AuthContext.
 */

let accessToken: string | null = null;
type Listener = (token: string | null) => void;
const listeners = new Set<Listener>();

export function getAccessToken(): string | null {
  return accessToken;
}

export function setAccessToken(token: string | null): void {
  accessToken = token;
  for (const listener of listeners) listener(token);
}

export function subscribeToAccessToken(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
