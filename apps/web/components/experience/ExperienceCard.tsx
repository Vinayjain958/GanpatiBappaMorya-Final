"use client";

import Link from "next/link";
import { useState } from "react";
import { Bookmark, Clock, MapPin, ShieldCheck, Star, UsersRound } from "lucide-react";
import type { Experience } from "@/types/experience";
import { Badge } from "@/components/ui/Badge";
import { PersonalizationBadge } from "@/components/ui/PersonalizationBadge";
import { ExperienceImageView } from "@/components/experience/ExperienceImageView";
import { ScrollReveal } from "@/components/common/ScrollReveal";
import { cn } from "@/lib/utils/cn";

const availabilityTone = {
  available: "success",
  limited: "warning",
  unavailable: "danger",
} as const;

const availabilityLabel = {
  available: "Available",
  limited: "Limited spots",
  unavailable: "Unavailable",
} as const;

export interface ExperienceCardProps {
  experience: Experience;
  variant?: "standard" | "compact" | "featured";
  saved?: boolean;
  onToggleSave?: (id: string, saved: boolean) => void | Promise<void>;
  className?: string;
}

export function ExperienceCard({
  experience,
  variant = "standard",
  saved = false,
  onToggleSave,
  className,
}: ExperienceCardProps) {
  // `saved` is the source of truth; `pendingSaved` only overrides it while
  // a toggle is in flight, so the bookmark responds instantly and falls
  // back to the prop once the write settles (or rolls back on failure).
  const [pendingSaved, setPendingSaved] = useState<boolean | null>(null);
  const [saveError, setSaveError] = useState(false);
  const isSaving = pendingSaved !== null;
  const isSaved = pendingSaved ?? saved;
  const isCompact = variant === "compact";
  const isFeatured = variant === "featured";
  const isCommunityAdded = experience.sourceType === "traveler_submission";

  async function handleSaveToggle() {
    if (isSaving) return;
    const nextSaved = !isSaved;
    setPendingSaved(nextSaved);
    setSaveError(false);
    try {
      await onToggleSave?.(experience.id, nextSaved);
    } catch {
      setSaveError(true);
    } finally {
      setPendingSaved(null);
    }
  }

  return (
    <ScrollReveal>
      <article
        className={cn(
          "group relative flex overflow-hidden rounded-2xl porcelain-card",
          isCompact ? "flex-row items-stretch" : "flex-col",
          isFeatured && "sm:col-span-2",
          className,
        )}
      >
        <div
          className={cn(
            "relative shrink-0 overflow-hidden bg-pastel-sky/20",
            isCompact ? "w-28 sm:w-36" : "aspect-[4/3] w-full",
            isFeatured && "sm:aspect-auto sm:min-h-[220px]",
          )}
        >
          <ExperienceImageView
            src={experience.imageUrl}
            alt=""
            fill
            sizes={isCompact ? "144px" : "(min-width: 640px) 400px, 100vw"}
            className="object-cover transition-transform duration-500 ease-out group-hover:scale-105"
          />

          {/* Subtle atmospheric scrim */}
          <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-black/20 via-transparent to-transparent opacity-60" />

          {!isCompact && onToggleSave ? (
            <button
              type="button"
              onClick={() => void handleSaveToggle()}
              disabled={isSaving}
              aria-pressed={isSaved}
              aria-label={isSaved ? "Remove from saved" : "Save experience"}
              className="absolute right-3 top-3 z-20 inline-flex size-9 items-center justify-center rounded-full border border-white/60 bg-surface/90 text-ink shadow-sm backdrop-blur-md transition-all duration-200 hover:scale-110 hover:bg-pastel-rose/80 active:scale-95 disabled:cursor-wait disabled:opacity-70"
            >
              <Bookmark
                className={cn(
                  "size-4",
                  isSaved && "fill-accent text-accent",
                )}
                aria-hidden="true"
              />
            </button>
          ) : null}

          {!isCompact && !experience.image.isFallback && !experience.image.isPlaceSpecific ? (
            <span className="absolute bottom-2 left-2.5 z-10 rounded-md border border-line/50 bg-surface/85 px-1.5 py-0.5 text-[10px] italic text-ink-subtle backdrop-blur-sm">
              Representative image
            </span>
          ) : null}
        </div>

        <div className={cn("flex flex-1 flex-col gap-3 p-4 sm:p-5", isCompact && "py-3")}>
          <div className="flex items-start justify-between gap-2">
            <div className="flex min-w-0 flex-wrap items-center gap-1.5">
              <Badge tone="accent">{experience.categoryLabel}</Badge>
              {isCommunityAdded ? (
                <Badge tone="highlight">
                  <UsersRound className="size-3" aria-hidden="true" />
                  Community added
                </Badge>
              ) : (
                <Badge tone={experience.isSynthetic ? "warning" : "neutral"}>
                  {experience.isSynthetic ? "Demo listing" : "Non-demo source"}
                </Badge>
              )}
            </div>
            {!isCompact ? (
              <Badge tone={availabilityTone[experience.availability]}>
                {availabilityLabel[experience.availability]}
              </Badge>
            ) : null}
          </div>

          <div>
            <h3
              className={cn(
                "font-semibold leading-snug tracking-tight text-ink transition-colors group-hover:text-accent",
                isCompact ? "text-sm" : "text-base",
              )}
            >
              <Link href={`/discover/${experience.id}`} className="hover:underline">
                <span className="absolute inset-0 z-10" aria-hidden={isCompact} />
                {experience.title}
              </Link>
            </h3>

            {!isCompact ? (
              <>
                <p className="mt-1.5 line-clamp-2 text-sm leading-6 text-ink-muted">
                  {experience.shortDescription}
                </p>

                {experience.matchSignals &&
                experience.matchSignals.length > 0 ? (
                  <div className="mt-2">
                    <PersonalizationBadge signals={experience.matchSignals} />
                  </div>
                ) : null}
              </>
            ) : null}
          </div>

          <div className="mt-auto flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs text-ink-subtle">
            <span className="inline-flex items-center gap-1">
              <MapPin className="size-3.5 text-accent" aria-hidden="true" />
              {experience.location.area}
              {experience.distanceKm != null
                ? ` · ${experience.distanceKm} km`
                : ""}
            </span>

            {experience.travelTimeMinutes != null ? (
              <span className="inline-flex items-center gap-1">
                <Clock className="size-3.5" aria-hidden="true" />
                {Math.round(experience.travelTimeMinutes)} min
                {experience.travelTimeSource === "haversine_estimate"
                  ? " (est.)"
                  : ""}
              </span>
            ) : null}

            {experience.durationMinutes != null ? (
              <span className="inline-flex items-center gap-1">
                <Clock className="size-3.5" aria-hidden="true" />
                {experience.durationMinutes} min
              </span>
            ) : null}

            {experience.accessibility.wheelchairAccessible ? (
              <span className="inline-flex items-center gap-1">
                <ShieldCheck className="size-3.5" aria-hidden="true" />
                Accessible
              </span>
            ) : null}
          </div>

          <div className="flex items-center justify-between border-t border-line pt-3">
            {experience.rating != null ? (
              <span className="inline-flex items-center gap-1 text-xs text-ink-muted">
                <Star
                  className="size-3.5 fill-highlight text-highlight"
                  aria-hidden="true"
                />
                <span className="font-semibold tabular-nums text-ink">{experience.rating}</span>
                {experience.reviewCount != null ? (
                  <span className="tabular-nums">({experience.reviewCount})</span>
                ) : null}
                {experience.isSynthetic ? (
                  <span
                    className="ml-0.5 rounded-md border border-line bg-surface-sunken/60 px-1.5 py-0.5 text-[9px] font-medium text-ink-subtle"
                    title="Synthetic Demo Rating"
                  >
                    Demo
                  </span>
                ) : null}
              </span>
            ) : (
              <span className="text-xs text-ink-subtle">No ratings yet</span>
            )}

            <span className="text-sm font-semibold tabular-nums text-ink">
              {experience.isPriceUnknown
                ? <span className="font-normal text-ink-subtle">Price not listed</span>
                : experience.priceInr === 0
                  ? "Free"
                  : `₹${experience.priceInr}`}
              {experience.isPriceEstimated ? (
                <span className="font-normal text-ink-subtle"> est.</span>
              ) : null}
            </span>
          </div>
          {saveError ? (
            <p className="text-xs text-danger" role="alert">
              Couldn&apos;t update your saved list. Try again.
            </p>
          ) : null}
        </div>
      </article>
    </ScrollReveal>
  );
}
