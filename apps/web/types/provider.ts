export interface ProviderExperienceRow {
  id: string;
  title: string;
  priceInr: number;
  durationMinutes: number;
  status: "active" | "draft" | "paused";
  availabilityLabel: string;
  views: number;
  saves: number;
  bookingsPlaceholder: number;
}

export interface ProviderProfile {
  id: string;
  businessName: string;
  category: string;
  verified: boolean;
  memberSince: string;
}

export interface ProviderInsightStat {
  id: string;
  label: string;
  value: string;
  changeLabel?: string;
  trend?: "up" | "down" | "flat";
}
