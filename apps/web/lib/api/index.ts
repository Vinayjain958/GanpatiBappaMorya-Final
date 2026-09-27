export { apiClient, ApiError } from "@/lib/api/client";
export { getHealth } from "@/lib/api/health";
export type { HealthResponse } from "@/lib/api/health";
export { getExperience, listExperiences } from "@/lib/api/experiences";
export { mapApiExperienceToUi } from "@/lib/api/experienceAdapter";
export { checkFeasibility, semanticSearchExperiences } from "@/lib/api/feasibility";
export { getMe, login, logout, refreshSession, registerAccount } from "@/lib/api/auth";
export { listCategories } from "@/lib/api/categories";
export type { ApiCategory } from "@/lib/api/categories";
export {
  getNearbyPois,
  getRoute,
  getTravelTimeMatrix,
  reverseGeocode,
  searchLocation,
} from "@/lib/api/location";
export { getMyExperiences, getMyProvider, updateMyProvider } from "@/lib/api/providers";
export {
  createAvailability,
  createExperience,
  deactivateAvailability,
  deactivateExperience,
  listAvailability,
  updateAvailability,
  updateExperience,
} from "@/lib/api/experiencesWrite";

export { recommendationApi } from "@/lib/api/recommendations";
export { feedbackApi } from "@/lib/api/feedback";
export {
  addItineraryItem,
  cancelItinerary,
  composeItinerary,
  getItinerary,
  listMyItineraries,
} from "@/lib/api/itineraries";
export {
  cancelBookingRequest,
  createBookingRequest,
  listMyBookingRequests,
  listProviderBookingRequests,
  updateProviderBookingRequest,
} from "@/lib/api/bookings";
