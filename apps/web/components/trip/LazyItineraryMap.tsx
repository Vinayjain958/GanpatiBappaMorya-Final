"use client";

import { useEffect, useState, type ComponentProps, type ComponentType } from "react";
import type { ItineraryMap } from "@/components/trip/ItineraryMap";

type ItineraryMapProps = ComponentProps<typeof ItineraryMap>;

/**
 * ItineraryMap, loaded on demand so MapLibre (~1 MB) is not part of the trip
 * page's initial bundle — the timeline and details render first, the map
 * follows. See components/common/LazyMapSurface.tsx for the same pattern.
 */
export function LazyItineraryMap(props: ItineraryMapProps) {
  const [Map, setMap] = useState<ComponentType<ItineraryMapProps> | null>(null);

  useEffect(() => {
    let active = true;
    void import("@/components/trip/ItineraryMap").then((module) => {
      if (active) setMap(() => module.ItineraryMap);
    });
    return () => {
      active = false;
    };
  }, []);

  if (!Map) {
    return (
      <div
        aria-hidden="true"
        className="min-h-[28rem] w-full rounded-2xl border border-line bg-surface-raised shadow-soft"
      />
    );
  }

  return <Map {...props} />;
}
