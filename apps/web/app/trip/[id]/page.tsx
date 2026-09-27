import type { Metadata } from "next";
import { PageContainer } from "@/components/layout/PageContainer";
import { ExperienceComposer } from "@/components/experience/ExperienceComposer";
import { ItineraryTimeline } from "@/components/trip/ItineraryTimeline";
import { RealTripDetail } from "@/components/trip/RealTripDetail";
import { RequireRole } from "@/components/common/RequireRole";
import { mockTrip } from "@/mocks/trip";

export async function generateMetadata({
  params,
}: PageProps<"/trip/[id]">): Promise<Metadata> {
  const { id } = await params;
  return { title: id === mockTrip.id ? mockTrip.title : "Trip" };
}

export default async function TripDetailPage({
  params,
}: PageProps<"/trip/[id]">) {
  const { id } = await params;
  if (id !== mockTrip.id) {
    return <RequireRole role="traveler"><RealTripDetail itineraryId={id} /></RequireRole>;
  }

  return (
    <PageContainer className="space-y-6 py-6 sm:space-y-8 sm:py-8">
      <header className="rounded-2xl border border-line bg-pastel-lavender/45 p-5 shadow-soft sm:p-6">
        <h1 className="text-3xl font-semibold tracking-tight text-ink sm:text-4xl">
          {mockTrip.title}
        </h1>
        <p className="mt-1 text-sm text-ink-muted">{mockTrip.date}</p>
      </header>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(320px,400px)] xl:items-start xl:gap-6">
        <section className="min-w-0 rounded-2xl border border-line bg-surface-raised p-4 shadow-soft sm:p-5">
          <ItineraryTimeline trip={mockTrip} />
        </section>

        <aside className="min-w-0 rounded-2xl border border-line bg-pastel-sky/30 p-3 shadow-soft xl:sticky xl:top-6">
          <ExperienceComposer trip={mockTrip} />
        </aside>
      </div>
    </PageContainer>
  );
}
