"use client";

import { useEffect, useState, type ComponentType } from "react";
import { cn } from "@/lib/utils/cn";
import type { MapSurfaceProps } from "@/components/common/MapSurface";

/**
 * MapSurface, loaded on demand. MapLibre is ~1 MB of JavaScript; importing
 * MapSurface directly puts it in the page's initial bundle. This wrapper
 * fetches it after first paint and shows a same-sized placeholder (matching
 * MapSurface's own container classes) meanwhile, so the layout doesn't jump.
 */
export function LazyMapSurface(props: MapSurfaceProps) {
  const [Surface, setSurface] = useState<ComponentType<MapSurfaceProps> | null>(null);

  useEffect(() => {
    let active = true;
    void import("@/components/common/MapSurface").then((module) => {
      if (active) setSurface(() => module.MapSurface);
    });
    return () => {
      active = false;
    };
  }, []);

  if (!Surface) {
    return (
      <div
        aria-hidden="true"
        className={cn(
          "relative min-h-64 w-full overflow-hidden rounded-2xl border border-line bg-surface-raised shadow-soft",
          props.className,
        )}
      />
    );
  }

  return <Surface {...props} />;
}
