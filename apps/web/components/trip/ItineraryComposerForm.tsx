"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Crosshair, ExternalLink, MapPin, Navigation, Plus, Search } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import { TripDiscoveryPanel } from "@/components/trip/TripDiscoveryPanel";
import { DraftTripTimeline } from "@/components/trip/DraftTripTimeline";
import { TripAddOnsPanel } from "@/components/trip/TripAddOnsPanel";
import { ApiError } from "@/lib/api/client";
import { composeItinerary, previewItinerary } from "@/lib/api/itineraries";
import { reverseGeocode, searchLocation } from "@/lib/api/location";
import { buildGoogleMapsDirectionsUrlFromStops } from "@/lib/itinerary/activeTripProgress";
import { useUserLocation } from "@/hooks/useUserLocation";
import type { GoogleMapsRouteStop } from "@/lib/itinerary/activeTripProgress";
import type { LocationSearchResult } from "@/types/location";
import { isCompositionFailure } from "@/types/api";
import type { ApiExperienceSummary } from "@/types/api";
import type {
  ApiItinerary,
  CompositionPace,
  CompositionValidationResponse,
  CustomActivityRequest,
  ItineraryPreviewResponse,
} from "@/types/api";

const REASON_LABELS: Record<string, string> = {
  OPENING_HOURS_CONFLICT: "isn't open during your chosen time window",
  OPENING_HOURS_UNAVAILABLE: "has no recorded opening hours to verify",
  AVAILABILITY_CONFLICT: "has no bookable slot in your chosen time window",
  AVAILABILITY_UNAVAILABLE: "has no availability data on record",
  BUDGET_EXCEEDED: "costs more than your budget allows",
  PRICE_UNAVAILABLE: "has no listed price to verify against your budget",
  DURATION_EXCEEDED: "takes longer than your available time",
  TRAVEL_TIME_EXCEEDED: "is too far to reach in time",
  GROUP_SIZE_EXCEEDS_CAPACITY: "can't accommodate your group size",
  CAPACITY_UNAVAILABLE: "has no capacity data on record",
};

/**
 * Builds a message from backend reason codes and response data.
 */
function describeCompositionFailure(
  result: CompositionValidationResponse,
): string {
  if (result.candidate_count === 0) {
    return "No matching places were found. Search for an address or place above to add it to your plan, or broaden your search.";
  }

  if (result.feasible_count === 0) {
    const blockers = [...new Set(result.issues.map((issue) => issue.message.trim()).filter(Boolean))].slice(0, 2);
    const details = blockers.length ? ` Main checks: ${blockers.join(" ")}` : "";
    return `Found ${result.candidate_count} matching places, but none passed all schedule checks.${details} Review the date, time window, budget, opening hours, and availability, then try again.`;
  }

  const reasonCounts = new Map<string, number>();
  for (const issue of result.issues) {
    const reasons = (issue.evidence.reasons as string[] | undefined) ?? [
      issue.code,
    ];
    for (const reason of reasons) {
      reasonCounts.set(reason, (reasonCounts.get(reason) ?? 0) + 1);
    }
  }

  const topReason = [...reasonCounts.entries()].sort(
    (a, b) => b[1] - a[1],
  )[0]?.[0];
  const explanation = topReason ? REASON_LABELS[topReason] : undefined;

  if (explanation) {
    return `Found ${result.feasible_count} matching experiences, but the best available option ${explanation}. Try a different time window or budget.`;
  }

  const validationMessages = [...new Set(
    result.issues.map((issue) => issue.message.trim()).filter(Boolean),
  )].slice(0, 2);
  if (validationMessages.length) {
    return `The plan failed its final checks: ${validationMessages.join(" ")}`;
  }

  return result.message.trim()
    || `Found ${result.feasible_count} matching experiences, but couldn't fit them into a valid plan for the given constraints.`;
}

/**
 * Sends composition parameters to the backend. Feasibility, ordering, and
 * timing decisions remain server-side.
 */
export function ItineraryComposerForm({
  onComposed,
}: {
  onComposed: (itinerary: ApiItinerary, startingPoint: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<string | null>(null);
  const [city, setCity] = useState<string | null>(null);
  const [locality, setLocality] = useState<string | null>(null);
  const [selectedExperiences, setSelectedExperiences] = useState<ApiExperienceSummary[]>([]);
  const [customActivities, setCustomActivities] = useState<CustomActivityRequest[]>([]);
  const [date, setDate] = useState("");
  const [startTime, setStartTime] = useState("09:00");
  const [endTime, setEndTime] = useState("18:00");
  const [maxExperiences, setMaxExperiences] = useState(4);
  const [maxBudget, setMaxBudget] = useState("");
  const [startingPoint, setStartingPoint] = useState("");
  const [startingPointCatalog, setStartingPointCatalog] = useState<ApiExperienceSummary[]>([]);
  const [startingPointFocused, setStartingPointFocused] = useState(false);
  const [addressResults, setAddressResults] = useState<LocationSearchResult[]>([]);
  const [addressSearchLoading, setAddressSearchLoading] = useState(false);
  const [addressSearchError, setAddressSearchError] = useState<string | null>(null);
  const userLocation = useUserLocation();
  const [pace, setPace] = useState<CompositionPace>("balanced");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [validationMessage, setValidationMessage] = useState<string | null>(
    null,
  );
  const [previewResult, setPreviewResult] = useState<{ key: string; value: ItineraryPreviewResponse } | null>(null);
  const [previewErrorKey, setPreviewErrorKey] = useState<string | null>(null);
  const [customTitle, setCustomTitle] = useState("");
  const [customKind, setCustomKind] = useState<CustomActivityRequest["kind"]>("activity");
  const [customNote, setCustomNote] = useState("");
  const [customLocation, setCustomLocation] = useState("");
  const [customStartTime, setCustomStartTime] = useState("12:00");
  const [customDuration, setCustomDuration] = useState("30");
  const [customCost, setCustomCost] = useState("");
  const lastAutoSyncedDraft = useRef("");
  const matchingStartingPoints = useMemo(() => {
    const term = startingPoint.trim().toLocaleLowerCase();
    if (term.length < 2) return [];
    const unique = new Map<string, { key: string; title: string; detail: string; value: string }>();
    for (const experience of startingPointCatalog) {
      const location = experience.location;
      const place = location.place_name?.trim();
      const address = location.address?.trim();
      const locality = location.locality?.trim();
      const value = [address, place, locality, location.city].filter(Boolean).join(", ");
      const fields = [experience.title, place, address, locality, location.city, location.state];
      if (!fields.some((field) => field?.toLocaleLowerCase().includes(term))) continue;
      const key = location.id || value;
      if (value && !unique.has(key)) {
        unique.set(key, {
          key,
          title: place || experience.title,
          detail: [address && address !== place ? address : null, locality, location.city].filter(Boolean).join(", "),
          value,
        });
      }
    }
    return [...unique.values()].slice(0, 5);
  }, [startingPoint, startingPointCatalog]);
  const hasDraftStops = selectedExperiences.length > 0 || customActivities.length > 0;
  const previewKey = JSON.stringify({
    date, startTime, endTime,
    experienceIds: selectedExperiences.map((experience) => experience.id),
    customActivities, maxExperiences, maxBudget, pace, city, locality,
  });
  const draftCompositionKey = JSON.stringify({
    experienceIds: selectedExperiences.map((experience) => experience.id),
    customActivities,
  });
  const preview = previewResult?.key === previewKey ? previewResult.value : null;
  const previewStatus = !date || !hasDraftStops ? "idle"
    : preview ? "checked"
      : previewErrorKey === previewKey ? "error" : "checking";
  const draftMapsStops: GoogleMapsRouteStop[] = preview?.items.length
    ? preview.items.flatMap<GoogleMapsRouteStop>((item) => {
      const experience = selectedExperiences.find((candidate) => candidate.id === item.experience_id);
      if (experience) return [{ latitude: experience.location.latitude, longitude: experience.location.longitude }];
      const custom = customActivities.find((candidate) => candidate.client_id === item.client_id);
      return custom && custom.kind !== "note" && custom.location_text?.trim()
        ? [{ latitude: null, longitude: null, locationText: custom.location_text }]
        : [];
    })
    : [
      ...selectedExperiences.map((experience) => ({
        startTime: "00:00:00",
        stop: { latitude: experience.location.latitude, longitude: experience.location.longitude },
      })),
      ...customActivities.filter((activity) => activity.kind !== "note" && activity.location_text?.trim()).map((activity) => ({
        startTime: activity.start_time,
        stop: { latitude: null, longitude: null, locationText: activity.location_text },
      })),
    ].sort((first, second) => first.startTime.localeCompare(second.startTime)).map((item) => item.stop);
  const draftMapsUrl = buildGoogleMapsDirectionsUrlFromStops(draftMapsStops, startingPoint);

  useEffect(() => {
    if (!userLocation.coordinate) return;
    const { lat, lng } = userLocation.coordinate;
    const controller = new AbortController();
    reverseGeocode({ lat, lng }, controller.signal)
      .then((response) => {
        if (!controller.signal.aborted) {
          setStartingPoint(response.items[0]?.display_name ?? `${lat.toFixed(5)}, ${lng.toFixed(5)}`);
          setStartingPointFocused(false);
          setAddressResults([]);
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) setStartingPoint(`${lat.toFixed(5)}, ${lng.toFixed(5)}`);
      });
    return () => controller.abort();
  }, [userLocation.coordinate]);

  async function findStartingPointAddresses() {
    const term = startingPoint.trim();
    if (term.length < 3) return;
    setAddressSearchLoading(true);
    setAddressSearchError(null);
    setAddressResults([]);
    try {
      const response = await searchLocation(term);
      setAddressResults(response.items);
      if (!response.items.length) setAddressSearchError("No address suggestions found. Try a nearby landmark or area name.");
    } catch {
      setAddressSearchError("Address search is temporarily unavailable. You can still choose a catalog suggestion.");
    } finally {
      setAddressSearchLoading(false);
    }
  }

  function chooseAddress(value: string) {
    setStartingPoint(value);
    setStartingPointFocused(false);
    setAddressResults([]);
    setAddressSearchError(null);
  }

  useEffect(() => {
    if (!date || !hasDraftStops) return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      previewItinerary({
        itinerary_date: date,
        start_time: `${startTime}:00`,
        end_time: `${endTime}:00`,
        experience_ids: selectedExperiences.map((experience) => experience.id),
        custom_activities: customActivities,
        max_experiences: maxExperiences,
        max_budget: maxBudget ? Number(maxBudget) : undefined,
        pace,
        city: city || undefined,
        locality: locality || undefined,
      }, controller.signal)
        .then((result) => {
          if (controller.signal.aborted) return;
          setPreviewResult({ key: previewKey, value: result });
          setPreviewErrorKey(null);

          if (lastAutoSyncedDraft.current !== draftCompositionKey) {
            lastAutoSyncedDraft.current = draftCompositionKey;
            if (!maxBudget.trim() && result.estimated_total_cost != null) {
              setMaxBudget(String(Math.ceil(result.estimated_total_cost)));
            }
            const latestEnd = result.items.reduce<string | null>((latest, item) => {
              const timeValue = item.planned_end.slice(11, 16);
              if (!/^\d{2}:\d{2}$/.test(timeValue)) return latest;
              return !latest || timeValue > latest ? timeValue : latest;
            }, null);
            if (latestEnd && latestEnd !== endTime) setEndTime(latestEnd);
          }
        })
        .catch(() => {
          if (!controller.signal.aborted) {
            setPreviewErrorKey(previewKey);
          }
        });
    }, 250);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [date, hasDraftStops, startTime, endTime, selectedExperiences, customActivities, maxExperiences, maxBudget, pace, city, locality, previewKey, draftCompositionKey]);

  function moveExperience(index: number, direction: -1 | 1) {
    setSelectedExperiences((current) => {
      const target = index + direction;
      if (target < 0 || target >= current.length) return current;
      const updated = [...current];
      [updated[index], updated[target]] = [updated[target], updated[index]];
      return updated;
    });
  }

  function toggleExperience(experience: ApiExperienceSummary) {
    const alreadySelected = selectedExperiences.some((item) => item.id === experience.id);
    const updated = alreadySelected
      ? selectedExperiences.filter((item) => item.id !== experience.id)
      : [...selectedExperiences, experience];
    setSelectedExperiences(updated);
    if (updated.length) setMaxExperiences(updated.length);
  }

  function removeExperience(experienceId: string) {
    const updated = selectedExperiences.filter((item) => item.id !== experienceId);
    setSelectedExperiences(updated);
    setMaxExperiences(Math.max(1, updated.length));
  }

  function useItineraryIdea(
    experiences: ApiExperienceSummary[],
    selectedLocality: string | null,
    selectedCity: string,
    totalMinutes: number | null,
    estimatedCost: number | null,
  ) {
    setSelectedExperiences(experiences);
    setCity(selectedCity);
    setLocality(selectedLocality);
    setMaxExperiences(Math.max(1, experiences.length));

    if (totalMinutes != null && totalMinutes > 0) {
      const [startHour, startMinute] = startTime.split(":").map(Number);
      const requiredEnd = Math.min(23 * 60 + 59, startHour * 60 + startMinute + Math.ceil(totalMinutes));
      setEndTime(`${String(Math.floor(requiredEnd / 60)).padStart(2, "0")}:${String(requiredEnd % 60).padStart(2, "0")}`);
    }

    // Preserve an explicit budget ceiling; fill it from the selected plan only
    // when the traveler hasn't set one yet.
    if (!maxBudget.trim() && estimatedCost != null) {
      setMaxBudget(String(Math.ceil(estimatedCost)));
    }
  }

  function addCustomActivity() {
    if (!customTitle.trim()) {
      setError("Give your personal stop a title.");
      return;
    }
    setError(null);
    const duration = customKind === "note" ? 0 : Number(customDuration);
    setCustomActivities((current) => [...current, {
      client_id: crypto.randomUUID(),
      title: customTitle.trim(),
      kind: customKind,
      note: customNote.trim() || undefined,
      location_text: customLocation.trim() || undefined,
      start_time: `${customStartTime}:00`,
      duration_minutes: duration,
      estimated_cost: customKind === "note" ? 0 : customCost.trim() ? Number(customCost) : undefined,
    }]);
    setCustomTitle("");
    setCustomNote("");
    setCustomLocation("");
    setCustomCost("");
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();

    if (!date) {
      setError("Please choose a date.");
      return;
    }

    setSubmitting(true);
    setError(null);
    setValidationMessage(null);

    if (selectedExperiences.length > maxExperiences) {
      setValidationMessage(`You selected ${selectedExperiences.length} places. Increase the maximum or remove a few before composing.`);
      setSubmitting(false);
      return;
    }

    try {
      const result = await composeItinerary({
        query: query || undefined,
        itinerary_date: date,
        start_time: `${startTime}:00`,
        end_time: `${endTime}:00`,
        max_experiences: maxExperiences,
        max_budget: maxBudget ? Number(maxBudget) : undefined,
        pace,
        category_slugs: category ? [category] : undefined,
        city: city || undefined,
        locality: locality || undefined,
        experience_ids: selectedExperiences.length
          ? selectedExperiences.map((experience) => experience.id)
          : undefined,
        custom_activities: customActivities,
      });

      if (isCompositionFailure(result)) {
        setValidationMessage(
          describeCompositionFailure(result),
        );
        return;
      }

      onComposed(result, startingPoint.trim());
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Something went wrong. Please try again.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  const controlClassName =
    "w-full rounded-xl border border-line-strong bg-surface-raised px-3.5 py-2.5 text-sm text-ink placeholder:text-ink-subtle focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent";

  return (
    <Card>
      <CardBody className="space-y-5">
        <div className="rounded-2xl bg-pastel-lemon/45 p-4 sm:p-5">
          <h2 className="text-lg font-semibold text-ink">
            Find places, then shape your itinerary
          </h2>
          <p className="mt-1 text-sm leading-6 text-ink-muted">
            Search your interests or an area. Add real catalog experiences and let LocaLens check the schedule before saving.
          </p>
        </div>

        <form className="space-y-4" onSubmit={handleSubmit}>
          <div className="grid grid-cols-1 gap-3 rounded-2xl border border-line bg-surface-raised p-4 sm:grid-cols-2">
            <label className="block text-sm">
              <span className="mb-1.5 block font-medium text-ink">Date</span>
              <input type="date" className={controlClassName} value={date} onChange={(event) => setDate(event.target.value)} required />
            </label>
            <label className="block text-sm">
              <span className="mb-1.5 block font-medium text-ink">Max experiences</span>
              <input type="number" min={1} max={20} className={controlClassName} value={maxExperiences} onChange={(event) => setMaxExperiences(Number(event.target.value))} />
            </label>
            <label className="block text-sm">
              <span className="mb-1.5 block font-medium text-ink">Start time</span>
              <input type="time" className={controlClassName} value={startTime} onChange={(event) => setStartTime(event.target.value)} />
            </label>
            <label className="block text-sm">
              <span className="mb-1.5 block font-medium text-ink">End time</span>
              <input type="time" className={controlClassName} value={endTime} onChange={(event) => setEndTime(event.target.value)} />
            </label>
            <label className="block text-sm">
              <span className="mb-1.5 block font-medium text-ink">Max budget (INR)</span>
              <input type="number" min={0} className={controlClassName} value={maxBudget} onChange={(event) => setMaxBudget(event.target.value)} placeholder="No limit" />
            </label>
            <label className="block text-sm">
              <span className="mb-1.5 block font-medium text-ink">Pace</span>
              <select className={controlClassName} value={pace} onChange={(event) => setPace(event.target.value as CompositionPace)}>
                <option value="relaxed">Relaxed</option>
                <option value="balanced">Balanced</option>
                <option value="packed">Packed</option>
              </select>
            </label>
          </div>

          <label className="block text-sm">
            <span className="mb-1.5 block font-medium text-ink">Starting point</span>
            <div className="relative">
              <MapPin className="pointer-events-none absolute left-4 top-1/2 size-4 -translate-y-1/2 text-ink-subtle" aria-hidden="true" />
              <input
                role="combobox"
                aria-expanded={startingPointFocused && (matchingStartingPoints.length > 0 || addressResults.length > 0)}
                aria-controls="starting-point-suggestions"
                aria-autocomplete="list"
                className={`${controlClassName} rounded-full py-3 pl-11 pr-12`}
                value={startingPoint}
                onChange={(event) => {
                  setStartingPoint(event.target.value);
                  setStartingPointFocused(true);
                  setAddressResults([]);
                  setAddressSearchError(null);
                  userLocation.clear();
                }}
                onFocus={() => setStartingPointFocused(true)}
                onBlur={() => setTimeout(() => setStartingPointFocused(false), 160)}
                placeholder="Search hotel / location"
                maxLength={300}
                autoComplete="off"
              />
              <button
                type="button"
                onClick={() => {
                  setAddressSearchError(null);
                  userLocation.request();
                }}
                disabled={userLocation.status === "loading"}
                aria-label="Use current location as starting point"
                title="Use current location"
                className="absolute right-2 top-1/2 inline-flex size-9 -translate-y-1/2 items-center justify-center rounded-full text-accent transition hover:bg-pastel-lemon/60 focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent disabled:opacity-50"
              >
                <Crosshair className={`size-4 ${userLocation.status === "loading" ? "animate-pulse" : ""}`} aria-hidden="true" />
              </button>
              {startingPointFocused && startingPoint.trim().length >= 2 ? (
                <div
                  id="starting-point-suggestions"
                  role="listbox"
                  className="absolute inset-x-0 top-[calc(100%+0.4rem)] z-40 max-h-72 overflow-y-auto rounded-2xl border border-line bg-surface-raised p-2 shadow-xl"
                >
                  {matchingStartingPoints.length ? (
                    <div>
                      <p className="px-3 pb-1 pt-1 text-[11px] font-semibold uppercase tracking-wide text-ink-subtle">Places and addresses nearby</p>
                      {matchingStartingPoints.map((suggestion) => (
                        <button
                          key={suggestion.key}
                          type="button"
                          role="option"
                          aria-selected={false}
                          onMouseDown={(event) => event.preventDefault()}
                          onClick={() => chooseAddress(suggestion.value)}
                          className="flex w-full items-start gap-2.5 rounded-xl px-3 py-2.5 text-left text-sm text-ink transition hover:bg-pastel-lemon/45"
                        >
                          <MapPin className="mt-0.5 size-4 shrink-0 text-accent" aria-hidden="true" />
                          <span className="min-w-0">
                            <span className="block truncate font-medium">{suggestion.title}</span>
                            {suggestion.detail ? <span className="mt-0.5 block truncate text-xs text-ink-muted">{suggestion.detail}</span> : null}
                          </span>
                        </button>
                      ))}
                    </div>
                  ) : null}
                  {addressResults.map((place) => (
                    <button
                      key={`${place.lat},${place.lng}`}
                      type="button"
                      role="option"
                      aria-selected={false}
                      onMouseDown={(event) => event.preventDefault()}
                      onClick={() => chooseAddress(place.display_name)}
                      className="flex w-full items-start gap-2.5 rounded-xl px-3 py-2.5 text-left text-sm text-ink transition hover:bg-pastel-lemon/45"
                    >
                      <MapPin className="mt-0.5 size-4 shrink-0 text-accent" aria-hidden="true" />
                      <span className="line-clamp-2">{place.display_name}</span>
                    </button>
                  ))}
                  {startingPoint.trim().length >= 3 ? (
                    <button
                      type="button"
                      onMouseDown={(event) => event.preventDefault()}
                      onClick={() => void findStartingPointAddresses()}
                      disabled={addressSearchLoading}
                      className="mt-1 flex w-full items-center gap-2 rounded-xl border-t border-line px-3 py-2.5 text-left text-xs font-medium text-accent hover:bg-pastel-lemon/35 disabled:opacity-60"
                    >
                      <Search className="size-3.5" aria-hidden="true" />
                      {addressSearchLoading ? "Searching addresses…" : `Search addresses for “${startingPoint.trim()}”`}
                    </button>
                  ) : null}
                  {addressSearchError ? <p className="px-3 py-2 text-xs text-ink-muted" role="status">{addressSearchError}</p> : null}
                </div>
              ) : null}
            </div>
            <p className="mt-1.5 text-xs text-ink-subtle">Choose a catalog suggestion, search another address, or use your current location.</p>
            {userLocation.status === "loading" ? <p className="mt-1 text-xs text-accent" role="status">Finding your current location…</p> : null}
            {userLocation.status === "denied" ? <p className="mt-1 text-xs text-warning" role="status">Location permission was denied. You can still enter an address.</p> : null}
            {userLocation.status === "error" ? <p className="mt-1 text-xs text-warning" role="status">{userLocation.error ?? "Could not read your location. Enter an address instead."}</p> : null}
            {addressSearchError && !startingPointFocused ? <p className="mt-1 text-xs text-warning" role="status">{addressSearchError}</p> : null}
          </label>

          <TripDiscoveryPanel
            query={query}
            onQueryChange={setQuery}
            category={category}
            onCategoryChange={setCategory}
            city={city}
            onCityChange={setCity}
            locality={locality}
            onLocalityChange={setLocality}
            selectedIds={selectedExperiences.map((experience) => experience.id)}
            maxBudget={maxBudget}
            maxStops={maxExperiences}
            itineraryDate={date}
            startTime={startTime}
            endTime={endTime}
            onLocationCatalogLoaded={setStartingPointCatalog}
            onToggleExperience={toggleExperience}
            onUseIdea={useItineraryIdea}
          />

          <div className="space-y-3">
            <div>
              <h3 className="text-lg font-semibold text-ink">Your itinerary</h3>
              <p className="mt-1 text-sm text-ink-muted">Build a route from the area ideas above, then fine-tune the stops and nearby add-ons here.</p>
            </div>
            <div className="grid gap-4 xl:grid-cols-[minmax(0,1.35fr)_minmax(19rem,0.85fr)] xl:items-start">
              <div className="min-w-0">
                {hasDraftStops ? (
                  <DraftTripTimeline
                    experiences={selectedExperiences}
                    customActivities={customActivities}
                    preview={preview}
                    previewStatus={previewStatus}
                    date={date}
                    onMove={moveExperience}
                    onRemoveExperience={removeExperience}
                    onRemoveCustom={(clientId) => setCustomActivities((current) => current.filter((activity) => activity.client_id !== clientId))}
                  />
                ) : (
                  <section className="flex h-full min-h-48 flex-col justify-center rounded-2xl border border-dashed border-line-strong bg-surface-raised p-5" aria-label="Draft itinerary">
                    <h3 className="font-semibold text-ink">Your itinerary plan</h3>
                    <p className="mt-1 text-sm leading-5 text-ink-muted">Choose a checked area route or add places to build a personal plan. Your schedule and estimated total appear here.</p>
                  </section>
                )}
              </div>
              <TripAddOnsPanel
                mode="draft"
                city={city}
                locality={locality}
                origin={selectedExperiences[0] ? {
                  latitude: selectedExperiences[0].location.latitude,
                  longitude: selectedExperiences[0].location.longitude,
                } : null}
                selectedExperienceIds={selectedExperiences.map((experience) => experience.id)}
                onToggleExperience={toggleExperience}
              />
            </div>
          </div>

          <section className="hidden space-y-3 rounded-2xl border border-line bg-surface-raised p-4" aria-label="Add a personal stop">
            <div>
              <h3 className="font-semibold text-ink">Add a personal stop or note</h3>
              <p className="mt-0.5 text-xs text-ink-muted">Saved with this itinerary. Personal stops stay separate from catalog places.</p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="block text-sm sm:col-span-2">
                <span className="mb-1.5 block font-medium text-ink">Title</span>
                <input className={controlClassName} value={customTitle} onChange={(event) => setCustomTitle(event.target.value)} placeholder="Meet a friend, visit a local shop…" maxLength={200} />
              </label>
              <label className="block text-sm">
                <span className="mb-1.5 block font-medium text-ink">Entry type</span>
                <select className={controlClassName} value={customKind} onChange={(event) => setCustomKind(event.target.value as CustomActivityRequest["kind"])}>
                  <option value="place">Personal place</option>
                  <option value="activity">Personal activity</option>
                  <option value="note">Note only</option>
                </select>
              </label>
              <label className="block text-sm">
                <span className="mb-1.5 block font-medium text-ink">Start time</span>
                <input type="time" className={controlClassName} value={customStartTime} onChange={(event) => setCustomStartTime(event.target.value)} />
              </label>
              <label className="block text-sm">
                <span className="mb-1.5 block font-medium text-ink">Duration (minutes)</span>
                <input type="number" min={0} max={720} disabled={customKind === "note"} className={controlClassName} value={customKind === "note" ? 0 : customDuration} onChange={(event) => setCustomDuration(event.target.value)} />
              </label>
              <label className="block text-sm">
                <span className="mb-1.5 block font-medium text-ink">Estimated cost (INR)</span>
                <input type="number" min={0} disabled={customKind === "note"} className={controlClassName} value={customKind === "note" ? 0 : customCost} onChange={(event) => setCustomCost(event.target.value)} placeholder="Optional" />
              </label>
              <label className="block text-sm">
                <span className="mb-1.5 block font-medium text-ink">Location or address</span>
                <input className={controlClassName} value={customLocation} onChange={(event) => setCustomLocation(event.target.value)} placeholder="Optional" maxLength={300} />
              </label>
              <label className="block text-sm sm:col-span-2">
                <span className="mb-1.5 block font-medium text-ink">Note</span>
                <textarea className={`${controlClassName} min-h-20 resize-y`} value={customNote} onChange={(event) => setCustomNote(event.target.value)} maxLength={2000} placeholder="Anything you want to remember" />
              </label>
            </div>
            <Button type="button" variant="outline" size="sm" onClick={addCustomActivity}>
              <Plus className="size-4" aria-hidden="true" /> Add to timeline
            </Button>
          </section>

          {error ? <p className="text-sm text-danger">{error}</p> : null}

          {validationMessage ? (
            <p className="rounded-xl bg-warning-soft px-3.5 py-3 text-sm text-warning">
              {validationMessage}
            </p>
          ) : null}

          <Button type="submit" loading={submitting} className="w-full">
            Compose itinerary
          </Button>

          <div className="flex justify-center">
            {draftMapsUrl ? (
              <a href={draftMapsUrl} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-10 items-center justify-center gap-2 rounded-full border border-line-strong bg-surface px-4 text-sm font-medium text-ink transition hover:bg-surface-sunken focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent">
                <Navigation className="size-4" aria-hidden="true" /> Google Maps directions <ExternalLink className="size-3.5" aria-hidden="true" />
              </a>
            ) : (
              <button type="button" disabled className="inline-flex min-h-10 items-center justify-center gap-2 rounded-full border border-line bg-surface-raised px-4 text-sm font-medium text-ink-subtle disabled:opacity-60">
                <Navigation className="size-4" aria-hidden="true" /> Google Maps directions
              </button>
            )}
          </div>
        </form>
      </CardBody>
    </Card>
  );
}
