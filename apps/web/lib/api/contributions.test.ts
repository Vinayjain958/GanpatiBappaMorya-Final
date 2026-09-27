import { beforeEach, describe, expect, it, vi } from "vitest";
import * as client from "./client";
import { ApiError } from "./client";
import { submitExperienceContribution } from "./contributions";
import type { ContributionFormValues } from "@/types/contribution";

vi.mock("./client", async () => {
  const actual = await vi.importActual<typeof import("./client")>("./client");
  return {
    ...actual,
    apiClient: { postForm: vi.fn() },
  };
});

const baseValues: ContributionFormValues = {
  name: "Fort Spice Corner",
  categoryId: "cat-1",
  latitude: 18.9402,
  longitude: 72.8347,
  placeName: "Fort Spice Corner",
  address: "",
  contactPhone: "+91 98765 43210",
  description: "",
  website: "",
};

function makeFile(): File {
  return new File(["fake-bytes"], "photo.jpg", { type: "image/jpeg" });
}

describe("submitExperienceContribution", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("builds multipart form data and posts to /api/v1/contributions/experiences", async () => {
    vi.mocked(client.apiClient.postForm).mockResolvedValue({
      experience: { id: "exp-1", title: "Fort Spice Corner" },
      contribution: { id: "contrib-1", status: "published" },
    });

    const result = await submitExperienceContribution(baseValues, makeFile(), "idem-key-1");

    expect(result.kind).toBe("published");
    expect(client.apiClient.postForm).toHaveBeenCalledTimes(1);
    const [path, form, options] = vi.mocked(client.apiClient.postForm).mock.calls[0];
    expect(path).toBe("/api/v1/contributions/experiences");
    expect(form).toBeInstanceOf(FormData);
    expect((form as FormData).get("name")).toBe("Fort Spice Corner");
    expect((form as FormData).get("category_id")).toBe("cat-1");
    expect((form as FormData).get("latitude")).toBe("18.9402");
    expect((form as FormData).get("contact_phone")).toBe("+91 98765 43210");
    expect((form as FormData).get("image")).toBeInstanceOf(File);
    expect(options?.headers).toEqual({ "Idempotency-Key": "idem-key-1" });
  });

  it("omits optional fields entirely when blank rather than sending empty strings", async () => {
    vi.mocked(client.apiClient.postForm).mockResolvedValue({
      experience: { id: "exp-1" },
      contribution: { id: "contrib-1", status: "published" },
    });

    await submitExperienceContribution(baseValues, makeFile(), "idem-key-2");

    const [, form] = vi.mocked(client.apiClient.postForm).mock.calls[0];
    expect((form as FormData).has("description")).toBe(false);
    expect((form as FormData).has("website")).toBe(false);
  });

  it("throws before making a request when location hasn't been picked", async () => {
    let caught: unknown;
    try {
      await submitExperienceContribution(
        { ...baseValues, latitude: null, longitude: null },
        makeFile(),
        "idem-key-3",
      );
    } catch (err) {
      caught = err;
    }
    expect(caught).toBeInstanceOf(ApiError);
    expect((caught as ApiError).message).toMatch(/located/i);
    expect(client.apiClient.postForm).not.toHaveBeenCalled();
  });

  it("treats a 200 response carrying `detail` as a non-blocking possible-duplicate result", async () => {
    vi.mocked(client.apiClient.postForm).mockResolvedValue({
      detail: "POSSIBLE_DUPLICATE",
      existing_experience_id: "exp-existing",
      reason: "similar name nearby",
      message: "We may already have this experience.",
    });

    const result = await submitExperienceContribution(baseValues, makeFile(), "idem-key-4");

    expect(result.kind).toBe("duplicate");
    if (result.kind === "duplicate") {
      expect(result.blocking).toBe(false);
      expect(result.data.existing_experience_id).toBe("exp-existing");
    }
  });

  it("treats a 409 ApiError as a blocking duplicate result rather than throwing", async () => {
    vi.mocked(client.apiClient.postForm).mockRejectedValue(
      new ApiError("We already have this place listed.", 409, {
        detail: "DUPLICATE_EXPERIENCE",
        existing_experience_id: "exp-existing",
        reason: "matching name and nearby location",
        message: "We already have this place listed.",
      }),
    );

    const result = await submitExperienceContribution(baseValues, makeFile(), "idem-key-5");

    expect(result.kind).toBe("duplicate");
    if (result.kind === "duplicate") {
      expect(result.blocking).toBe(true);
      expect(result.data.existing_experience_id).toBe("exp-existing");
    }
  });

  it("re-throws a genuine validation error unchanged", async () => {
    vi.mocked(client.apiClient.postForm).mockRejectedValue(
      new ApiError("Please upload a valid JPG, PNG, or WebP image.", 422),
    );

    await expect(submitExperienceContribution(baseValues, makeFile(), "idem-key-6")).rejects.toThrow(
      /valid JPG/i,
    );
  });
});
