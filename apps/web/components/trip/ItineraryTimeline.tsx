import type { Trip } from "@/types/trip";
import { ItineraryItemCard } from "@/components/trip/ItineraryItemCard";
import { ReplanBanner } from "@/components/trip/ReplanBanner";

export function ItineraryTimeline({ trip }: { trip: Trip }) {
  return (
    <div className="space-y-4">
      <ReplanBanner />

      <ol
        className="relative space-y-4 before:absolute before:bottom-4 before:left-[1.125rem] before:top-4 before:w-px before:bg-line-strong"
        aria-label={`Itinerary for ${trip.title}`}
      >
        {trip.items.map((item) => (
          <li key={item.id} className="relative pl-10">
            <span
              aria-hidden="true"
              className="absolute left-[0.7rem] top-5 z-10 size-3 rounded-full border-2 border-surface bg-pastel-lemon shadow-sm"
            />
            <ItineraryItemCard item={item} />
          </li>
        ))}
      </ol>
    </div>
  );
}