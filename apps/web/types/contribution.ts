/** Shapes for POST /api/v1/contributions/experiences. Mirrors
 * apps/api/src/schemas/contribution.py — keep in sync. */

import type { ApiExperienceDetail } from "@/types/api";

export interface ContributionSummary {
  id: string;
  status: string;
}

export interface ContributionPublishResponse {
  experience: ApiExperienceDetail & { contributor_display_name?: string };
  contribution: ContributionSummary;
}

/** The backend returns this same shape for both a hard block (409,
 * DUPLICATE_EXPERIENCE) and a soft "are you sure" (200, POSSIBLE_DUPLICATE)
 * — the caller distinguishes them by `detail` and by which HTTP status the
 * response actually came back with (see lib/api/contributions.ts). */
export interface DuplicateFoundResponse {
  detail: "DUPLICATE_EXPERIENCE" | "POSSIBLE_DUPLICATE";
  existing_experience_id: string;
  reason: string;
  message: string;
}

export interface ContributionFormValues {
  name: string;
  categoryId: string;
  latitude: number | null;
  longitude: number | null;
  placeName: string;
  address: string;
  contactPhone: string;
  description: string;
  website: string;
}

export const EMPTY_CONTRIBUTION_FORM: ContributionFormValues = {
  name: "",
  categoryId: "",
  latitude: null,
  longitude: null,
  placeName: "",
  address: "",
  contactPhone: "",
  description: "",
  website: "",
};
