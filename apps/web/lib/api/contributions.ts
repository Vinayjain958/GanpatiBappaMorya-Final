import { apiClient, ApiError } from "@/lib/api/client";
import type {
  ContributionFormValues,
  ContributionPublishResponse,
  DuplicateFoundResponse,
} from "@/types/contribution";

/** Distinguishes the three possible outcomes of a submission without
 * throwing for the "possible duplicate" case — that's a decision point
 * for the traveler, not an error. A hard duplicate block
 * (409) still comes back as this same shape rather than an ApiError, so
 * the form can show "We may already have this" either way and only
 * differ in whether [Continue Anyway] is offered. */
export type SubmitContributionResult =
  | { kind: "published"; data: ContributionPublishResponse }
  | { kind: "duplicate"; blocking: boolean; data: DuplicateFoundResponse };

export async function submitExperienceContribution(
  values: ContributionFormValues,
  image: File,
  idempotencyKey: string,
  options: { overrideDuplicateCheck?: boolean; signal?: AbortSignal } = {},
): Promise<SubmitContributionResult> {
  if (values.latitude == null || values.longitude == null) {
    throw new ApiError("Please select where this experience is located.", 422);
  }

  const form = new FormData();
  form.set("name", values.name);
  form.set("category_id", values.categoryId);
  form.set("latitude", String(values.latitude));
  form.set("longitude", String(values.longitude));
  form.set("contact_phone", values.contactPhone);
  if (values.placeName) form.set("place_name", values.placeName);
  if (values.address) form.set("address", values.address);
  if (values.description) form.set("description", values.description);
  if (values.website) form.set("website", values.website);
  form.set("override_duplicate_check", String(options.overrideDuplicateCheck ?? false));
  form.set("image", image);

  try {
    const data = await apiClient.postForm<ContributionPublishResponse | DuplicateFoundResponse>(
      "/api/v1/contributions/experiences",
      form,
      { signal: options.signal, headers: { "Idempotency-Key": idempotencyKey } },
    );
    // A 200 response is either a genuine publish or an uncertain-duplicate
    // decision point — the backend distinguishes them by
    // whether `detail` is present, not by HTTP status alone.
    if ("detail" in data) {
      return { kind: "duplicate", blocking: false, data };
    }
    return { kind: "published", data };
  } catch (err) {
    if (err instanceof ApiError && err.status === 409) {
      return { kind: "duplicate", blocking: true, data: err.detail as DuplicateFoundResponse };
    }
    throw err;
  }
}
