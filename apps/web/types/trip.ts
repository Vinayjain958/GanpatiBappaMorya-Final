export type ItineraryItemStatus = "confirmed" | "pending" | "at_risk";

export interface ItineraryItem {
  id: string;
  title: string;
  category: string;
  time: string;
  durationMinutes: number;
  location: string;
  provider: string;
  travelMinutesFromPrevious: number;
  costInr: number;
  status: ItineraryItemStatus;
}

export interface Trip {
  id: string;
  title: string;
  contextSummary: string;
  date: string;
  totalTimeMinutes: number;
  totalTravelMinutes: number;
  totalCostInr: number;
  preferencesMatched: string[];
  items: ItineraryItem[];
  isSynthetic: true;
}
