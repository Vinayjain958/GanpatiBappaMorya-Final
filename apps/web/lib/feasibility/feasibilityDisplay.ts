import type { FeasibilityReason, FeasibilityReasonCode, FeasibilityStatus, RetrievalMode } from "@/types/api";

/**
 * Pure, deterministic mapping from backend feasibility data to display
 * copy — no business logic in React components (INV: browser is
 * transport/UI only). UNKNOWN must never be phrased as "probably okay"
 * anywhere in the UI (docs/AI_CONTEXT.md hard invariant) — the copy below
 * is written to honor that for every status.
 */

export type VerifiedBadgeKind = "fits-budget" | "fits-time" | "within-travel-range" | "accessible";

const BADGE_LABELS: Record<VerifiedBadgeKind, string> = {
  "fits-budget": "Fits your budget",
  "fits-time": "Fits your time",
  "within-travel-range": "Within travel range",
  accessible: "Meets accessibility needs",
};

/**
 * Which verified-match badges to show for a FEASIBLE item, derived only
 * from which constraints the traveler actually asked about (so a badge is
 * never shown without real evidence backing it). A constraint the
 * traveler never mentioned never produces a badge, even implicitly.
 */
export function verifiedBadgesForRequestedConstraints(requested: {
  hasBudget: boolean;
  hasTime: boolean;
  hasTravel: boolean;
  hasAccessibility: boolean;
}): { kind: VerifiedBadgeKind; label: string }[] {
  const badges: { kind: VerifiedBadgeKind; label: string }[] = [];
  if (requested.hasBudget) badges.push({ kind: "fits-budget", label: BADGE_LABELS["fits-budget"] });
  if (requested.hasTime) badges.push({ kind: "fits-time", label: BADGE_LABELS["fits-time"] });
  if (requested.hasTravel) badges.push({ kind: "within-travel-range", label: BADGE_LABELS["within-travel-range"] });
  if (requested.hasAccessibility) badges.push({ kind: "accessible", label: BADGE_LABELS.accessible });
  return badges;
}

/** Human-readable label for a single reason code — used in the excluded
 * summary. Deliberately factual/neutral, never reassuring for UNKNOWN
 * codes (e.g. never "probably fine"). */
const REASON_LABELS: Record<FeasibilityReasonCode, string> = {
  EXPERIENCE_INACTIVE: "No longer active",
  MISSING_LOCATION: "Location data missing",
  BUDGET_EXCEEDED: "Over budget",
  PRICE_UNAVAILABLE: "Price not available",
  UNSUPPORTED_CURRENCY: "Currency not supported",
  DURATION_EXCEEDED: "Takes longer than your available time",
  DURATION_UNAVAILABLE: "Duration not available",
  OUTSIDE_AVAILABLE_TIME: "Doesn't fit your available time with travel",
  OPENING_HOURS_CONFLICT: "Closed at your requested time",
  OPENING_HOURS_UNAVAILABLE: "Opening hours not available",
  TRAVEL_TIME_EXCEEDED: "Travel time too long",
  TRAVEL_TIME_UNAVAILABLE: "Travel time not available",
  MAX_DISTANCE_EXCEEDED: "Too far away",
  GROUP_SIZE_EXCEEDS_CAPACITY: "Group too large",
  CAPACITY_UNAVAILABLE: "Capacity not available",
  ACCESSIBILITY_NOT_SUPPORTED: "Doesn't meet accessibility needs",
  ACCESSIBILITY_DATA_UNAVAILABLE: "Accessibility info not available",
  AVAILABILITY_CONFLICT: "No matching availability slot",
  AVAILABILITY_UNAVAILABLE: "Availability not on record",
  ITINERARY_CONFLICT: "Conflicts with an existing plan",
  MISSING_TIME_CONTEXT: "Time context missing",
  MISSING_ORIGIN: "Starting location missing",
  ROUTE_UNAVAILABLE: "Route not available",
};

export function reasonLabel(code: FeasibilityReasonCode): string {
  return REASON_LABELS[code] ?? code;
}

/** UNKNOWN-specific reason codes never get a "confident" phrasing — this
 * flags which codes represent missing data (vs an explicit contradiction)
 * so UI copy can say "not available" rather than implying a pass/fail. */
const UNKNOWN_CODES = new Set<FeasibilityReasonCode>([
  "PRICE_UNAVAILABLE",
  "UNSUPPORTED_CURRENCY",
  "DURATION_UNAVAILABLE",
  "OPENING_HOURS_UNAVAILABLE",
  "TRAVEL_TIME_UNAVAILABLE",
  "MISSING_ORIGIN",
  "ROUTE_UNAVAILABLE",
  "CAPACITY_UNAVAILABLE",
  "ACCESSIBILITY_DATA_UNAVAILABLE",
  "AVAILABILITY_UNAVAILABLE",
  "MISSING_TIME_CONTEXT",
  "MISSING_LOCATION",
]);

export function isUnknownReason(code: FeasibilityReasonCode): boolean {
  return UNKNOWN_CODES.has(code);
}

/** A short status summary line — never phrases UNKNOWN as reassuring. */
export function statusSummary(status: FeasibilityStatus, reasons: FeasibilityReason[]): string {
  if (status === "FEASIBLE") return "Verified feasible";
  if (status === "UNKNOWN") {
    const missing = reasons.map((r) => reasonLabel(r.code)).join(", ");
    return missing ? `Not enough information to verify: ${missing}` : "Not enough information to verify";
  }
  const failed = reasons.map((r) => reasonLabel(r.code)).join(", ");
  return failed ? `Not feasible: ${failed}` : "Not feasible";
}

/** Group excluded-candidate reason counts for a compact summary panel,
 * sorted by frequency descending (most common exclusion reason first). */
export function summarizeExcludedReasons(
  reasonCounts: Record<string, number>,
): { code: FeasibilityReasonCode; label: string; count: number }[] {
  return Object.entries(reasonCounts)
    .map(([code, count]) => ({ code: code as FeasibilityReasonCode, label: reasonLabel(code as FeasibilityReasonCode), count }))
    .sort((a, b) => b.count - a.count);
}

export function retrievalModeLabel(mode: RetrievalMode): string {
  switch (mode) {
    case "pgvector_semantic":
      return "Semantic search (pgvector)";
    case "sqlite_python_semantic":
      return "Semantic search";
    case "keyword_fallback":
      return "Keyword search";
    default:
      return mode;
  }
}
