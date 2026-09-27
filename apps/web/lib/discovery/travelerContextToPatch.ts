import type { DiscoveryState } from "@/types/discovery";
import type { SearchExperiencesArgs, TravelerContext } from "@/types/conversation";
import { categoryOptions } from "@/lib/constants/categories";

const CATEGORY_SLUGS = new Set(categoryOptions.map((c) => c.value));

/**
 * Deterministically translates AI-extracted intent into a DiscoveryState
 * patch — the app controls this mapping, never the model. category_slugs
 * are re-validated against the canonical taxonomy (the backend already
 * does this too; re-checking here means a stale/malformed value never
 * reaches DiscoveryState even if some future caller skips the API).
 *
 * location_text is intentionally NEVER mapped to lat/lng/locationLabel —
 * geocoding only happens on an explicit user action (ADR-022). A
 * conversational location mention is surfaced as a suggestion the user
 * must apply themselves (see components/voice/VoiceTranscriptPanel.tsx).
 */
export function travelerContextToDiscoveryPatch(context: TravelerContext): Partial<DiscoveryState> {
  const category = context.category_slugs.find((slug) => CATEGORY_SLUGS.has(slug)) ?? null;
  return {
    q: context.raw_query || undefined,
    category,
    budget: context.budget ?? "any",
    duration: context.duration ?? "any",
  };
}

/** Voice-path sibling: Gemini Live drives search_experiences tool args
 * directly, so there is no separate extracted TravelerContext object for
 * voice turns — this maps the tool call's own args instead. */
export function searchArgsToDiscoveryPatch(args: SearchExperiencesArgs): Partial<DiscoveryState> {
  const category = args.category_slug && CATEGORY_SLUGS.has(args.category_slug) ? args.category_slug : null;
  return {
    q: args.q || undefined,
    category,
  };
}
