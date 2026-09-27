"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { PageContainer } from "@/components/layout/PageContainer";
import { RequireRole } from "@/components/common/RequireRole";
import {
  EMPTY_FORM_VALUES,
  ExperienceForm,
  buildCreatePayload,
  type ExperienceFormValues,
} from "@/components/provider/ExperienceForm";
import { createExperience, uploadExperienceImage } from "@/lib/api/experiencesWrite";
import { ApiError } from "@/lib/api/client";

export default function NewExperiencePage() {
  const router = useRouter();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(values: ExperienceFormValues, shopImage: File | null) {
    setIsSubmitting(true);
    setError(null);

    try {
      const created = await createExperience(buildCreatePayload(values));
      if (shopImage) {
        // The experience is already created at this point — a failed
        // image upload shouldn't block navigation to it, just skip the
        // photo silently rather than losing the whole submission.
        await uploadExperienceImage(created.id, shopImage).catch(() => undefined);
      }
      router.push(`/provider/experiences/${created.id}`);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Couldn't create this experience. Please try again.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <RequireRole role="provider">
      <PageContainer className="max-w-3xl space-y-7 py-8 sm:py-10">
        <div className="space-y-2">
          <h1 className="text-3xl font-semibold tracking-tight text-ink sm:text-4xl">
            New experience
          </h1>
          <p className="text-sm leading-6 text-ink-muted">
            This starts as a draft — set status to Active when ready.
          </p>
        </div>

        <ExperienceForm
          mode="create"
          initialValues={EMPTY_FORM_VALUES}
          onSubmit={handleSubmit}
          submitLabel="Create experience"
          isSubmitting={isSubmitting}
          error={error}
        />
      </PageContainer>
    </RequireRole>
  );
}