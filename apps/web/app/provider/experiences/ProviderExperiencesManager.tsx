"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PackageOpen, Plus } from "lucide-react";
import { ProviderExperienceRow } from "@/components/provider/ProviderExperienceRow";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Skeleton } from "@/components/ui/Skeleton";
import { Button } from "@/components/ui/Button";
import { getMyExperiences } from "@/lib/api/providers";
import { deactivateExperience } from "@/lib/api/experiencesWrite";
import type { ApiExperienceSummary } from "@/types/api";

export function ProviderExperiencesManager() {
  const [experiences, setExperiences] = useState<ApiExperienceSummary[]>([]);
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    let cancelled = false;

    getMyExperiences({ limit: 100 })
      .then((response) => {
        if (!cancelled) {
          setExperiences(response.items);
          setStatus("success");
        }
      })
      .catch(() => {
        if (!cancelled) setStatus("error");
      });

    return () => {
      cancelled = true;
    };
  }, [reloadToken]);

  async function handleDeactivate(id: string) {
    if (!window.confirm("Deactivate this experience? It will stop appearing in Discover.")) return;
    await deactivateExperience(id);
    setReloadToken((t) => t + 1);
  }

  return (
    <>
      {status === "loading" ? (
        <div className="space-y-4" aria-busy="true" aria-live="polite">
          {Array.from({ length: 3 }).map((_, index) => (
            <Skeleton key={index} className="h-24 w-full rounded-2xl" />
          ))}
        </div>
      ) : status === "error" ? (
        <ErrorState
          title="Couldn't load your experiences"
          onRetry={() => setReloadToken((t) => t + 1)}
        />
      ) : experiences.length === 0 ? (
        <EmptyState
          icon={PackageOpen}
          title="No experiences yet"
          description="Create your first listing to start appearing in traveler discovery."
          action={
            <Link href="/provider/experiences/new">
              <Button size="sm">
                <Plus className="size-4" aria-hidden="true" />
                New experience
              </Button>
            </Link>
          }
        />
      ) : (
        <div className="space-y-4">
          {experiences.map((experience) => (
            <ProviderExperienceRow
              key={experience.id}
              experience={experience}
              onDeactivate={handleDeactivate}
            />
          ))}
        </div>
      )}
    </>
  );
}