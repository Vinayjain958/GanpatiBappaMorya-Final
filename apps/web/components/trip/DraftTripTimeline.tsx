"use client";

import { ArrowDown, ArrowUp, Clock3, MapPin, X } from "lucide-react";
import type { ApiExperienceSummary, CustomActivityRequest, ItineraryPreviewResponse } from "@/types/api";

function priceOf(place: ApiExperienceSummary): number | null {
  return place.price ?? place.maximum_price ?? place.minimum_price ?? null;
}

function timeLabel(value: string) {
  return new Date(value).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

export function DraftTripTimeline({
  experiences,
  customActivities,
  preview,
  previewStatus,
  date,
  onMove,
  onRemoveExperience,
  onRemoveCustom,
}: {
  experiences: ApiExperienceSummary[];
  customActivities: CustomActivityRequest[];
  preview: ItineraryPreviewResponse | null;
  previewStatus: "idle" | "checking" | "checked" | "error";
  date: string;
  onMove: (index: number, direction: -1 | 1) => void;
  onRemoveExperience: (id: string) => void;
  onRemoveCustom: (clientId: string) => void;
}) {
  if (!experiences.length && !customActivities.length) return null;

  const scheduledRows = preview?.items ?? [];
  const fallbackRows = [
    ...experiences.map((experience) => ({ experience_id: experience.id, client_id: null, title: experience.title })),
    ...customActivities.map((activity) => ({ experience_id: null, client_id: activity.client_id ?? null, title: activity.title })),
  ];
  const rowTitles = scheduledRows.length ? scheduledRows : fallbackRows;
  const knownPrices = experiences.map(priceOf);
  const customPrices = customActivities.map((activity) => activity.estimated_cost ?? (activity.kind === "note" ? 0 : null));
  const costsKnown = [...knownPrices, ...customPrices].every((value) => value != null);
  const roughCost = [...knownPrices, ...customPrices].reduce<number>((total, value) => total + (value ?? 0), 0);
  const roughMinutes = experiences.reduce((total, place) => total + (place.duration_minutes ?? 0), 0)
    + customActivities.reduce((total, activity) => total + activity.duration_minutes, 0);
  const estimatedTotal = preview?.estimated_total_cost;
  const totalMinutes = preview?.total_minutes ?? roughMinutes;
  const scheduleById = new Map(scheduledRows.filter((row) => row.experience_id).map((row) => [row.experience_id!, row]));
  const scheduleByClientId = new Map(scheduledRows.filter((row) => row.client_id).map((row) => [row.client_id!, row]));

  return (
    <section className="space-y-3 rounded-2xl border border-line bg-surface-raised p-4" aria-label="Draft trip timeline">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold text-ink">Your live trip timeline</h3>
          <p className="mt-0.5 text-xs text-ink-muted">
            {previewStatus === "checking" ? "Checking hours, availability, travel and budget…"
              : previewStatus === "checked" && date ? `Schedule checked for ${date}`
                : date ? "Draft schedule updates as you edit stops." : "Choose a date to check the schedule."}
          </p>
        </div>
        <div className="flex flex-wrap gap-2 text-xs">
          <span className="rounded-full bg-pastel-sky/50 px-3 py-1.5 text-ink">{rowTitles.length} stops</span>
          <span className="rounded-full bg-pastel-lemon/60 px-3 py-1.5 text-ink">{totalMinutes} min total</span>
          <span className="rounded-full bg-pastel-rose/50 px-3 py-1.5 text-ink">
            {estimatedTotal != null ? `₹${Math.round(estimatedTotal)} total` : costsKnown ? `₹${Math.round(roughCost)} est. total` : "Some prices unavailable"}
          </span>
        </div>
      </div>

      {previewStatus === "error" ? (
        <p role="status" className="rounded-xl bg-warning-soft px-3 py-2 text-xs text-warning">Live validation is unavailable. The server will still check the plan when you save it.</p>
      ) : null}
      {preview?.demo_schedule_used ? (
        <p role="status" className="rounded-xl border border-highlight/20 bg-pastel-lemon/45 px-3 py-2 text-xs text-ink-muted">
          Demo opening hours and availability are being used for this check. Confirm schedules and bookings with each venue.
        </p>
      ) : null}
      {preview?.valid && preview.travel_time_source === "haversine_estimate" ? (
        <p className="text-xs text-ink-subtle">Travel times use labelled distance estimates because routed times were unavailable.</p>
      ) : null}
      {preview && !preview.valid && preview.issues.length ? (
        <ul className="space-y-1 rounded-xl bg-warning-soft px-3 py-2 text-xs text-warning" aria-label="Schedule checks">
          {preview.issues.slice(0, 3).map((issue, index) => <li key={`${issue.code}-${index}`}>{issue.message}</li>)}
          {preview.issues.length > 3 ? <li>And {preview.issues.length - 3} more checks need attention.</li> : null}
        </ul>
      ) : null}

      <ol className="space-y-2">
        {rowTitles.map((row, orderIndex) => {
          const experienceIndex = experiences.findIndex((place) => place.id === row.experience_id);
          const experience = experiences.find((place) => place.id === row.experience_id);
          const custom = customActivities.find((activity) => activity.client_id === row.client_id);
          const scheduled = row.experience_id ? scheduleById.get(row.experience_id) : row.client_id ? scheduleByClientId.get(row.client_id) : undefined;
          return (
            <li key={row.experience_id ?? row.client_id ?? `${row.title}-${orderIndex}`} className="flex items-center gap-2 rounded-xl border border-line px-3 py-2.5">
              <span className="inline-flex size-7 shrink-0 items-center justify-center rounded-full bg-pastel-lemon/65 text-xs font-semibold text-ink">{orderIndex + 1}</span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-ink">{row.title}</p>
                <p className="mt-0.5 flex flex-wrap gap-x-3 text-xs text-ink-subtle">
                  {experience ? <span className="inline-flex items-center gap-1"><MapPin className="size-3" aria-hidden="true" />{experience.location.locality ?? experience.location.city}</span> : null}
                  {custom?.location_text ? <span className="inline-flex items-center gap-1"><MapPin className="size-3" aria-hidden="true" />{custom.location_text}</span> : null}
                  <span className="inline-flex items-center gap-1"><Clock3 className="size-3" aria-hidden="true" />
                    {scheduled ? `${timeLabel(scheduled.planned_start)}–${timeLabel(scheduled.planned_end)}` : custom ? `${custom.start_time} · ${custom.duration_minutes} min` : `${experience?.duration_minutes ?? 0} min`}
                  </span>
                  {scheduled?.travel_from_previous_minutes != null ? <span>{Math.round(scheduled.travel_from_previous_minutes)} min travel{scheduled.travel_time_source === "haversine_estimate" ? " est." : ""}</span> : null}
                  {custom && custom.kind !== "note" ? <span>Custom stop · travel not checked against catalog</span> : null}
                </p>
              </div>
              {experienceIndex >= 0 ? (
                <div className="flex shrink-0 items-center gap-1">
                  <button type="button" disabled={experienceIndex === 0} onClick={() => onMove(experienceIndex, -1)} aria-label={`Move ${row.title} earlier`} className="inline-flex size-8 items-center justify-center rounded-full text-ink-subtle hover:bg-pastel-lemon/50 disabled:opacity-35"><ArrowUp className="size-4" aria-hidden="true" /></button>
                  <button type="button" disabled={experienceIndex === experiences.length - 1} onClick={() => onMove(experienceIndex, 1)} aria-label={`Move ${row.title} later`} className="inline-flex size-8 items-center justify-center rounded-full text-ink-subtle hover:bg-pastel-lemon/50 disabled:opacity-35"><ArrowDown className="size-4" aria-hidden="true" /></button>
                  <button type="button" onClick={() => onRemoveExperience(row.experience_id!)} aria-label={`Remove ${row.title}`} className="inline-flex size-8 items-center justify-center rounded-full text-ink-subtle hover:bg-pastel-rose hover:text-ink"><X className="size-4" aria-hidden="true" /></button>
                </div>
              ) : custom?.client_id ? (
                <button type="button" onClick={() => onRemoveCustom(custom.client_id!)} aria-label={`Remove ${row.title}`} className="inline-flex size-8 shrink-0 items-center justify-center rounded-full text-ink-subtle hover:bg-pastel-rose hover:text-ink"><X className="size-4" aria-hidden="true" /></button>
              ) : null}
            </li>
          );
        })}
      </ol>
    </section>
  );
}
