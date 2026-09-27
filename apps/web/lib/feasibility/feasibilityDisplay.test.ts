import { describe, expect, it } from "vitest";
import {
  isUnknownReason,
  reasonLabel,
  retrievalModeLabel,
  statusSummary,
  summarizeExcludedReasons,
  verifiedBadgesForRequestedConstraints,
} from "@/lib/feasibility/feasibilityDisplay";
import type { FeasibilityReason } from "@/types/api";

describe("verifiedBadgesForRequestedConstraints", () => {
  it("returns no badges when nothing was requested", () => {
    expect(
      verifiedBadgesForRequestedConstraints({
        hasBudget: false,
        hasTime: false,
        hasTravel: false,
        hasAccessibility: false,
      }),
    ).toEqual([]);
  });

  it("returns only the badge for a requested constraint", () => {
    const badges = verifiedBadgesForRequestedConstraints({
      hasBudget: true,
      hasTime: false,
      hasTravel: false,
      hasAccessibility: false,
    });
    expect(badges).toHaveLength(1);
    expect(badges[0].kind).toBe("fits-budget");
  });

  it("returns all badges when everything was requested", () => {
    const badges = verifiedBadgesForRequestedConstraints({
      hasBudget: true,
      hasTime: true,
      hasTravel: true,
      hasAccessibility: true,
    });
    expect(badges.map((b) => b.kind)).toEqual(["fits-budget", "fits-time", "within-travel-range", "accessible"]);
  });

  it("never fabricates a badge for a constraint that wasn't requested", () => {
    const badges = verifiedBadgesForRequestedConstraints({
      hasBudget: false,
      hasTime: true,
      hasTravel: false,
      hasAccessibility: false,
    });
    expect(badges.some((b) => b.kind === "fits-budget")).toBe(false);
    expect(badges.some((b) => b.kind === "within-travel-range")).toBe(false);
  });
});

describe("reasonLabel", () => {
  it("returns a human label for a known code", () => {
    expect(reasonLabel("BUDGET_EXCEEDED")).toBe("Over budget");
  });

  it("falls back to the raw code for an unrecognized value", () => {
    // @ts-expect-error — testing the defensive fallback path
    expect(reasonLabel("SOME_FUTURE_CODE")).toBe("SOME_FUTURE_CODE");
  });
});

describe("isUnknownReason", () => {
  it("flags missing-data codes as unknown", () => {
    expect(isUnknownReason("PRICE_UNAVAILABLE")).toBe(true);
    expect(isUnknownReason("CAPACITY_UNAVAILABLE")).toBe(true);
  });

  it("does not flag explicit-contradiction codes as unknown", () => {
    expect(isUnknownReason("BUDGET_EXCEEDED")).toBe(false);
    expect(isUnknownReason("MAX_DISTANCE_EXCEEDED")).toBe(false);
  });
});

describe("statusSummary", () => {
  it("reports FEASIBLE plainly", () => {
    expect(statusSummary("FEASIBLE", [])).toBe("Verified feasible");
  });

  it("never phrases UNKNOWN as reassuring — states missing info instead", () => {
    const reasons: FeasibilityReason[] = [
      { code: "PRICE_UNAVAILABLE", constraint: "budget", message: "x", blocking: true, evidence: {} },
    ];
    const summary = statusSummary("UNKNOWN", reasons);
    expect(summary).toContain("Not enough information");
    expect(summary.toLowerCase()).not.toContain("probably");
    expect(summary.toLowerCase()).not.toContain("should be okay");
    expect(summary.toLowerCase()).not.toContain("fine");
  });

  it("reports INFEASIBLE with the failing reasons", () => {
    const reasons: FeasibilityReason[] = [
      { code: "BUDGET_EXCEEDED", constraint: "budget", message: "x", blocking: true, evidence: {} },
    ];
    expect(statusSummary("INFEASIBLE", reasons)).toContain("Over budget");
  });
});

describe("summarizeExcludedReasons", () => {
  it("sorts by count descending", () => {
    const summary = summarizeExcludedReasons({ BUDGET_EXCEEDED: 2, MAX_DISTANCE_EXCEEDED: 5 });
    expect(summary[0].code).toBe("MAX_DISTANCE_EXCEEDED");
    expect(summary[0].count).toBe(5);
    expect(summary[1].code).toBe("BUDGET_EXCEEDED");
  });

  it("returns an empty array for no exclusions", () => {
    expect(summarizeExcludedReasons({})).toEqual([]);
  });
});

describe("retrievalModeLabel", () => {
  it("never claims semantic retrieval when it fell back to keyword search", () => {
    const label = retrievalModeLabel("keyword_fallback");
    expect(label.toLowerCase()).not.toContain("semantic");
  });

  it("labels pgvector and sqlite semantic modes distinctly but both as semantic", () => {
    expect(retrievalModeLabel("pgvector_semantic")).toContain("Semantic");
    expect(retrievalModeLabel("sqlite_python_semantic")).toContain("Semantic");
  });
});
