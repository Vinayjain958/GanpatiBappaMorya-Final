"use client";

import { useEffect, useRef, useState } from "react";
import { Crosshair, MapPin, Search, X } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { useLocationSearch } from "@/hooks/useLocationSearch";
import { useUserLocation } from "@/hooks/useUserLocation";
import { reverseGeocode } from "@/lib/api/location";

export interface PickedLocation {
  lat: number;
  lng: number;
  label: string;
  address?: string;
}

/**
 * Location picker for the "Add a Local Experience" form. Uses the same
 * search + "use current location" pattern (useLocationSearch /
 * useUserLocation) as the trip planner's starting-point field — only the
 * presentation differs (shows an address line, and the traveler can clear
 * and repick). Map-click
 * placement is intentionally not offered: MapSurface has no pin-drop
 * capability today.
 */
export function ExperienceLocationPicker({
  value,
  onChange,
  disabled,
}: {
  value: PickedLocation | null;
  onChange: (value: PickedLocation | null) => void;
  disabled?: boolean;
}) {
  const [query, setQuery] = useState("");
  const { status: searchStatus, results, search, clear } = useLocationSearch();
  const { status: geoStatus, coordinate, error: geoError, request } = useUserLocation();
  // The parent passes a fresh onChange every render. Read it through a ref
  // so the reverse-geocode effect below depends only on the coordinate —
  // otherwise any parent re-render would abort the in-flight lookup and,
  // with the coordinate already marked handled, silently drop the result.
  const onChangeRef = useRef(onChange);
  useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);

  useEffect(() => {
    if (!coordinate) return;
    const controller = new AbortController();
    reverseGeocode(coordinate, controller.signal)
      .then((response) => response.items[0])
      .then((item) => {
        if (controller.signal.aborted) return;
        onChangeRef.current({
          lat: coordinate.lat,
          lng: coordinate.lng,
          label: item?.display_name ?? "Current location",
          address: item?.display_name,
        });
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          onChangeRef.current({ lat: coordinate.lat, lng: coordinate.lng, label: "Current location" });
        }
      });
    return () => controller.abort();
  }, [coordinate]);

  function runSearch() {
    if (query.trim()) void search(query);
  }

  if (value) {
    return (
      <div className="flex items-center gap-2 rounded-xl border border-line bg-surface px-3 py-2.5 text-sm">
        <MapPin className="size-4 shrink-0 text-accent" aria-hidden="true" />
        <span className="min-w-0 flex-1 truncate text-ink" title={value.label}>
          {value.label}
        </span>
        <button
          type="button"
          onClick={() => onChange(null)}
          disabled={disabled}
          className="rounded-full p-1 text-ink-subtle hover:bg-surface-sunken"
          aria-label="Change location"
        >
          <X className="size-4" aria-hidden="true" />
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <input
          className="h-11 min-w-0 flex-1 rounded-xl border border-line-strong bg-surface px-3.5 text-sm text-ink placeholder:text-ink-subtle outline-none transition focus:border-accent focus:ring-2 focus:ring-accent/15"
          value={query}
          disabled={disabled}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              runSearch();
            }
          }}
          placeholder="Search location"
          aria-label="Search for this experience's location"
        />
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-auto shrink-0"
          onClick={runSearch}
          disabled={disabled}
          loading={searchStatus === "loading"}
        >
          <Search className="size-4" aria-hidden="true" />
          <span className="sr-only sm:not-sr-only">Search</span>
        </Button>
      </div>

      {searchStatus === "success" && results.length === 0 ? (
        <p className="text-xs text-ink-subtle">No places found — try a different name.</p>
      ) : null}
      {searchStatus === "error" ? (
        <p className="text-xs text-danger">Location search is unavailable right now.</p>
      ) : null}
      {results.length ? (
        <ul className="max-h-48 space-y-1 overflow-y-auto rounded-xl border border-line bg-surface p-1" aria-label="Location results">
          {results.slice(0, 5).map((result) => (
            <li key={`${result.lat},${result.lng},${result.display_name}`}>
              <button
                type="button"
                className="w-full rounded-lg px-2.5 py-2 text-left text-xs text-ink hover:bg-surface-sunken"
                onClick={() => {
                  onChange({
                    lat: result.lat,
                    lng: result.lng,
                    label: result.display_name,
                    address: result.display_name,
                  });
                  clear();
                  setQuery("");
                }}
              >
                {result.display_name}
              </button>
            </li>
          ))}
        </ul>
      ) : null}

      <button
        type="button"
        onClick={request}
        disabled={disabled || geoStatus === "loading"}
        className="inline-flex items-center gap-1.5 text-xs font-medium text-accent hover:underline disabled:opacity-60"
      >
        <Crosshair className="size-3.5" aria-hidden="true" />
        {geoStatus === "loading" ? "Getting your location…" : "Use current location"}
      </button>
      {geoStatus === "denied" ? (
        <p className="text-xs text-warning">Location permission was denied — search for the location instead.</p>
      ) : null}
      {geoStatus === "error" ? (
        <p className="text-xs text-warning">
          Couldn&apos;t get your location{geoError ? ` (${geoError})` : ""} — search for the location instead.
        </p>
      ) : null}
    </div>
  );
}
