import type { Metadata } from "next";
import { ShieldAlert } from "lucide-react";
import { PageContainer } from "@/components/layout/PageContainer";
import { EmergencyButton } from "@/components/safety/EmergencyButton";
import { SafetyDashboard } from "@/components/safety/SafetyDashboard";

export const metadata: Metadata = { title: "Safety" };

export default function SafetyPage() {
  return (
    <PageContainer className="space-y-8 py-8 sm:py-10">
      <div className="motion-arrive flex flex-wrap items-center justify-between gap-3">
        <div className="space-y-2">
          <h1 className="flex items-center gap-2.5 text-3xl font-semibold tracking-tight text-ink sm:text-4xl">
            <span className="flex size-10 items-center justify-center rounded-2xl bg-danger-soft text-danger">
              <ShieldAlert className="size-5" aria-hidden="true" />
            </span>
            Safety Center
          </h1>
          <p className="text-sm leading-6 text-ink-muted">
            Kept separate from recommendations &mdash; this stays available even if discovery is down.
          </p>
        </div>
      </div>

      <EmergencyButton />

      <SafetyDashboard />
    </PageContainer>
  );
}
