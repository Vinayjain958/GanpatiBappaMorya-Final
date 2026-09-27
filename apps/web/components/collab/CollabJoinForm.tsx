"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, KeyRound } from "lucide-react";
import { PageContainer } from "@/components/layout/PageContainer";
import { Card, CardBody } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { ApiError } from "@/lib/api/client";
import { joinCollabGroup } from "@/lib/api/collab";

export function CollabJoinForm() {
  const router = useRouter();
  const [inviteCode, setInviteCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [joining, setJoining] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setJoining(true);
    setError(null);
    try {
      const group = await joinCollabGroup(inviteCode.trim());
      router.push(`/collab/${group.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn’t join this group.");
    } finally {
      setJoining(false);
    }
  }

  return (
    <PageContainer className="max-w-2xl space-y-6 py-8 sm:py-10">
      <Link href="/collab" className="inline-flex items-center gap-2 text-sm font-medium text-ink-muted transition hover:text-ink"><ArrowLeft className="size-4" aria-hidden="true" />Back to Collab</Link>
      <header className="space-y-2"><p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent">You’re invited</p><h1 className="text-3xl font-semibold tracking-tight text-ink">Join a group</h1><p className="text-sm leading-6 text-ink-muted">Enter the private code shared by the group owner.</p></header>
      <Card><CardBody className="p-5 sm:p-7">
        <form onSubmit={submit} className="space-y-5">
          <Input label="Invite code" value={inviteCode} onChange={(event) => setInviteCode(event.target.value)} minLength={8} maxLength={48} autoComplete="off" required placeholder="Paste your group code" />
          {error ? <p role="alert" className="rounded-xl bg-danger-soft px-4 py-3 text-sm text-danger">{error}</p> : null}
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-5">
            <p className="flex items-center gap-2 text-xs text-ink-muted"><KeyRound className="size-4" aria-hidden="true" />Only people with the code can join.</p>
            <Button type="submit" loading={joining}>Join group</Button>
          </div>
        </form>
      </CardBody></Card>
    </PageContainer>
  );
}
