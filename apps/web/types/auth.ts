export type UserRole = "traveler" | "provider" | "admin";

export interface AuthUser {
  id: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export interface TravelerProfile {
  id: string;
  traveler_type: string | null;
}

export interface ProviderProfileSummary {
  id: string;
  business_name: string;
  verification_status: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  user: AuthUser;
  traveler: TravelerProfile | null;
  provider: ProviderProfileSummary | null;
}

export interface MeResponse {
  user: AuthUser;
  traveler: TravelerProfile | null;
  provider: ProviderProfileSummary | null;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface RegisterTravelerPayload {
  email: string;
  password: string;
  role: "traveler";
  display_name: string;
  traveler_type?: string;
}

export interface RegisterProviderPayload {
  email: string;
  password: string;
  role: "provider";
  display_name: string;
  business_name: string;
  description?: string;
  provider_type?: string;
}

export type RegisterPayload = RegisterTravelerPayload | RegisterProviderPayload;
