import type { Metadata } from "next";
import { PageContainer } from "@/components/layout/PageContainer";
import { RequireRole } from "@/components/common/RequireRole";
import { TripComposerSection } from "@/components/trip/TripComposerSection";
import { MyItineraryList } from "@/components/trip/MyItineraryList";

export const metadata: Metadata = { title: "Trips" };

/**
 * /trip — hydrates entirely from the API (GET /api/v1/itineraries) inside
 * TripComposerSection and MyItineraryList. No mock trip data is rendered
 * here; a refresh or a fresh login shows exactly what the database holds.
 */
export default function TripListPage() {
  return (
    <RequireRole role="traveler">
      <PageContainer className="space-y-8 py-8 sm:py-10">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="space-y-2">
            <h1 className="text-3xl font-semibold tracking-tight text-ink sm:text-4xl">Your trips</h1>
            <p className="text-sm leading-6 text-ink-muted">
              Plan a trip from real local places, or revisit one you&apos;ve saved.
            </p>
          </div>
        </div>

        <TripComposerSection />

        <MyItineraryList />
      </PageContainer>
    </RequireRole>
  );
}
