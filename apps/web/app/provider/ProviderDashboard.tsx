"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Eye, ListChecks, ShieldCheck, Sparkles } from "lucide-react";
import { PageContainer } from "@/components/layout/PageContainer";
import { Card, CardBody } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ErrorState } from "@/components/ui/ErrorState";
import { Skeleton } from "@/components/ui/Skeleton";
import { getMyExperiences, getMyProvider } from "@/lib/api/providers";
import type { ProviderMe } from "@/types/provider-api";
import type { ApiExperienceSummary } from "@/types/api";

const VERIFICATION_LABEL: Record<string, string> = {
  unverified: "Pending review",
  catalog_imported: "Imported from open data",
  verified: "Verified",
};

export function ProviderDashboard() {
  const [provider, setProvider] = useState<ProviderMe | null>(null);
  const [experiences, setExperiences] = useState<ApiExperienceSummary[]>([]);
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    let cancelled = false;

    Promise.all([getMyProvider(), getMyExperiences({ limit: 100 })])
      .then(([providerData, experiencesData]) => {
        if (cancelled) return;
        setProvider(providerData);
        setExperiences(experiencesData.items);
        setStatus("success");
      })
      .catch(() => {
        if (!cancelled) setStatus("error");
      });

    return () => {
      cancelled = true;
    };
  }, [reloadToken]);

  if (status === "loading") {
    return (
      <PageContainer
        className="space-y-7 py-8 sm:py-10"
        aria-busy="true"
        aria-live="polite"
      >
        <Skeleton className="h-24 w-full rounded-3xl" />
        <div className="grid gap-5 sm:grid-cols-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <Skeleton key={index} className="h-32 w-full rounded-2xl" />
          ))}
        </div>
        <Skeleton className="h-64 w-full rounded-3xl" />
      </PageContainer>
    );
  }

  if (status === "error" || !provider) {
    return (
      <PageContainer className="py-8 sm:py-10">
        <ErrorState
          title="Couldn't load your provider dashboard"
          onRetry={() => setReloadToken((t) => t + 1)}
        />
      </PageContainer>
    );
  }

  const activeCount = experiences.filter((e) => e.status === "active").length;
  const inactiveCount = experiences.filter((e) => e.status !== "active").length;

  return (
    <PageContainer className="space-y-8 py-8 sm:py-10">
      <section className="flex flex-col gap-5 rounded-3xl border border-line bg-surface-raised p-5 shadow-soft sm:flex-row sm:items-center sm:justify-between sm:p-7">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent">
            Provider
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-semibold tracking-tight text-ink sm:text-3xl">
              {provider.business_name}
            </h1>
            {provider.verification_status === "verified" ? (
              <Badge tone="success">
                <ShieldCheck className="size-3" aria-hidden="true" />
                Verified
              </Badge>
            ) : null}
          </div>
          <p className="mt-1 text-sm text-ink-muted">
            {VERIFICATION_LABEL[provider.verification_status] ?? provider.verification_status}
            {provider.city ? ` · ${provider.city}` : ""}
          </p>
        </div>

        <Link href="/provider/experiences" className="shrink-0">
          <Button size="sm">Manage experiences</Button>
        </Link>
      </section>

      <section aria-label="Provider overview" className="grid gap-5 sm:grid-cols-3">
        <Card className="h-full">
          <CardBody className="flex h-full items-start gap-4 p-5">
            <span className="flex size-11 shrink-0 items-center justify-center rounded-2xl bg-success-soft text-success">
              <ListChecks className="size-5" aria-hidden="true" />
            </span>
            <div>
              <p className="text-sm text-ink-muted">Active listings</p>
              <p className="mt-1 text-3xl font-semibold tracking-tight text-ink">
                {activeCount}
              </p>
            </div>
          </CardBody>
        </Card>

        <Card className="h-full">
          <CardBody className="flex h-full items-start gap-4 p-5">
            <span className="flex size-11 shrink-0 items-center justify-center rounded-2xl bg-highlight-soft text-highlight">
              <Eye className="size-5" aria-hidden="true" />
            </span>
            <div>
              <p className="text-sm text-ink-muted">Inactive / draft listings</p>
              <p className="mt-1 text-3xl font-semibold tracking-tight text-ink">
                {inactiveCount}
              </p>
            </div>
          </CardBody>
        </Card>

        <Card className="h-full">
          <CardBody className="flex h-full items-start gap-4 p-5">
            <span className="flex size-11 shrink-0 items-center justify-center rounded-2xl bg-accent-soft text-accent">
              <Sparkles className="size-5" aria-hidden="true" />
            </span>
            <div>
              <p className="text-sm font-medium text-ink">Analytics</p>
              <p className="mt-1 text-sm leading-5 text-ink-muted">
                Analytics will appear once traveler interactions are enabled.
              </p>
            </div>
          </CardBody>
        </Card>
      </section>

      <section className="space-y-4">
        <div>
          <h2 className="text-xl font-semibold tracking-tight text-ink">
            Recent experiences
          </h2>
        </div>

        {experiences.length === 0 ? (
          <Card>
            <CardBody className="p-5">
              <p className="text-sm leading-6 text-ink-muted">
                You haven&apos;t created any experiences yet.{" "}
                <Link
                  href="/provider/experiences"
                  className="font-medium text-accent hover:underline"
                >
                  Create your first one
                </Link>
                .
              </p>
            </CardBody>
          </Card>
        ) : (
          <ul className="space-y-3">
            {experiences.slice(0, 5).map((experience) => (
              <li
                key={experience.id}
                className="flex items-center justify-between gap-4 rounded-2xl border border-line bg-surface px-4 py-4 shadow-soft transition-shadow hover:shadow-md sm:px-5"
              >
                <span className="min-w-0 truncate text-sm font-medium text-ink">
                  {experience.title}
                </span>
                <Badge
                  tone={experience.status === "active" ? "success" : "neutral"}
                  className="shrink-0 capitalize"
                >
                  {experience.status}
                </Badge>
              </li>
            ))}
          </ul>
        )}
      </section>
    </PageContainer>
  );
}