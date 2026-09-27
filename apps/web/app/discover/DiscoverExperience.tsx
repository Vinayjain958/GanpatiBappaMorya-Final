"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { List, Map as MapIcon, Plus, SearchX } from "lucide-react";
import { PageContainer } from "@/components/layout/PageContainer";
import { ConversationalDiscoveryInput } from "@/components/discovery/ConversationalDiscoveryInput";
import { CategoryChips } from "@/components/discovery/CategoryChips";
import { FilterBar } from "@/components/discovery/FilterBar";
import { SourceDataDownloadButton } from "@/components/discovery/SourceDataDownloadButton";
import { LocationBar } from "@/components/discovery/LocationBar";
import { ExperienceCard } from "@/components/experience/ExperienceCard";
import { LazyMapSurface as MapSurface } from "@/components/common/LazyMapSurface";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Skeleton } from "@/components/ui/Skeleton";
import { Button } from "@/components/ui/Button";
import { useExperienceDiscovery } from "@/hooks/useExperienceDiscovery";
import { useSavedExperienceIds } from "@/hooks/useSavedExperienceIds";
import { listAvailableCategories, type ApiCategory } from "@/lib/api/categories";
import {
  discoveryStateToParams,
  parseDiscoveryStateFromParams,
} from "@/lib/discovery/urlState";
import { experiencesToFeatureCollection } from "@/lib/geo/geojson";
import { haversineKm } from "@/lib/geo/haversine";
import { DEFAULT_DISCOVERY_STATE } from "@/types/discovery";
import { cn } from "@/lib/utils/cn";
import { useAuth } from "@/lib/auth/AuthContext";

export function DiscoverExperience() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const [discoveryState, setDiscoveryState] = useState(() =>
    parseDiscoveryStateFromParams(searchParams),
  );
  const [reloadToken, setReloadToken] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [mobileView, setMobileView] = useState<"list" | "map">("list");
  const [areaCategories, setAreaCategories] = useState<ApiCategory[]>([]);

  const { experiences, total, status } = useExperienceDiscovery(
    discoveryState,
    reloadToken,
  );
  const { savedIds, toggleSaved } = useSavedExperienceIds();
  const { user } = useAuth();
  const canContribute = !user || user.role === "traveler";

  // Keep the URL shareable/reproducible without triggering a full navigation.
  useEffect(() => {
    const params = discoveryStateToParams(discoveryState);
    const query = params.toString();

    router.replace(query ? `${pathname}?${query}` : pathname, {
      scroll: false,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [discoveryState]);

  const hasLocation = discoveryState.lat != null && discoveryState.lng != null;

  useEffect(() => {
    if (!hasLocation) {
      return;
    }
    const controller = new AbortController();
    listAvailableCategories({
      lat: discoveryState.lat,
      lng: discoveryState.lng,
      radius_km: discoveryState.radiusKm,
    }, controller.signal)
      .then(setAreaCategories)
      .catch(() => {
        if (!controller.signal.aborted) setAreaCategories([]);
      });
    return () => controller.abort();
  }, [hasLocation, discoveryState.lat, discoveryState.lng, discoveryState.radiusKm]);
  const origin = hasLocation
    ? { lat: discoveryState.lat!, lng: discoveryState.lng! }
    : null;

  const featureCollection = useMemo(
    () => experiencesToFeatureCollection(experiences, selectedId),
    [experiences, selectedId],
  );

  function handleSearchThisArea(bounds: {
    minLat: number;
    maxLat: number;
    minLng: number;
    maxLng: number;
  }) {
    const centerLat = (bounds.minLat + bounds.maxLat) / 2;
    const centerLng = (bounds.minLng + bounds.maxLng) / 2;
    const radius = haversineKm(
      centerLat,
      centerLng,
      bounds.maxLat,
      bounds.maxLng,
    );

    setDiscoveryState((s) => ({
      ...s,
      lat: centerLat,
      lng: centerLng,
      locationLabel: s.locationLabel ?? "this area",
      radiusKm: Math.max(0.5, Math.round(radius * 10) / 10),
    }));
  }

  return (
    <PageContainer className="space-y-5 py-6 sm:space-y-6 sm:py-8">
      <section className="grid min-w-0 gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(360px,0.9fr)] xl:items-center">
        <div className="min-w-0">
          <h1 className="text-3xl font-semibold tracking-tight text-ink sm:text-4xl">
            Discover
          </h1>
          <p className="mt-1 text-sm text-ink-muted">
            Search by what you want, then narrow by location.
          </p>
          {canContribute ? (
            <Link
              href="/contribute/experience"
              className="group mt-3 inline-flex items-center gap-2 rounded-full border border-pastel-lemon/80 bg-pastel-lemon/40 px-3.5 py-1.5 text-xs font-medium text-ink shadow-xs transition-all duration-200 hover:-translate-y-0.5 hover:bg-pastel-lemon/70 hover:shadow-porcelain-hover"
            >
              <Plus className="size-3.5 transition-transform duration-200 group-hover:rotate-90" aria-hidden="true" />
              Know a hidden gem? Add a local experience
            </Link>
          ) : null}
        </div>

        <div className="min-w-0 rounded-[1.5rem] border border-line bg-pastel-lavender/60 p-2 shadow-soft sm:p-3">
          <ConversationalDiscoveryInput
            size="compact"
            suggestions={discoveryState.q ? [] : undefined}
            onSubmitQuery={(q) =>
              setDiscoveryState((s) => ({ ...s, q }))
            }
            onDiscoveryPatch={(patch) =>
              setDiscoveryState((s) => ({ ...s, ...patch }))
            }
          />
        </div>
      </section>

      {discoveryState.q ? (
        <p className="rounded-xl border border-line bg-surface-raised px-4 py-3 text-sm text-ink-muted">
          Showing results shaped by:{" "}
          <span className="font-medium text-ink">
            &ldquo;{discoveryState.q}&rdquo;
          </span>{" "}
          <span className="text-ink-subtle">
            (keyword + filter matching &mdash; no AI retrieval yet)
          </span>
        </p>
      ) : null}

      <section
        aria-label="Discovery filters"
        className="space-y-4 rounded-2xl border border-line bg-surface-raised p-4 shadow-soft sm:p-5"
      >
        <LocationBar
          value={{
            lat: discoveryState.lat,
            lng: discoveryState.lng,
            label: discoveryState.locationLabel,
            radiusKm: discoveryState.radiusKm,
          }}
          onChange={(loc) =>
            setDiscoveryState((s) => ({
              ...s,
              lat: loc.lat,
              lng: loc.lng,
              locationLabel: loc.label,
              radiusKm: loc.radiusKm,
              sort:
                loc.lat == null && s.sort === "distance"
                  ? "relevance"
                  : s.sort,
            }))
          }
        />

        <div className="border-t border-line pt-3">
          <CategoryChips
            value={discoveryState.category}
            categories={hasLocation ? areaCategories : undefined}
            onChange={(category) =>
              setDiscoveryState((s) => ({ ...s, category }))
            }
          />
        </div>

        <div className="border-t border-line pt-3">
          <FilterBar
            value={{
              budget: discoveryState.budget,
              duration: discoveryState.duration,
              sort: discoveryState.sort,
              dataSource: discoveryState.dataSource,
            }}
            onChange={(value) =>
              setDiscoveryState((s) => ({ ...s, ...value }))
            }
            hasLocation={hasLocation}
          />
        </div>
      </section>

      {/* Mobile: list/map toggle — the desktop view keeps both visible. */}
      <div className="flex items-center gap-2 xl:hidden">
        <Button
          size="sm"
          variant={mobileView === "list" ? "primary" : "outline"}
          onClick={() => setMobileView("list")}
        >
          <List className="size-4" aria-hidden="true" />
          List
        </Button>
        <Button
          size="sm"
          variant={mobileView === "map" ? "primary" : "outline"}
          onClick={() => setMobileView("map")}
        >
          <MapIcon className="size-4" aria-hidden="true" />
          Map
        </Button>
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(360px,420px)] xl:gap-6">
        <section
          aria-label="Experience results"
          className={cn(
            "min-w-0 space-y-4",
            mobileView === "map" && "hidden xl:block",
          )}
        >
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-line bg-surface-raised px-4 py-3">
            <p className="text-sm font-medium text-ink-muted">
              {status === "success"
                ? `${experiences.length} of ${total} experiences`
                : "Loading experiences…"}
            </p>
            <SourceDataDownloadButton />
          </div>

          {status === "loading" ? (
            <div
              className="grid gap-4 sm:grid-cols-2"
              aria-busy="true"
              aria-live="polite"
            >
              {Array.from({ length: 6 }).map((_, index) => (
                <Skeleton
                  key={index}
                  className="h-72 w-full rounded-2xl"
                />
              ))}
            </div>
          ) : status === "error" ? (
            <ErrorState
              title="Couldn't load experiences"
              description="The LocaLens API might not be running. Start it and try again."
              onRetry={() => setReloadToken((token) => token + 1)}
            />
          ) : experiences.length === 0 ? (
            <EmptyState
              icon={SearchX}
              title="No experiences found"
              description="Try a different category, a larger radius, or loosen your filters."
              action={
                discoveryState.q ||
                discoveryState.category ||
                hasLocation ? (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() =>
                      setDiscoveryState(DEFAULT_DISCOVERY_STATE)
                    }
                  >
                    Clear all filters
                  </Button>
                ) : undefined
              }
            />
          ) : (
            <div className="grid gap-4 sm:grid-cols-2">
              {experiences.map((experience) => (
                <div
                  key={experience.id}
                  onMouseEnter={() => setSelectedId(experience.id)}
                  className={cn(
                    "min-w-0 rounded-2xl transition-shadow",
                    selectedId === experience.id &&
                      "ring-2 ring-accent/60 ring-offset-2 ring-offset-bg",
                  )}
                >
                  <ExperienceCard
                    experience={experience}
                    saved={savedIds.has(experience.id)}
                    onToggleSave={toggleSaved}
                  />
                </div>
              ))}
            </div>
          )}
        </section>

        <div
          className={cn(
            "min-w-0 xl:sticky xl:top-6 xl:self-start",
            mobileView === "list" && "hidden xl:block",
          )}
        >
          <MapSurface
            features={featureCollection}
            onSelectFeature={setSelectedId}
            origin={origin}
            center={origin ?? undefined}
            onSearchThisArea={handleSearchThisArea}
            className="h-[65vh] min-h-[360px] rounded-2xl xl:h-[calc(100vh-3rem)]"
            label="Discover experiences map"
          />
        </div>
      </div>
    </PageContainer>
  );
}
