"use client";

import { useEffect, useMemo, useState } from "react";
import { MapPin, Search } from "lucide-react";
import { Card, CardBody } from "@/components/ui/Card";
import { listAvailableCategories, listCategories, type ApiCategory } from "@/lib/api/categories";
import { listAllExperiences, listExperiences } from "@/lib/api/experiences";
import { previewItineraryIdeas } from "@/lib/api/itineraries";
import { buildItineraryIdeas } from "@/lib/trip/itineraryIdeas";
import type { ApiExperienceSummary } from "@/types/api";
import type { ItineraryPreviewResponse } from "@/types/api";

const PAGE_SIZE = 24;

type CatalogLocationSuggestion = {
  key: string;
  city: string;
  locality: string | null;
  title: string;
  address: string | null;
  priority: number;
};

function experienceSearchFields(experience: ApiExperienceSummary) {
  return [
    experience.title,
    experience.short_description,
    experience.category.name,
    experience.location.place_name,
    experience.location.address,
    experience.location.locality,
    experience.location.city,
    experience.location.state,
  ].filter((value): value is string => Boolean(value)).map((value) => value.toLocaleLowerCase());
}

function durationText(minutes: number | null) {
  if (minutes == null) return "Time unavailable";
  const hours = Math.floor(minutes / 60);
  const remainder = minutes % 60;
  return hours ? `${hours}h ${remainder ? `${remainder}m` : ""}` : `${remainder}m`;
}

function timeWindowMinutes(startTime: string, endTime: string): number | undefined {
  const [startHour, startMinute] = startTime.split(":").map(Number);
  const [endHour, endMinute] = endTime.split(":").map(Number);
  const minutes = endHour * 60 + endMinute - (startHour * 60 + startMinute);
  return Number.isFinite(minutes) && minutes > 0 ? minutes : undefined;
}

export function TripDiscoveryPanel({
  query,
  onQueryChange,
  category,
  onCategoryChange,
  city,
  onCityChange,
  locality,
  onLocalityChange,
  selectedIds,
  maxBudget,
  maxStops,
  itineraryDate,
  startTime,
  endTime,
  onLocationCatalogLoaded,
  onToggleExperience,
  onUseIdea,
}: {
  query: string;
  onQueryChange: (value: string) => void;
  category: string | null;
  onCategoryChange: (value: string | null) => void;
  city: string | null;
  onCityChange: (value: string | null) => void;
  locality: string | null;
  onLocalityChange: (value: string | null) => void;
  selectedIds: string[];
  maxBudget: string;
  maxStops: number;
  itineraryDate: string;
  startTime: string;
  endTime: string;
  onLocationCatalogLoaded: (experiences: ApiExperienceSummary[]) => void;
  onToggleExperience: (experience: ApiExperienceSummary) => void;
  onUseIdea: (
    experiences: ApiExperienceSummary[],
    locality: string | null,
    city: string,
    totalMinutes: number | null,
    estimatedCost: number | null,
  ) => void;
}) {
  const [categories, setCategories] = useState<ApiCategory[]>([]);
  const [areaCategories, setAreaCategories] = useState<ApiCategory[]>([]);
  const [experiences, setExperiences] = useState<ApiExperienceSummary[]>([]);
  const [locationCatalog, setLocationCatalog] = useState<ApiExperienceSummary[]>([]);
  const [locationCatalogStatus, setLocationCatalogStatus] = useState<"loading" | "ready" | "error">("loading");
  const [ideaExperiences, setIdeaExperiences] = useState<ApiExperienceSummary[]>([]);
  const [ideaDataStatus, setIdeaDataStatus] = useState<"loading" | "ready" | "error">("loading");
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [queryFocused, setQueryFocused] = useState(false);
  const [visibleIdeas, setVisibleIdeas] = useState(4);
  const [ideaPreviewResult, setIdeaPreviewResult] = useState<{ key: string; value: Record<string, ItineraryPreviewResponse> } | null>(null);
  const [ideaPreviewErrorKey, setIdeaPreviewErrorKey] = useState<string | null>(null);
  const budgetLimit = maxBudget.trim() ? Number(maxBudget) : undefined;

  useEffect(() => {
    listCategories()
      .then(setCategories)
      .catch(() => setCategories([]));
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    listAllExperiences({ is_synthetic: false, sort: "relevance" }, controller.signal)
      .then((items) => {
        if (!controller.signal.aborted) {
          setLocationCatalog(items);
          onLocationCatalogLoaded(items);
          setLocationCatalogStatus("ready");
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) setLocationCatalogStatus("error");
      });
    return () => controller.abort();
  }, [onLocationCatalogLoaded]);

  useEffect(() => {
    if (!city && !locality) return;
    const controller = new AbortController();
    listAvailableCategories({ city, locality }, controller.signal)
      .then(setAreaCategories)
      .catch(() => {
        if (!controller.signal.aborted) setAreaCategories([]);
      });
    return () => controller.abort();
  }, [city, locality]);

  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(() => {
      setStatus("loading");
      setExperiences([]);
      setVisibleIdeas(4);
      listExperiences(
        {
          q: query.trim() || undefined,
          category: category ?? undefined,
          city: city ?? undefined,
          locality: locality ?? undefined,
          max_price: budgetLimit != null && Number.isFinite(budgetLimit) ? budgetLimit : undefined,
          is_synthetic: false,
          limit: PAGE_SIZE,
          offset: 0,
          sort: "relevance",
        },
        controller.signal,
      )
        .then((response) => {
          setExperiences(response.items);
          setStatus("ready");
        })
        .catch(() => {
          if (!controller.signal.aborted) setStatus("error");
        });
    }, query.trim() ? 220 : 0);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query, category, city, locality, budgetLimit]);

  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(() => {
      setIdeaDataStatus("loading");
      listAllExperiences({
        q: query.trim() || undefined,
        category: category ?? undefined,
        city: city ?? undefined,
        locality: locality ?? undefined,
        max_price: budgetLimit != null && Number.isFinite(budgetLimit) ? budgetLimit : undefined,
        is_synthetic: false,
        sort: "relevance",
      }, controller.signal)
        .then((items) => {
          if (!controller.signal.aborted) {
            setIdeaExperiences(items);
            setIdeaDataStatus("ready");
            setVisibleIdeas(4);
          }
        })
        .catch(() => {
          if (!controller.signal.aborted) {
            setIdeaExperiences([]);
            setIdeaDataStatus("error");
          }
        });
    }, query.trim() ? 250 : 0);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query, category, city, locality, budgetLimit]);

  const ideas = useMemo(() => buildItineraryIdeas(ideaExperiences, {
    maxIdeas: 200,
    maxIdeasPerLocation: 2,
    maxStops,
    maxBudget: budgetLimit,
    availableMinutes: timeWindowMinutes(startTime, endTime),
  }), [ideaExperiences, maxStops, budgetLimit, startTime, endTime]);
  const locations = useMemo((): CatalogLocationSuggestion[] => {
    const term = query.trim().toLocaleLowerCase();
    if (!term) return [];
    const suggestions = new Map<string, CatalogLocationSuggestion>();
    for (const experience of locationCatalog) {
      const location = experience.location;
      const locality = location.locality?.trim() || null;
      const areaLabel = [locality, location.city].filter(Boolean).join(", ");
      const areaMatches = [locality, location.city, location.state]
        .some((value) => value?.toLocaleLowerCase().includes(term));
      const placeName = location.place_name?.trim() || null;
      const address = location.address?.trim() || null;
      const placeMatches = [placeName, address]
        .some((value) => value?.toLocaleLowerCase().includes(term));

      if (areaMatches) {
        const key = `area:${location.city}:${locality ?? ""}`;
        suggestions.set(key, { key, city: location.city, locality, title: areaLabel, address: null, priority: 0 });
      }
      if (placeMatches) {
        const key = `place:${location.id}`;
        suggestions.set(key, {
          key,
          city: location.city,
          locality,
          title: placeName ?? address ?? areaLabel,
          address: address && address !== placeName ? address : null,
          priority: 1,
        });
      }
    }
    return [...suggestions.values()]
      .sort((first, second) => first.priority - second.priority || first.title.localeCompare(second.title))
      .slice(0, 5);
  }, [locationCatalog, query]);

  const availableCategories = city || locality ? areaCategories : categories;
  const matchingCategories = useMemo(() => {
    const term = query.trim().toLocaleLowerCase();
    return availableCategories
      .filter((item) => !term || item.name.toLocaleLowerCase().includes(term) || item.slug.includes(term))
      .slice(0, 8);
  }, [availableCategories, query]);
  const matchingExperiences = useMemo(() => {
    const term = query.trim().toLocaleLowerCase();
    if (!term) return experiences.slice(0, 4);
    const candidates = locationCatalog.length ? locationCatalog : experiences;
    const budget = maxBudget.trim() ? Number(maxBudget) : undefined;
    return candidates
      .filter((experience) => experienceSearchFields(experience).some((field) => field.includes(term)))
      .filter((experience) => !category || experience.category.slug === category)
      .filter((experience) => !city || experience.location.city === city)
      .filter((experience) => !locality || experience.location.locality === locality)
      .filter((experience) => {
        const price = experience.price ?? experience.maximum_price ?? experience.minimum_price;
        return budget == null || !Number.isFinite(budget) || price == null || price <= budget;
      })
      .sort((first, second) => {
        const score = (experience: ApiExperienceSummary) => {
          const title = experience.title.toLocaleLowerCase();
          const placeName = experience.location.place_name?.toLocaleLowerCase() ?? "";
          const address = experience.location.address?.toLocaleLowerCase() ?? "";
          if (title.startsWith(term)) return 0;
          if (placeName.startsWith(term) || address.startsWith(term)) return 1;
          if (experience.location.locality?.toLocaleLowerCase().startsWith(term)) return 2;
          return 3;
        };
        return score(first) - score(second);
      })
      .slice(0, 4);
  }, [experiences, locationCatalog, query, category, city, locality, maxBudget]);

  const ideaPreviewKey = JSON.stringify({
    itineraryDate, startTime, endTime,
    plans: ideas.map((idea) => idea.experienceIds),
    maxStops, budgetLimit, city, locality,
  });
  const ideaPreviews = ideaPreviewResult?.key === ideaPreviewKey ? ideaPreviewResult.value : {};
  const ideasStatus = !itineraryDate || !ideas.length ? "idle"
    : ideaDataStatus === "loading" ? "loading"
      : ideaPreviewResult?.key === ideaPreviewKey ? "ready"
        : ideaPreviewErrorKey === ideaPreviewKey ? "error" : "checking";

  useEffect(() => {
    if (!itineraryDate || !ideas.length || ideaDataStatus !== "ready") return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      previewItineraryIdeas({
        base: {
          itinerary_date: itineraryDate,
          start_time: `${startTime}:00`,
          end_time: `${endTime}:00`,
          max_experiences: maxStops,
          max_budget: budgetLimit != null && Number.isFinite(budgetLimit) ? budgetLimit : undefined,
          pace: "balanced",
          city: city || undefined,
          locality: locality || undefined,
        },
        plans: ideas.map((idea) => idea.experienceIds),
      }, controller.signal)
        .then((previews) => {
          const keyed = ideas.reduce<Record<string, ItineraryPreviewResponse>>((items, idea, index) => {
            const preview = previews[index];
            if (preview) items[idea.id] = preview;
            return items;
          }, {});
          setIdeaPreviewResult({ key: ideaPreviewKey, value: keyed });
          setIdeaPreviewErrorKey(null);
        })
        .catch(() => {
          if (!controller.signal.aborted) {
            setIdeaPreviewErrorKey(ideaPreviewKey);
          }
        });
    }, 400);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [itineraryDate, startTime, endTime, ideas, ideaDataStatus, maxStops, budgetLimit, city, locality, ideaPreviewKey]);

  const readyIdeas = ideaDataStatus === "ready" ? ideas : [];

  function selectLocation(selectedCity: string, selectedLocality: string | null) {
    onCityChange(selectedCity);
    onLocalityChange(selectedLocality);
    onQueryChange("");
    setQueryFocused(false);
  }

  return (
    <section className="space-y-5" aria-label="Trip discovery">
      <div className="space-y-3">
        <label className="block text-sm font-medium text-ink" htmlFor="trip-discovery-query">
          What would you like to explore?
        </label>
        <div className="relative">
          <Search className="pointer-events-none absolute left-4 top-1/2 size-4 -translate-y-1/2 text-ink-subtle" aria-hidden="true" />
          <input
            id="trip-discovery-query"
            role="combobox"
            className="w-full rounded-full border border-line-strong bg-surface-raised py-3 pl-11 pr-4 text-sm text-ink placeholder:text-ink-subtle focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
            value={query}
            onChange={(event) => { setStatus("loading"); onQueryChange(event.target.value); }}
            onFocus={() => setQueryFocused(true)}
            onBlur={() => setTimeout(() => setQueryFocused(false), 150)}
            autoComplete="off"
            aria-expanded={queryFocused && Boolean(query.trim())}
            aria-controls="trip-discovery-suggestions"
            aria-autocomplete="list"
            placeholder="Search an interest, area, or place…"
          />
          {queryFocused && query.trim() ? (
            <div
              id="trip-discovery-suggestions"
              role="listbox"
              className="absolute inset-x-0 top-[calc(100%+0.5rem)] z-30 max-h-80 overflow-y-auto rounded-2xl border border-line bg-surface-raised p-3 shadow-xl"
            >
              {matchingCategories.length || locations.length || matchingExperiences.length || locationCatalogStatus === "loading" ? (
                <div className="space-y-3">
                  {locationCatalogStatus === "loading" ? (
                    <p className="px-2 text-xs text-ink-subtle" role="status">Searching catalog addresses and places…</p>
                  ) : null}
                  {locations.length ? (
                    <div>
                      <p className="px-2 pb-1 text-xs font-semibold uppercase tracking-wide text-ink-subtle">Locations and addresses</p>
                      {locations.map((item) => (
                        <button
                          key={item.key}
                          type="button"
                          role="option"
                          aria-selected={city === item.city && locality === item.locality}
                          onMouseDown={(event) => event.preventDefault()}
                          onClick={() => selectLocation(item.city, item.locality)}
                          className="flex w-full items-start gap-2 rounded-xl px-3 py-2 text-left text-sm text-ink hover:bg-pastel-lemon/45"
                        >
                          <MapPin className="mt-0.5 size-4 shrink-0 text-ink-subtle" aria-hidden="true" />
                          <span className="min-w-0">
                            <span className="block truncate">{item.title}</span>
                            {item.address ? <span className="mt-0.5 block truncate text-xs text-ink-muted">{item.address} · {item.locality ?? item.city}</span> : null}
                          </span>
                        </button>
                      ))}
                    </div>
                  ) : null}
                  {matchingCategories.length ? (
                    <div>
                      <p className="px-2 pb-1 text-xs font-semibold uppercase tracking-wide text-ink-subtle">Explore categories</p>
                      {matchingCategories.slice(0, 4).map((item) => (
                        <button
                          key={item.id}
                          type="button"
                          role="option"
                          aria-selected={category === item.slug}
                          onMouseDown={(event) => event.preventDefault()}
                          onClick={() => {
                            onCategoryChange(item.slug === category ? null : item.slug);
                            setQueryFocused(false);
                          }}
                          className="flex w-full items-center rounded-xl px-3 py-2 text-left text-sm text-ink hover:bg-pastel-lemon/45"
                        >
                          {item.name}
                        </button>
                      ))}
                    </div>
                  ) : null}
                  {matchingExperiences.length ? (
                    <div>
                      <p className="px-2 pb-1 text-xs font-semibold uppercase tracking-wide text-ink-subtle">Experiences from your catalog</p>
                      {matchingExperiences.map((item) => (
                        <button
                          key={item.id}
                          type="button"
                          role="option"
                          aria-selected={selectedIds.includes(item.id)}
                          onMouseDown={(event) => event.preventDefault()}
                          onClick={() => { onToggleExperience(item); setQueryFocused(false); }}
                          className="flex w-full items-start justify-between gap-3 rounded-xl px-3 py-2 text-left hover:bg-pastel-lemon/45"
                        >
                          <span className="min-w-0">
                            <span className="block truncate text-sm font-medium text-ink">{item.title}</span>
                            <span className="mt-0.5 block truncate text-xs text-ink-muted">{item.location.address || [item.location.locality, item.location.city].filter(Boolean).join(", ")}</span>
                          </span>
                          <span className="shrink-0 text-xs text-ink-subtle">{selectedIds.includes(item.id) ? "Added" : "Add"}</span>
                        </button>
                      ))}
                    </div>
                  ) : null}
                </div>
              ) : (
                <p className="px-2 py-3 text-sm text-ink-muted">No matching place or address found. Try a broader search.</p>
              )}
            </div>
          ) : null}
        </div>
        {locality || city ? (
          <div className="flex flex-wrap items-center gap-2 text-xs text-ink-muted">
            <span>Exploring {locality ? `${locality}, ` : ""}{city}</span>
          <button type="button" className="font-medium text-accent hover:underline" onClick={() => { onCityChange(null); onLocalityChange(null); }}>
            Clear location
          </button>
          </div>
        ) : null}
      </div>

      {availableCategories.length ? (
        <div className="space-y-2">
          <p className="text-sm font-medium text-ink">What you can explore{city || locality ? ` in ${locality ?? city}` : ""}</p>
          <div className="flex flex-wrap gap-2">
            {availableCategories.slice(0, 12).map((item) => (
              <button
                key={item.id}
                type="button"
                aria-pressed={category === item.slug}
                onClick={() => onCategoryChange(category === item.slug ? null : item.slug)}
                className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${category === item.slug ? "border-ink bg-ink text-white" : "border-line bg-surface-raised text-ink-muted hover:border-line-strong hover:text-ink"}`}
              >
                {item.name}
              </button>
            ))}
          </div>
        </div>
      ) : null}

      {status === "error" ? (
        <div className="rounded-2xl border border-warning/30 bg-warning-soft px-4 py-3 text-sm text-ink">
          Some recommendations are temporarily unavailable. Your existing itinerary composer is still available below.
          <button type="button" className="ml-2 font-semibold text-accent underline" onClick={() => onQueryChange(`${query} `)}>Try again</button>
        </div>
      ) : null}

      <div className="space-y-3 border-t border-line pt-5">
        <div>
          <h3 className="text-lg font-semibold text-ink">Itinerary ideas by area</h3>
          <p className="mt-1 text-sm text-ink-muted">Up to two distance-aware routes per locality, built from the full set of real catalog places. Times and costs are estimates until the selected date is checked.</p>
        </div>
        {ideaDataStatus === "loading" ? (
          <p className="rounded-xl bg-surface-raised px-4 py-3 text-sm text-ink-muted" role="status" aria-live="polite">Building area routes from the processed catalog…</p>
        ) : ideaDataStatus === "error" ? (
          <p className="rounded-xl bg-warning-soft px-4 py-3 text-sm text-warning">Area routes could not be loaded. Use the place search above or adjust your search and try again.</p>
        ) : !readyIdeas.length ? (
          <p className="rounded-xl bg-surface-raised px-4 py-3 text-sm text-ink-muted">No saved route matches these filters yet. Search and select catalog places or addresses above, then compose your own itinerary below.</p>
        ) : (
          <>
            {!itineraryDate ? (
              <p className="rounded-xl bg-surface-raised px-4 py-3 text-sm text-ink-muted">Choose a date to check these estimated routes against recorded opening hours, availability, budget and travel time.</p>
            ) : ideasStatus === "checking" || ideasStatus === "loading" ? (
              <p className="rounded-xl bg-surface-raised px-4 py-3 text-sm text-ink-muted" role="status" aria-live="polite">Checking {ideas.length} area routes for {itineraryDate}…</p>
            ) : ideasStatus === "error" ? (
              <p className="rounded-xl bg-warning-soft px-4 py-3 text-sm text-warning">Date-specific route checks are unavailable. These remain estimates; the composer will check a selected plan before saving.</p>
            ) : null}
            <div className="grid gap-3 md:grid-cols-2">
              {readyIdeas.slice(0, visibleIdeas).map((idea) => {
                const picked = idea.experienceIds.every((id) => selectedIds.includes(id));
                const checkedPlan = ideaPreviews[idea.id];
                const ideaRecords = idea.experienceIds
                  .map((id) => ideaExperiences.find((experience) => experience.id === id))
                  .filter((experience): experience is ApiExperienceSummary => Boolean(experience));
                const planMinutes = checkedPlan?.total_minutes ?? (idea.visitMinutes == null ? null : idea.visitMinutes + idea.travelEstimateMinutes);
                const planCost = checkedPlan?.estimated_total_cost ?? idea.estimatedBudget;
                const statusLabel = !itineraryDate ? "Estimated area route"
                  : ideasStatus === "checking" || ideasStatus === "loading" ? "Checking this date…"
                    : checkedPlan?.valid ? `Verified for ${itineraryDate}`
                      : checkedPlan ? "Needs schedule review" : "Date check unavailable";
                const issueMessage = checkedPlan && !checkedPlan.valid ? checkedPlan.issues[0]?.message : null;
                return (
                  <Card key={idea.id}>
                    <CardBody className="space-y-3 p-4">
                      <div>
                        <p className="font-semibold leading-snug text-ink">{idea.title}</p>
                        <p className="mt-1 text-sm text-ink-muted">{idea.categories.join(" · ")}</p>
                        <p className={`mt-1 text-xs font-medium ${checkedPlan?.valid ? "text-success" : "text-ink-subtle"}`}>{statusLabel}</p>
                      </div>
                      <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-ink-subtle">
                        <span>{idea.experienceIds.length} stops</span>
                        <span>~{idea.routeDistanceKm} km route</span>
                        <span>{durationText(planMinutes)} total</span>
                        <span>{planCost == null ? "Some prices unavailable" : `${checkedPlan?.has_estimated_cost || idea.hasEstimatedPrice ? "Est. " : ""}₹${Math.round(planCost)} total`}</span>
                      </div>
                      {issueMessage ? <p className="rounded-lg bg-warning-soft px-3 py-2 text-xs text-warning">{issueMessage}</p> : null}
                      <button
                        type="button"
                        disabled={ideaRecords.length !== idea.experienceIds.length}
                        onClick={() => onUseIdea(ideaRecords, idea.locality, idea.city, planMinutes, planCost)}
                        className="rounded-full border border-line-strong px-3.5 py-2 text-sm font-medium text-ink transition hover:bg-pastel-lemon/45 disabled:opacity-50"
                      >
                        {picked ? "Selected · edit the plan below" : checkedPlan?.valid ? "Use checked itinerary" : "Build this itinerary"}
                      </button>
                    </CardBody>
                  </Card>
                );
              })}
            </div>
            {visibleIdeas < readyIdeas.length ? (
              <button type="button" onClick={() => setVisibleIdeas((count) => Math.min(count + 8, readyIdeas.length))} className="rounded-full px-4 py-2 text-sm font-medium text-accent hover:bg-accent-soft">
                See more itinerary options
              </button>
            ) : visibleIdeas > 4 ? (
              <button type="button" onClick={() => setVisibleIdeas(4)} className="rounded-full px-4 py-2 text-sm font-medium text-accent hover:bg-accent-soft">
                See fewer itinerary options
              </button>
            ) : null}
          </>
        )}
      </div>

    </section>
  );
}
