import { apiClient } from "@/lib/api/client";
import type { AuthResponse, LoginPayload, MeResponse, RegisterPayload } from "@/types/auth";

export function registerAccount(payload: RegisterPayload) {
  return apiClient.post<AuthResponse>("/api/v1/auth/register", payload);
}

export function login(payload: LoginPayload) {
  return apiClient.post<AuthResponse>("/api/v1/auth/login", payload);
}

/** Not used directly by most call sites — lib/api/client.ts calls the
 * endpoint itself for the automatic 401 retry. Exposed here for
 * AuthProvider's explicit startup bootstrap call. */
export function refreshSession() {
  return apiClient.post<AuthResponse>("/api/v1/auth/refresh");
}

export function logout() {
  return apiClient.post<void>("/api/v1/auth/logout");
}

export function getMe() {
  return apiClient.get<MeResponse>("/api/v1/auth/me");
}
