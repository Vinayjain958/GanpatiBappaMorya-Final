"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ApiError } from "@/lib/api/client";
import { createBookingRequest } from "@/lib/api/bookings";
import { bookingStatusLabel, bookingStatusTone } from "@/lib/itinerary/itineraryDisplay";
import type { ApiBookingRequest, BookingStatus } from "@/types/api";

/**
 * Shows the booking request state. A REQUESTED or ACCEPTED status is not
 * shown as “Confirmed”; a request records intent and does not take payment
 * (docs/DECISIONS.md ADR-046).
 */
export function BookingRequestButton({
  itineraryId,
  itineraryItemId,
  initialBooking,
}: {
  itineraryId: string;
  itineraryItemId: string;
  initialBooking?: ApiBookingRequest | null;
}) {
  const [booking, setBooking] = useState<ApiBookingRequest | null>(initialBooking ?? null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (booking) {
    const tone = bookingStatusTone(booking.status as BookingStatus);

    return (
      <Badge tone={tone === "neutral" ? "neutral" : tone}>
        {bookingStatusLabel(booking.status as BookingStatus)}
      </Badge>
    );
  }

  async function handleRequest() {
    setSubmitting(true);
    setError(null);

    try {
      const created = await createBookingRequest(itineraryId, {
        itinerary_item_id: itineraryItemId,
      });
      setBooking(created);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not send the booking request.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <Button
        size="sm"
        variant="outline"
        loading={submitting}
        onClick={handleRequest}
        className="rounded-full border-accent/30 bg-accent-soft px-4 text-accent hover:border-accent/50 hover:bg-accent-soft"
      >
        Request booking
      </Button>
      {error ? (
        <span className="max-w-48 text-right text-xs text-danger">{error}</span>
      ) : null}
    </div>
  );
}