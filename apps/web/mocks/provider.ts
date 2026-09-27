import type { ProviderExperienceRow, ProviderInsightStat, ProviderProfile } from "@/types/provider";

/** DEMO / MOCK DATA — presentation only. See mocks/experiences.ts for labelling rationale. */
export const mockProviderProfile: ProviderProfile = {
  id: "prov-heritage-trails",
  businessName: "Bombay Heritage Trails",
  category: "Walking tours & heritage",
  verified: true,
  memberSince: "2024",
};

export const mockProviderExperiences: ProviderExperienceRow[] = [
  {
    id: "exp-heritage-walk-fort",
    title: "Fort Heritage Walking Trail",
    priceInr: 450,
    durationMinutes: 90,
    status: "active",
    availabilityLabel: "Daily, 9am – 6pm",
    views: 1240,
    saves: 96,
    bookingsPlaceholder: 0,
  },
  {
    id: "exp-market-exploration",
    title: "Crawford Market Morning Exploration",
    priceInr: 300,
    durationMinutes: 60,
    status: "active",
    availabilityLabel: "Daily, 8am – 11am",
    views: 580,
    saves: 41,
    bookingsPlaceholder: 0,
  },
  {
    id: "exp-monsoon-heritage",
    title: "Monsoon Heritage Walk (seasonal)",
    priceInr: 500,
    durationMinutes: 90,
    status: "draft",
    availabilityLabel: "Not yet published",
    views: 0,
    saves: 0,
    bookingsPlaceholder: 0,
  },
];

export const mockProviderInsights: ProviderInsightStat[] = [
  { id: "views", label: "Profile views (7d)", value: "1,820", changeLabel: "Demo data", trend: "flat" },
  { id: "saves", label: "Experience saves (7d)", value: "137", changeLabel: "Demo data", trend: "flat" },
  { id: "bookings", label: "Booking requests", value: "—", changeLabel: "Not available yet" },
  { id: "conversion", label: "View → save rate", value: "7.5%", changeLabel: "Demo data", trend: "flat" },
];
