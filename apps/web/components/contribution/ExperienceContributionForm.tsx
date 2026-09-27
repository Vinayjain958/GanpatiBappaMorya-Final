"use client";

import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Input, Textarea } from "@/components/ui/Input";
import { listCategories, type ApiCategory } from "@/lib/api/categories";
import { ExperienceLocationPicker, type PickedLocation } from "@/components/contribution/ExperienceLocationPicker";
import { ExperiencePhotoUploader } from "@/components/contribution/ExperiencePhotoUploader";
import { EMPTY_CONTRIBUTION_FORM, type ContributionFormValues } from "@/types/contribution";

export interface ContributionFormState {
  values: ContributionFormValues;
  image: File;
}

/**
 * "Add a Local Experience" form. Required fields: photo,
 * name, category, location, contact number. Optional description/website
 * are collapsed under "Add more details" rather than always shown,
 * to keep the primary mobile path short: photo → name → category →
 * location → phone → publish.
 */
export function ExperienceContributionForm({
  onSubmit,
  isSubmitting,
  error,
  submitLabel = "Publish Experience",
}: {
  onSubmit: (state: ContributionFormState) => void;
  isSubmitting: boolean;
  error: string | null;
  submitLabel?: string;
}) {
  const [values, setValues] = useState<ContributionFormValues>(EMPTY_CONTRIBUTION_FORM);
  const [image, setImage] = useState<File | null>(null);
  const [categories, setCategories] = useState<ApiCategory[]>([]);
  const [showMoreDetails, setShowMoreDetails] = useState(false);

  useEffect(() => {
    listCategories()
      .then(setCategories)
      .catch(() => setCategories([]));
  }, []);

  function update<K extends keyof ContributionFormValues>(key: K, value: ContributionFormValues[K]) {
    setValues((prev) => ({ ...prev, [key]: value }));
  }

  function handleLocationChange(location: PickedLocation | null) {
    setValues((prev) => ({
      ...prev,
      latitude: location?.lat ?? null,
      longitude: location?.lng ?? null,
      placeName: location?.label ?? "",
      address: location?.address ?? "",
    }));
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!image) return;
    onSubmit({ values, image });
  }

  const locationValue: PickedLocation | null =
    values.latitude != null && values.longitude != null
      ? { lat: values.latitude, lng: values.longitude, label: values.placeName || "Selected location", address: values.address }
      : null;

  const isReadyToSubmit = Boolean(image && values.name.trim() && values.categoryId && locationValue && values.contactPhone.trim());

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <fieldset disabled={isSubmitting} className="space-y-5">
        <section className="space-y-3 rounded-3xl border border-line bg-surface p-5 shadow-soft sm:p-6">
          <h2 className="text-lg font-semibold tracking-tight text-ink">Photo</h2>
          <ExperiencePhotoUploader file={image} onChange={setImage} />
        </section>

        <section className="space-y-5 rounded-3xl border border-line bg-surface p-5 shadow-soft sm:p-6">
          <Input
            label="Experience Name"
            required
            minLength={2}
            value={values.name}
            onChange={(event) => update("name", event.target.value)}
            placeholder="e.g. Aunty's Vada Pav Stall"
          />

          <label className="flex flex-col gap-2 text-sm font-medium text-ink">
            Category
            <select
              required
              value={values.categoryId}
              onChange={(event) => update("categoryId", event.target.value)}
              className="h-11 rounded-xl border border-line-strong bg-surface px-3.5 text-sm text-ink outline-none transition focus:border-accent focus:ring-2 focus:ring-accent/15"
            >
              <option value="" disabled>
                Select category
              </option>
              {categories.map((category) => (
                <option key={category.id} value={category.id}>
                  {category.name}
                </option>
              ))}
            </select>
          </label>

          <div className="flex flex-col gap-2 text-sm font-medium text-ink">
            Location
            <ExperienceLocationPicker value={locationValue} onChange={handleLocationChange} disabled={isSubmitting} />
          </div>

          <Input
            label="Contact Number"
            required
            type="tel"
            value={values.contactPhone}
            onChange={(event) => update("contactPhone", event.target.value)}
            placeholder="+91 98765 43210"
            hint="Shown to LocaLens only — not published on the experience listing."
          />
        </section>

        <section className="rounded-3xl border border-line bg-surface p-5 shadow-soft sm:p-6">
          <button
            type="button"
            onClick={() => setShowMoreDetails((prev) => !prev)}
            className="flex w-full items-center justify-between text-sm font-semibold text-ink"
          >
            Add more details (optional)
            {showMoreDetails ? (
              <ChevronUp className="size-4" aria-hidden="true" />
            ) : (
              <ChevronDown className="size-4" aria-hidden="true" />
            )}
          </button>

          {showMoreDetails ? (
            <div className="mt-4 space-y-5">
              <Textarea
                label="Description"
                maxLength={4000}
                value={values.description}
                onChange={(event) => update("description", event.target.value)}
                placeholder="What makes this place worth visiting?"
              />
              <Input
                label="Website / Instagram"
                type="url"
                value={values.website}
                onChange={(event) => update("website", event.target.value)}
                placeholder="https://instagram.com/..."
              />
            </div>
          ) : null}
        </section>

        {error ? (
          <p role="alert" className="rounded-2xl bg-danger-soft px-4 py-3 text-sm text-danger">
            {error}
          </p>
        ) : null}

        <Button type="submit" size="lg" className="w-full" loading={isSubmitting} disabled={!isReadyToSubmit}>
          {submitLabel}
        </Button>
      </fieldset>
    </form>
  );
}
