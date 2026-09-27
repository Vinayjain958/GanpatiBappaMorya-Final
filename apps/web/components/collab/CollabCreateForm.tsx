"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, UsersRound } from "lucide-react";
import { PageContainer } from "@/components/layout/PageContainer";
import { Card, CardBody } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input, Textarea } from "@/components/ui/Input";
import { ApiError } from "@/lib/api/client";
import { createCollabGroup } from "@/lib/api/collab";

const commaList = (value: string) => value.split(",").map((item) => item.trim()).filter(Boolean);

export function CollabCreateForm() {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [destination, setDestination] = useState("");
  const [date, setDate] = useState("");
  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");
  const [originLat, setOriginLat] = useState("");
  const [originLng, setOriginLng] = useState("");
  const [interests, setInterests] = useState("");
  const [mustInclude, setMustInclude] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const group = await createCollabGroup({
        title,
        destination: destination.trim() || null,
        itinerary_date: date || null,
        start_time: startTime || null,
        end_time: endTime || null,
        origin_latitude: originLat ? Number(originLat) : null,
        origin_longitude: originLng ? Number(originLng) : null,
        travel_mode: "walking",
        objectives: { interests: commaList(interests), must_include: commaList(mustInclude) },
      });
      router.push(`/collab/${group.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn’t create the group.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <PageContainer className="max-w-4xl space-y-6 py-8 sm:py-10">
      <Link href="/collab" className="inline-flex items-center gap-2 text-sm font-medium text-ink-muted transition hover:text-ink"><ArrowLeft className="size-4" aria-hidden="true" />Back to Collab</Link>
      <header className="space-y-2"><p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent">Start planning</p><h1 className="text-3xl font-semibold tracking-tight text-ink">Create a group</h1><p className="text-sm leading-6 text-ink-muted">Choose a destination and shared goals. You can add member preferences and refine the schedule after creating the group.</p></header>
      <Card><CardBody className="p-5 sm:p-7">
        <form onSubmit={submit} className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2">
            <Input label="Group name" value={title} onChange={(event) => setTitle(event.target.value)} required minLength={2} maxLength={160} placeholder="Weekend in Mumbai" />
            <Input label="Destination" value={destination} onChange={(event) => setDestination(event.target.value)} maxLength={120} placeholder="Mumbai" />
          </div>
          <fieldset className="space-y-3">
            <legend className="text-sm font-semibold text-ink">Shared schedule</legend>
            <p className="text-xs text-ink-muted">A date enables availability checks against verified hours and bookable slots. Leave the time window blank until the group decides.</p>
            <div className="grid gap-4 sm:grid-cols-3">
              <Input label="Date" type="date" value={date} onChange={(event) => setDate(event.target.value)} />
              <Input label="Start time" type="time" value={startTime} onChange={(event) => setStartTime(event.target.value)} />
              <Input label="End time" type="time" value={endTime} onChange={(event) => setEndTime(event.target.value)} />
            </div>
          </fieldset>
          <fieldset className="space-y-3">
            <legend className="text-sm font-semibold text-ink">Starting point</legend>
            <p className="text-xs text-ink-muted">Optional coordinates let the group enforce its shared distance limit. Collab never requests device location automatically.</p>
            <div className="grid gap-4 sm:grid-cols-2">
              <Input label="Latitude" type="number" step="any" min={-90} max={90} value={originLat} onChange={(event) => setOriginLat(event.target.value)} placeholder="18.9346" />
              <Input label="Longitude" type="number" step="any" min={-180} max={180} value={originLng} onChange={(event) => setOriginLng(event.target.value)} placeholder="72.8356" />
            </div>
          </fieldset>
          <div className="grid gap-4 sm:grid-cols-2">
            <Textarea label="Group interests" value={interests} onChange={(event) => setInterests(event.target.value)} placeholder="heritage, street food, photography" />
            <Textarea label="Must include" value={mustInclude} onChange={(event) => setMustInclude(event.target.value)} placeholder="a local market, a museum" />
          </div>
          {error ? <p role="alert" className="rounded-xl bg-danger-soft px-4 py-3 text-sm text-danger">{error}</p> : null}
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-5">
            <p className="flex items-center gap-2 text-xs text-ink-muted"><UsersRound className="size-4" aria-hidden="true" />An invite code will be created for your group.</p>
            <Button type="submit" loading={saving}>Create group</Button>
          </div>
        </form>
      </CardBody></Card>
    </PageContainer>
  );
}
