import { apiClient } from "@/lib/api/client";
import type {
  ApiBookingRequest,
  BookingRequestCreate,
  BookingRequestListResponse,
  BookingStatusUpdate,
} from "@/types/api";

/** POST /api/v1/itineraries/{itineraryId}/booking-requests — Phase 8.
 * Creates a REQUESTED-status booking request only — never a payment, and
 * never returned/rendered as "confirmed". Traveler-auth required. */
export function createBookingRequest(
  itineraryId: string,
  request: BookingRequestCreate,
  signal?: AbortSignal,
) {
  return apiClient.post<ApiBookingRequest>(
    `/api/v1/itineraries/${itineraryId}/booking-requests`,
    request,
    { signal },
  );
}

/** GET /api/v1/bookings/me — the current traveler's own booking requests. */
export function listMyBookingRequests(signal?: AbortSignal) {
  return apiClient.get<BookingRequestListResponse>("/api/v1/bookings/me", { signal });
}

/** GET /api/v1/provider/booking-requests — the current provider's own
 * incoming booking requests only (never another provider's). */
export function listProviderBookingRequests(signal?: AbortSignal) {
  return apiClient.get<BookingRequestListResponse>("/api/v1/provider/booking-requests", { signal });
}

/** PATCH /api/v1/provider/booking-requests/{id} — ACCEPT or DECLINE.
 * Provider-auth required; the backend enforces the provider owns the
 * underlying experience. ACCEPTED must never be displayed as CONFIRMED. */
export function updateProviderBookingRequest(
  bookingId: string,
  update: BookingStatusUpdate,
  signal?: AbortSignal,
) {
  return apiClient.patch<ApiBookingRequest>(
    `/api/v1/provider/booking-requests/${bookingId}`,
    update,
    { signal },
  );
}

/** POST /api/v1/bookings/{id}/cancel — traveler cancels their own
 * REQUESTED/ACCEPTED booking request. */
export function cancelBookingRequest(bookingId: string, signal?: AbortSignal) {
  return apiClient.post<ApiBookingRequest>(`/api/v1/bookings/${bookingId}/cancel`, undefined, { signal });
}
