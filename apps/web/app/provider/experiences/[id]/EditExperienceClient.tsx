"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { PageContainer } from "@/components/layout/PageContainer";
import { RequireRole } from "@/components/common/RequireRole";
import { ErrorState } from "@/components/ui/ErrorState";
import { Skeleton } from "@/components/ui/Skeleton";
import { AvailabilityManager } from "@/components/provider/AvailabilityManager";
import {
  EMPTY_OPENING_HOURS,
  ExperienceForm,
  buildUpdatePayload,
  type ExperienceFormValues,
} from "@/components/provider/ExperienceForm";
import { getExperience } from "@/lib/api/experiences";
import { updateExperience, uploadExperienceImage } from "@/lib/api/experiencesWrite";
import { ApiError } from "@/lib/api/client";
import { useAuth } from "@/lib/auth/AuthContext";

function valuesFromApi(
  experience: Awaited<ReturnType<typeof getExperience>>,
): ExperienceFormValues {
  const openingHours = experience.opening_hours.length
    ? Array.from({ length: 7 }, (_, day) => {
        const match = experience.opening_hours.find((w) => w.day_of_week === day);

        return match
          ? {
              day_of_week: day,
              open_time: match.open_time,
              close_time: match.close_time,
              is_closed: match.is_closed,
            }
          : {
              day_of_week: day,
              open_time: "10:00",
              close_time: "18:00",
              is_closed: true,
            };
      })
    : EMPTY_OPENING_HOURS;

  return {
    title: experience.title,
    short_description: experience.short_description,
    full_description: experience.full_description,
    category_id: experience.category.id,
    price: experience.price != null ? String(experience.price) : "",
    duration_minutes:
      experience.duration_minutes != null ? String(experience.duration_minutes) : "",
    minimum_group_size:
      experience.minimum_group_size != null ? String(experience.minimum_group_size) : "",
    maximum_group_size:
      experience.maximum_group_size != null ? String(experience.maximum_group_size) : "",
    capacity: experience.capacity != null ? String(experience.capacity) : "",
    wheelchair_accessible: experience.wheelchair_accessible ?? false,
    step_free: experience.step_free ?? false,
    accessibility_notes: experience.accessibility_notes ?? "",
    tags: (experience.tags ?? []).join(", "),
    suitability: experience.suitability ?? [],
    status: experience.status as ExperienceFormValues["status"],
    openingHours,
    latitude: String(experience.location.latitude),
    longitude: String(experience.location.longitude),
    place_name: experience.location.place_name ?? "",
    address: experience.location.address ?? "",
    locality: experience.location.locality ?? "",
    city: experience.location.city,
  };
}

export function EditExperienceClient({ experienceId }: { experienceId: string }) {
  const router = useRouter();
  const { provider: authProvider } = useAuth();
  const [initialValues, setInitialValues] = useState<ExperienceFormValues | null>(null);
  const [status, setStatus] = useState<"loading" | "success" | "error" | "forbidden">(
    "loading",
  );
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    getExperience(experienceId)
      .then((experience) => {
        if (cancelled) return;

        // GET is public and read-only, so it can return another provider's
        // or a catalog-imported experience. Only the owning provider may
        // see the edit form; the server also enforces ownership on updates.
        if (!authProvider || experience.provider.id !== authProvider.id) {
          setStatus("forbidden");
          return;
        }

        setInitialValues(valuesFromApi(experience));
        setStatus("success");
      })
      .catch((err) => {
        if (cancelled) return;
        setStatus(err instanceof ApiError && err.status === 404 ? "forbidden" : "error");
      });

    return () => {
      cancelled = true;
    };
  }, [experienceId, authProvider]);

  async function handleSubmit(values: ExperienceFormValues, shopImage: File | null) {
    setIsSubmitting(true);
    setError(null);

    try {
      await updateExperience(experienceId, buildUpdatePayload(values));
      if (shopImage) {
        await uploadExperienceImage(experienceId, shopImage);
      }
      router.refresh();
      setInitialValues(values);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't save changes. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <RequireRole role="provider">
      <PageContainer className="max-w-4xl space-y-7 py-8 sm:py-10">
        <div className="space-y-2">
          <h1 className="text-3xl font-semibold tracking-tight text-ink sm:text-4xl">
            Manage experience
          </h1>
        </div>

        {status === "loading" ? (
          <div className="space-y-4" aria-busy="true">
            <Skeleton className="h-10 w-2/3 rounded-xl" />
            <Skeleton className="h-48 w-full rounded-2xl" />
          </div>
        ) : status === "forbidden" ? (
          <ErrorState
            title="Experience not found"
            description="It may not exist, or it may not belong to your account."
          />
        ) : status === "error" || !initialValues ? (
          <ErrorState title="Couldn't load this experience" />
        ) : (
          <div className="space-y-7">
            <ExperienceForm
              mode="edit"
              initialValues={initialValues}
              onSubmit={handleSubmit}
              submitLabel="Save changes"
              isSubmitting={isSubmitting}
              error={error}
            />
            <AvailabilityManager experienceId={experienceId} />
          </div>
        )}
      </PageContainer>
    </RequireRole>
  );
}