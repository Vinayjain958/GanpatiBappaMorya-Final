/** Shapes returned by the conversational discovery endpoints. Mirrors
 * apps/api/src/schemas/conversation.py — keep in sync. */

import type { ApiExperienceSummary, DiscoverySort } from "@/types/api";

export type TravelerBudget = "any" | "low" | "mid" | "high";
export type TravelerDuration = "any" | "short" | "medium" | "long";

/** The single structured-intent shape shared by both text and voice
 * turns. Gemini never supplies coordinates — location_text is free text
 * only, applied only on explicit user action (never auto-geocoded). */
export interface TravelerContext {
  raw_query: string;
  interests: string[];
  category_slugs: string[];
  location_text: string | null;
  budget: TravelerBudget | null;
  duration: TravelerDuration | null;
  party_size: number | null;
  time_context: string | null;
  notes: string | null;
}

export interface SearchExperiencesArgs {
  q?: string;
  category_slug?: string;
  city?: string;
  locality?: string;
  min_price?: number;
  max_price?: number;
  min_duration_minutes?: number;
  max_duration_minutes?: number;
  lat?: number;
  lng?: number;
  radius_km?: number;
  sort?: DiscoverySort;
  limit?: number;
}

export interface SearchExperiencesResult {
  items: ApiExperienceSummary[];
  total: number;
  truncated: boolean;
}

export interface ConversationCreateResponse {
  id: string;
  created_at: string;
}

export interface ConversationMessagePublic {
  id: string;
  role: "user" | "assistant";
  text: string;
  created_at: string;
}

export interface ConversationDetailResponse {
  id: string;
  created_at: string;
  messages: ConversationMessagePublic[];
  latest_traveler_context: TravelerContext | null;
}

export interface ConversationTurnResponse {
  message_id: string;
  assistant_text: string;
  traveler_context: TravelerContext;
  tool_results: SearchExperiencesResult | null;
}

export interface LiveTokenResponse {
  token: string;
  expire_time: string;
  new_session_expire_time: string;
  model: string;
}

/** Voice session state machine (Phase 5). Every unrecoverable failure
 * lands in ERROR — never a fake CONNECTED appearance. */
export type VoiceState =
  | "IDLE"
  | "CONNECTING"
  | "CONNECTED"
  | "LISTENING"
  | "THINKING"
  | "SPEAKING"
  | "TOOL_EXECUTING"
  | "RECONNECTING"
  | "ERROR"
  | "ENDED";

export interface VoiceTranscriptEntry {
  role: "user" | "assistant";
  text: string;
  final: boolean;
}
