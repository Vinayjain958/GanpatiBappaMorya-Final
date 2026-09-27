"use client";

import { useEffect, useId, useState } from "react";
import type { FormEvent } from "react";
import { Crosshair, MapPin, X } from "lucide-react";
import { useLocationSearch } from "@/hooks/useLocationSearch";
import { useUserLocation } from "@/hooks/useUserLocation";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/utils/cn";

const RADIUS_OPTIONS_KM = [1, 2, 5, 10, 20];

export interface LocationValue {
  lat: number | null;
  lng: number | null;
  label: string | null;
  radiusKm: number | null;
}

export function LocationBar({
  value,
  onChange,
}: {
  value: LocationValue;
  onChange: (value: LocationValue) => void;
}) {
  const [query, setQuery] = useState("");
  const [showResults, setShowResults] = useState(false);
  const {
    status: searchStatus,
    results,
    search,
    clear: clearResults,
  } = useLocationSearch();
  const {
    status: geoStatus,
    coordinate,
    request: requestLocation,
  } = useUserLocation();
  const inputId = useId();

  const hasLocation = value.lat != null && value.lng != null;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!query.trim()) return;
    setShowResults(true);
    await search(query);
  }

  function handleUseCurrentLocation() {
    requestLocation();
  }

  // Reflect a freshly-resolved browser location into discovery state.
  useEffect(() => {
    if (coordinate) {
      onChange({
        lat: coordinate.lat,
        lng: coordinate.lng,
        label: "your location",
        radiusKm: value.radiusKm ?? 3,
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [coordinate]);

  function handlePickResult(result: {
    lat: number;
    lng: number;
    display_name: string;
  }) {
    onChange({
      lat: result.lat,
      lng: result.lng,
      label: result.display_name.split(",")[0],
      radiusKm: value.radiusKm ?? 3,
    });
    setShowResults(false);
    clearResults();
    setQuery("");
  }

  function handleClear() {
    onChange({ lat: null, lng: null, label: null, radiusKm: null });
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2.5">
        {hasLocation ? (
          <span className="inline-flex items-center gap-2 rounded-full border border-transparent bg-pastel-mint px-3 py-2 text-sm font-medium text-ink">
            <MapPin className="size-4" aria-hidden="true" />
            Near {value.label ?? "selected location"}
            <button
              type="button"
              onClick={handleClear}
              aria-label="Clear location"
              className="ml-0.5 inline-flex size-6 items-center justify-center rounded-full transition-colors hover:bg-surface/70"
            >
              <X className="size-3.5" aria-hidden="true" />
            </button>
          </span>
        ) : (
          <>
            <form
              onSubmit={handleSubmit}
              role="search"
              className="flex min-w-0 flex-1 items-center gap-2"
            >
              <label htmlFor={inputId} className="sr-only">
                Where are you exploring?
              </label>
              <input
                id={inputId}
                type="text"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Where are you exploring? e.g. Fort"
                className="h-11 min-w-0 flex-1 rounded-full border border-line-strong bg-surface px-4 text-sm text-ink placeholder:text-ink-subtle focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
              />
              <Button
                type="submit"
                size="sm"
                variant="primary"
                loading={searchStatus === "loading"}
              >
                Search
              </Button>
            </form>

            <Button
              type="button"
              size="sm"
              variant="secondary"
              onClick={handleUseCurrentLocation}
              loading={geoStatus === "loading"}
            >
              <Crosshair className="size-4" aria-hidden="true" />
              Use my location
            </Button>
          </>
        )}

        {hasLocation ? (
          <label className="inline-flex items-center gap-2 rounded-full border border-line bg-surface px-3 py-2 text-sm text-ink-muted">
            Radius
            <select
              value={value.radiusKm ?? 3}
              onChange={(event) =>
                onChange({ ...value, radiusKm: Number(event.target.value) })
              }
              className="bg-transparent text-sm font-medium text-ink focus:outline-none"
            >
              {RADIUS_OPTIONS_KM.map((km) => (
                <option key={km} value={km}>
                  {km} km
                </option>
              ))}
            </select>
          </label>
        ) : null}
      </div>

      {geoStatus === "denied" ? (
        <p className="rounded-xl bg-warning-soft px-3 py-2 text-xs text-warning">
          Location permission denied. You can still search for a place above.
        </p>
      ) : null}

      {showResults && !hasLocation ? (
        <div
          className={cn(
            "max-w-xl overflow-hidden rounded-2xl border border-line bg-surface-raised p-1 shadow-soft",
            searchStatus === "loading" && "animate-pulse",
          )}
        >
          {searchStatus === "success" && results.length === 0 ? (
            <p className="px-3 py-2 text-sm text-ink-subtle">
              No matching places found.
            </p>
          ) : (
            <ul className="max-h-56 overflow-auto">
              {results.map((result) => (
                <li key={`${result.lat}-${result.lng}`}>
                  <button
                    type="button"
                    onClick={() => handlePickResult(result)}
                    className="block w-full truncate rounded-xl px-3 py-2.5 text-left text-sm text-ink transition-colors hover:bg-pastel-lavender/40"
                  >
                    {result.display_name}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}
    </div>
  );
}