"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Bookmark } from "lucide-react";
import { PageContainer } from "@/components/layout/PageContainer";
import { ExperienceCard } from "@/components/experience/ExperienceCard";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Skeleton } from "@/components/ui/Skeleton";
import { Button } from "@/components/ui/Button";
import { listSavedExperiences } from "@/lib/api/experiences";
import { mapApiExperienceToUi } from "@/lib/api/experienceAdapter";
import { recordExperienceSave } from "@/lib/api/feedback";
import type { Experience } from "@/types/experience";

type Status = "loading" | "success" | "error";

export function SavedExperiences() {
  const [experiences, setExperiences] = useState<Experience[]>([]);
  const [total, setTotal] = useState(0);
  const [status, setStatus] = useState<Status>("loading");
  const [reloadToken, setReloadToken] = useState(0);
  const [loadingMore, setLoadingMore] = useState(false);
  const [moreError, setMoreError] = useState(false);

  useEffect(() => {
    const controller = new AbortController();

    listSavedExperiences(controller.signal)
      .then((response) => {
        if (controller.signal.aborted) return;
        setExperiences(response.items.map((item) => mapApiExperienceToUi(item, null)));
        setTotal(response.total);
        setMoreError(false);
        setStatus("success");
      })
      .catch(() => {
        if (!controller.signal.aborted) setStatus("error");
      });

    return () => controller.abort();
  }, [reloadToken]);

  async function handleSaveToggle(id: string, saved: boolean) {
    await recordExperienceSave(id, saved);
    if (!saved) {
      setExperiences((current) => current.filter((experience) => experience.id !== id));
      setTotal((current) => Math.max(0, current - 1));
    }
  }

  async function loadMore() {
    if (loadingMore) return;
    setLoadingMore(true);
    setMoreError(false);
    try {
      const response = await listSavedExperiences(undefined, experiences.length);
      const next = response.items.map((item) => mapApiExperienceToUi(item, null));
      setExperiences((current) => {
        const knownIds = new Set(current.map((experience) => experience.id));
        return [...current, ...next.filter((experience) => !knownIds.has(experience.id))];
      });
      setTotal(response.total);
    } catch {
      setMoreError(true);
    } finally {
      setLoadingMore(false);
    }
  }

  return (
    <PageContainer className="space-y-8 py-8 sm:py-10">
      <div className="space-y-2">
        <h1 className="text-3xl font-semibold tracking-tight text-ink sm:text-4xl">Saved</h1>
        <p className="text-sm leading-6 text-ink-muted">
          Experiences you&apos;ve bookmarked for later.
        </p>
      </div>

      {status === "loading" ? (
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3" aria-label="Loading saved experiences">
          {Array.from({ length: 3 }).map((_, index) => (
            <Skeleton key={index} className="h-72 w-full rounded-2xl" />
          ))}
        </div>
      ) : status === "error" ? (
        <ErrorState
          title="Couldn’t load your saved experiences"
          description="Please try again."
          onRetry={() => {
            setStatus("loading");
            setReloadToken((current) => current + 1);
          }}
        />
      ) : experiences.length === 0 ? (
        <EmptyState
          icon={Bookmark}
          title="No saved experiences"
          description="Tap the bookmark icon on any experience card to save it here."
          action={
            <Link href="/discover">
              <Button size="sm">Browse experiences</Button>
            </Link>
          }
        />
      ) : (
        <>
          <p className="text-sm text-ink-muted" aria-live="polite">
            Showing {experiences.length} of {total} saved {total === 1 ? "experience" : "experiences"}.
          </p>
          <div className="motion-stagger grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {experiences.map((experience) => (
              <ExperienceCard
                key={experience.id}
                experience={experience}
                saved
                onToggleSave={handleSaveToggle}
              />
            ))}
          </div>
          {moreError ? (
            <p className="text-sm text-danger" role="alert">
              Couldn’t load more saved experiences. Try again.
            </p>
          ) : null}
          {experiences.length < total ? (
            <div className="flex justify-center">
              <Button variant="outline" loading={loadingMore} onClick={() => void loadMore()}>
                Load more
              </Button>
            </div>
          ) : null}
        </>
      )}
    </PageContainer>
  );
}
