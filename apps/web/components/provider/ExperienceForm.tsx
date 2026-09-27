"use client";

import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Search } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Input, Textarea } from "@/components/ui/Input";
import { listCategories, type ApiCategory } from "@/lib/api/categories";
import { useLocationSearch } from "@/hooks/useLocationSearch";
import type {
  ExperienceCreateInput,
  ExperienceUpdateInput,
  OpeningHourInput,
} from "@/types/provider-api";

const DAY_LABELS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const SUITABILITY_OPTIONS = ["solo", "couple", "friends", "family", "business"];

export interface ExperienceFormValues {
  title: string;
  short_description: string;
  full_description: string;
  category_id: string;
  price: string;
  duration_minutes: string;
  minimum_group_size: string;
  maximum_group_size: string;
  capacity: string;
  wheelchair_accessible: boolean;
  step_free: boolean;
  accessibility_notes: string;
  tags: string;
  suitability: string[];
  status: "active" | "draft" | "inactive";
  openingHours: OpeningHourInput[];
  // location — create mode only
  latitude: string;
  longitude: string;
  place_name: string;
  address: string;
  locality: string;
  city: string;
}

export const EMPTY_OPENING_HOURS: OpeningHourInput[] = DAY_LABELS.map((_, day) => ({
  day_of_week: day,
  open_time: "10:00",
  close_time: "18:00",
  is_closed: day === 6,
}));

export const EMPTY_FORM_VALUES: ExperienceFormValues = {
  title: "",
  short_description: "",
  full_description: "",
  category_id: "",
  price: "",
  duration_minutes: "",
  minimum_group_size: "",
  maximum_group_size: "",
  capacity: "",
  wheelchair_accessible: false,
  step_free: false,
  accessibility_notes: "",
  tags: "",
  suitability: [],
  status: "draft",
  openingHours: EMPTY_OPENING_HOURS,
  latitude: "",
  longitude: "",
  place_name: "",
  address: "",
  locality: "",
  city: "Mumbai",
};

function toNullableNumber(value: string): number | null {
  if (value.trim() === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function buildCreatePayload(values: ExperienceFormValues): ExperienceCreateInput {
  return {
    title: values.title,
    short_description: values.short_description,
    full_description: values.full_description,
    category_id: values.category_id,
    location: {
      latitude: Number(values.latitude),
      longitude: Number(values.longitude),
      place_name: values.place_name || undefined,
      address: values.address || undefined,
      locality: values.locality || undefined,
      city: values.city || "Mumbai",
    },
    price: toNullableNumber(values.price),
    price_type: values.price ? "fixed" : "unknown",
    duration_minutes: toNullableNumber(values.duration_minutes),
    minimum_group_size: toNullableNumber(values.minimum_group_size),
    maximum_group_size: toNullableNumber(values.maximum_group_size),
    capacity: toNullableNumber(values.capacity),
    wheelchair_accessible: values.wheelchair_accessible,
    step_free: values.step_free,
    accessibility_notes: values.accessibility_notes || undefined,
    tags: values.tags
      .split(",")
      .map((tag) => tag.trim())
      .filter(Boolean),
    suitability: values.suitability,
    status: values.status,
    opening_hours: values.openingHours,
  };
}

export function buildUpdatePayload(values: ExperienceFormValues): ExperienceUpdateInput {
  const payload = buildCreatePayload(values) as ExperienceUpdateInput & { location?: unknown };
  delete payload.location;
  return payload;
}

export function ExperienceForm({
  mode,
  initialValues,
  onSubmit,
  submitLabel,
  isSubmitting,
  error,
}: {
  mode: "create" | "edit";
  initialValues: ExperienceFormValues;
  onSubmit: (values: ExperienceFormValues) => void | Promise<void>;
  submitLabel: string;
  isSubmitting: boolean;
  error?: string | null;
}) {
  const [values, setValues] = useState(initialValues);
  const [categories, setCategories] = useState<ApiCategory[]>([]);
  const [placeQuery, setPlaceQuery] = useState("");
  const {
    status: placeSearchStatus,
    results: placeResults,
    search: searchPlace,
    clear: clearPlaceResults,
  } = useLocationSearch();

  useEffect(() => {
    listCategories()
      .then(setCategories)
      .catch(() => setCategories([]));
  }, []);

  function update<K extends keyof ExperienceFormValues>(
    key: K,
    value: ExperienceFormValues[K],
  ) {
    setValues((prev) => ({ ...prev, [key]: value }));
  }

  async function handlePlaceSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!placeQuery.trim()) return;
    await searchPlace(placeQuery);
  }

  function handlePickPlace(result: {
    lat: number;
    lng: number;
    display_name: string;
    city: string | null;
    locality: string | null;
  }) {
    // Only applied after an explicit pick; manually entered location isn't silently overwritten.
    setValues((prev) => ({
      ...prev,
      latitude: String(result.lat),
      longitude: String(result.lng),
      address: result.display_name,
      city: result.city ?? prev.city,
      locality: result.locality ?? prev.locality,
    }));
    clearPlaceResults();
    setPlaceQuery("");
  }

  function updateOpeningHour(day: number, patch: Partial<OpeningHourInput>) {
    setValues((prev) => ({
      ...prev,
      openingHours: prev.openingHours.map((window) =>
        window.day_of_week === day ? { ...window, ...patch } : window,
      ),
    }));
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void onSubmit(values);
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <section className="space-y-5 rounded-3xl border border-line bg-surface p-5 shadow-soft sm:p-6">
        <h2 className="text-lg font-semibold tracking-tight text-ink">Basic details</h2>

        <Input
          label="Title"
          required
          minLength={3}
          value={values.title}
          onChange={(event) => update("title", event.target.value)}
        />
        <Textarea
          label="Short description"
          required
          minLength={10}
          maxLength={300}
          value={values.short_description}
          onChange={(event) => update("short_description", event.target.value)}
        />
        <Textarea
          label="Full description"
          required
          minLength={10}
          value={values.full_description}
          onChange={(event) => update("full_description", event.target.value)}
        />

        <label className="flex flex-col gap-2 text-sm font-medium text-ink">
          Category
          <select
            required
            value={values.category_id}
            onChange={(event) => update("category_id", event.target.value)}
            className="h-11 rounded-xl border border-line-strong bg-surface px-3.5 text-sm text-ink outline-none transition focus:border-accent focus:ring-2 focus:ring-accent/15"
          >
            <option value="" disabled>
              Select a category
            </option>
            {categories.map((category) => (
              <option key={category.id} value={category.id}>
                {category.name}
              </option>
            ))}
          </select>
        </label>
      </section>

      {mode === "create" ? (
        <section className="space-y-5 rounded-3xl border border-line bg-surface p-5 shadow-soft sm:p-6">
          <h2 className="text-lg font-semibold tracking-tight text-ink">Location</h2>

          <div className="space-y-3 rounded-2xl bg-surface-raised p-3 sm:p-4">
            <form onSubmit={handlePlaceSearch} className="flex flex-col gap-2 sm:flex-row">
              <input
                type="text"
                value={placeQuery}
                onChange={(event) => setPlaceQuery(event.target.value)}
                placeholder="Search a place to fill the fields below"
                className="h-11 min-w-0 flex-1 rounded-xl border border-line-strong bg-surface px-3.5 text-sm text-ink placeholder:text-ink-subtle outline-none transition focus:border-accent focus:ring-2 focus:ring-accent/15"
              />
              <Button
                type="submit"
                size="sm"
                variant="outline"
                loading={placeSearchStatus === "loading"}
                className="rounded-full"
              >
                <Search className="size-4" aria-hidden="true" />
                Search
              </Button>
            </form>

            {placeSearchStatus === "success" && placeResults.length > 0 ? (
              <ul className="max-w-full space-y-1 rounded-2xl border border-line bg-surface p-2 shadow-soft sm:max-w-xl">
                {placeResults.map((result) => (
                  <li key={`${result.lat}-${result.lng}`}>
                    <button
                      type="button"
                      onClick={() => handlePickPlace(result)}
                      className="block w-full truncate rounded-xl px-3 py-2.5 text-left text-sm text-ink transition-colors hover:bg-accent-soft"
                    >
                      {result.display_name}
                    </button>
                  </li>
                ))}
              </ul>
            ) : placeSearchStatus === "success" ? (
              <p className="rounded-xl bg-highlight-soft px-3 py-2 text-xs text-ink-muted">
                No matching places found — enter coordinates manually below.
              </p>
            ) : null}
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <Input
              label="Latitude"
              type="number"
              step="any"
              required
              value={values.latitude}
              onChange={(event) => update("latitude", event.target.value)}
            />
            <Input
              label="Longitude"
              type="number"
              step="any"
              required
              value={values.longitude}
              onChange={(event) => update("longitude", event.target.value)}
            />
            <Input
              label="Place name"
              value={values.place_name}
              onChange={(event) => update("place_name", event.target.value)}
            />
            <Input
              label="City"
              value={values.city}
              onChange={(event) => update("city", event.target.value)}
            />
            <Input
              label="Address"
              className="sm:col-span-2"
              value={values.address}
              onChange={(event) => update("address", event.target.value)}
            />
            <Input
              label="Locality / area"
              value={values.locality}
              onChange={(event) => update("locality", event.target.value)}
            />
          </div>
        </section>
      ) : null}

      <section className="space-y-5 rounded-3xl border border-line bg-surface p-5 shadow-soft sm:p-6">
        <h2 className="text-lg font-semibold tracking-tight text-ink">
          Pricing &amp; logistics
        </h2>

        <div className="grid gap-4 sm:grid-cols-2">
          <Input
            label="Price (₹)"
            type="number"
            min={0}
            value={values.price}
            onChange={(event) => update("price", event.target.value)}
          />
          <Input
            label="Duration (minutes)"
            type="number"
            min={1}
            value={values.duration_minutes}
            onChange={(event) => update("duration_minutes", event.target.value)}
          />
          <Input
            label="Minimum group size"
            type="number"
            min={1}
            value={values.minimum_group_size}
            onChange={(event) => update("minimum_group_size", event.target.value)}
          />
          <Input
            label="Maximum group size"
            type="number"
            min={1}
            value={values.maximum_group_size}
            onChange={(event) => update("maximum_group_size", event.target.value)}
          />
          <Input
            label="Capacity"
            type="number"
            min={1}
            value={values.capacity}
            onChange={(event) => update("capacity", event.target.value)}
          />

          <label className="flex flex-col gap-2 text-sm font-medium text-ink">
            Status
            <select
              value={values.status}
              onChange={(event) =>
                update("status", event.target.value as ExperienceFormValues["status"])
              }
              className="h-11 rounded-xl border border-line-strong bg-surface px-3.5 text-sm text-ink outline-none transition focus:border-accent focus:ring-2 focus:ring-accent/15"
            >
              <option value="draft">Draft</option>
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
            </select>
          </label>
        </div>
      </section>

      <section className="space-y-5 rounded-3xl border border-line bg-surface p-5 shadow-soft sm:p-6">
        <h2 className="text-lg font-semibold tracking-tight text-ink">
          Discovery &amp; accessibility
        </h2>

        <Input
          label="Tags (comma-separated)"
          value={values.tags}
          onChange={(event) => update("tags", event.target.value)}
        />

        <fieldset className="space-y-3">
          <legend className="text-sm font-medium text-ink">Suitable for</legend>
          <div className="flex flex-wrap gap-2">
            {SUITABILITY_OPTIONS.map((option) => (
              <label
                key={option}
                className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-line bg-surface-raised px-3.5 py-2 text-xs capitalize text-ink-muted transition-colors hover:border-accent/40 hover:bg-accent-soft"
              >
                <input
                  type="checkbox"
                  className="size-4 accent-accent"
                  checked={values.suitability.includes(option)}
                  onChange={(event) =>
                    update(
                      "suitability",
                      event.target.checked
                        ? [...values.suitability, option]
                        : values.suitability.filter((item) => item !== option),
                    )
                  }
                />
                {option}
              </label>
            ))}
          </div>
        </fieldset>

        <div className="flex flex-col gap-3 sm:flex-row sm:gap-6">
          <label className="inline-flex cursor-pointer items-center gap-2.5 text-sm text-ink">
            <input
              type="checkbox"
              className="size-4 accent-accent"
              checked={values.wheelchair_accessible}
              onChange={(event) => update("wheelchair_accessible", event.target.checked)}
            />
            Wheelchair accessible
          </label>
          <label className="inline-flex cursor-pointer items-center gap-2.5 text-sm text-ink">
            <input
              type="checkbox"
              className="size-4 accent-accent"
              checked={values.step_free}
              onChange={(event) => update("step_free", event.target.checked)}
            />
            Step-free route
          </label>
        </div>

        <Textarea
          label="Accessibility notes (optional)"
          value={values.accessibility_notes}
          onChange={(event) => update("accessibility_notes", event.target.value)}
        />
      </section>

      <section className="space-y-5 rounded-3xl border border-line bg-surface p-5 shadow-soft sm:p-6">
        <h2 className="text-lg font-semibold tracking-tight text-ink">Opening hours</h2>

        <div className="space-y-3">
          {values.openingHours.map((window) => (
            <div
              key={window.day_of_week}
              className="flex flex-wrap items-center gap-x-4 gap-y-3 rounded-2xl border border-line bg-surface-raised p-3 sm:p-4"
            >
              <span className="w-24 text-sm font-medium text-ink">
                {DAY_LABELS[window.day_of_week]}
              </span>

              <label className="inline-flex cursor-pointer items-center gap-2 text-xs text-ink-muted">
                <input
                  type="checkbox"
                  className="size-4 accent-accent"
                  checked={window.is_closed}
                  onChange={(event) =>
                    updateOpeningHour(window.day_of_week, {
                      is_closed: event.target.checked,
                    })
                  }
                />
                Closed
              </label>

              {!window.is_closed ? (
                <div className="flex flex-wrap items-center gap-2">
                  <input
                    type="time"
                    value={window.open_time ?? "10:00"}
                    onChange={(event) =>
                      updateOpeningHour(window.day_of_week, {
                        open_time: event.target.value,
                      })
                    }
                    className="h-10 rounded-xl border border-line-strong bg-surface px-3 text-sm text-ink outline-none transition focus:border-accent focus:ring-2 focus:ring-accent/15"
                  />
                  <span className="text-xs text-ink-subtle">to</span>
                  <input
                    type="time"
                    value={window.close_time ?? "18:00"}
                    onChange={(event) =>
                      updateOpeningHour(window.day_of_week, {
                        close_time: event.target.value,
                      })
                    }
                    className="h-10 rounded-xl border border-line-strong bg-surface px-3 text-sm text-ink outline-none transition focus:border-accent focus:ring-2 focus:ring-accent/15"
                  />
                </div>
              ) : null}
            </div>
          ))}
        </div>
      </section>

      {error ? (
        <p
          role="alert"
          className="rounded-2xl border border-danger/20 bg-danger-soft px-4 py-3 text-sm text-danger"
        >
          {error}
        </p>
      ) : null}

      <div className="flex justify-end">
        <Button type="submit" loading={isSubmitting} className="min-w-44 rounded-full">
          {submitLabel}
        </Button>
      </div>
    </form>
  );
}