"use client";

import Link from "next/link";
import { Plus } from "lucide-react";
import { PageContainer } from "@/components/layout/PageContainer";
import { Button } from "@/components/ui/Button";
import { RequireRole } from "@/components/common/RequireRole";
import { ProviderExperiencesManager } from "./ProviderExperiencesManager";

export default function ProviderExperiencesPage() {
  return (
    <RequireRole role="provider">
      <PageContainer className="space-y-8 py-8 sm:py-10">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="space-y-2">
            <h1 className="text-3xl font-semibold tracking-tight text-ink sm:text-4xl">Your experiences</h1>
            <p className="text-sm leading-6 text-ink-muted">Manage listings, pricing, and availability.</p>
          </div>
          <Link href="/provider/experiences/new">
            <Button size="sm" className="rounded-full">
              <Plus className="size-4" aria-hidden="true" />
              New experience
            </Button>
          </Link>
        </div>

        <ProviderExperiencesManager />
      </PageContainer>
    </RequireRole>
  );
}
