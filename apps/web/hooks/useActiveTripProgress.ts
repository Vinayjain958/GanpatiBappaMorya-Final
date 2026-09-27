"use client";

import { useEffect, useState } from "react";
import {
  ACTIVE_TRIP_PROGRESS_EVENT,
  readActiveTripProgress,
  type ActiveTripProgress,
} from "@/lib/itinerary/activeTripProgress";

export function useActiveTripProgress(userId: string | null | undefined): ActiveTripProgress | null {
  const [progress, setProgress] = useState<ActiveTripProgress | null>(null);

  useEffect(() => {
    const sync = () => setProgress(readActiveTripProgress(userId));
    sync();
    window.addEventListener(ACTIVE_TRIP_PROGRESS_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(ACTIVE_TRIP_PROGRESS_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, [userId]);

  return progress;
}
