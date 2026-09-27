"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ArrowRight, CalendarDays, MapPin, Plus, UsersRound } from "lucide-react";
import { PageContainer } from "@/components/layout/PageContainer";
import { Card, CardBody } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Skeleton } from "@/components/ui/Skeleton";
import { listCollabGroups } from "@/lib/api/collab";
import { ApiError } from "@/lib/api/client";
import type { CollabGroup } from "@/types/collab";

export function CollabHome() {
  const [groups, setGroups] = useState<CollabGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);

  const load = useCallback(async (signal?: AbortSignal) => {
    try {
      const rows = await listCollabGroups(signal);
      if (!signal?.aborted) {
        setGroups(rows);
        setError(null);
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      if (!signal?.aborted) setError(err instanceof ApiError ? err.message : "Couldn't load your groups.");
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load, reload]);

  return (
    <PageContainer className="space-y-8 py-8 sm:py-10">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent">Plan together</p>
          <h1 className="text-3xl font-semibold tracking-tight text-ink sm:text-4xl">Collab</h1>
          <p className="max-w-2xl text-sm leading-6 text-ink-muted">
            Bring everyone’s preferences into one plan, compare real local experiences, and make the final call together.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link href="/collab/create"><Button><Plus className="size-4" aria-hidden="true" />Create group</Button></Link>
          <Link href="/collab/join"><Button variant="outline">Join a group</Button></Link>
        </div>
      </header>

      {loading ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3" aria-busy="true" aria-live="polite">
          {[0, 1, 2].map((item) => <Skeleton key={item} className="h-40 rounded-3xl" />)}
        </div>
      ) : error ? (
        <ErrorState title="Couldn’t load your groups" description={error} onRetry={() => { setLoading(true); setError(null); setReload((value) => value + 1); }} />
      ) : groups.length === 0 ? (
        <EmptyState
          icon={UsersRound}
          title="No shared plans yet"
          description="Create a group and invite people with its private join code, or join a group you’ve been invited to."
          action={<div className="flex gap-2"><Link href="/collab/create"><Button>Create group</Button></Link><Link href="/collab/join"><Button variant="outline">Join group</Button></Link></div>}
        />
      ) : (
        <section aria-label="Your Collab groups" className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {groups.map((group) => (
            <Link key={group.id} href={`/collab/${group.id}`} className="group rounded-3xl focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent">
              <Card className="h-full transition duration-200 group-hover:-translate-y-0.5 group-hover:shadow-xl">
                <CardBody className="flex h-full flex-col gap-5 p-5 sm:p-6">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <h2 className="truncate text-lg font-semibold text-ink">{group.title}</h2>
                      <p className="mt-1 flex items-center gap-1.5 text-sm text-ink-muted">
                        <MapPin className="size-3.5" aria-hidden="true" />{group.destination || "Destination not set"}
                      </p>
                    </div>
                    <span className="flex size-10 shrink-0 items-center justify-center rounded-2xl bg-pastel-lavender text-accent"><UsersRound className="size-5" aria-hidden="true" /></span>
                  </div>
                  <div className="mt-auto flex items-center justify-between border-t border-line pt-4 text-xs text-ink-muted">
                    <span className="flex items-center gap-1.5"><CalendarDays className="size-3.5" aria-hidden="true" />{group.itinerary_date || "Date flexible"}</span>
                    <span>{group.members.length} member{group.members.length === 1 ? "" : "s"}</span>
                  </div>
                  <span className="inline-flex items-center gap-1 text-sm font-semibold text-accent">Open group <ArrowRight className="size-4 transition-transform group-hover:translate-x-1" aria-hidden="true" /></span>
                </CardBody>
              </Card>
            </Link>
          ))}
        </section>
      )}
    </PageContainer>
  );
}
