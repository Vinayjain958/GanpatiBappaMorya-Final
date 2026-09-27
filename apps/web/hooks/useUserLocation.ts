"use client";

import { useCallback, useState } from "react";

export type UserLocationStatus = "idle" | "loading" | "success" | "denied" | "error";

/**
 * Browser geolocation wrapper. Never requested automatically — only via
 * the explicit `request()` call, triggered by a user clicking "Use my
 * location" (docs/DECISIONS.md ADR-026 — location privacy). The
 * coordinate is held only in this hook's React state, never persisted.
 */
export function useUserLocation() {
  const [status, setStatus] = useState<UserLocationStatus>("idle");
  const [coordinate, setCoordinate] = useState<{ lat: number; lng: number } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const request = useCallback(() => {
    if (!("geolocation" in navigator)) {
      setStatus("error");
      setError("Your browser doesn't support location.");
      return;
    }
    setStatus("loading");
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setCoordinate({ lat: position.coords.latitude, lng: position.coords.longitude });
        setStatus("success");
      },
      (geoError) => {
        setStatus(geoError.code === geoError.PERMISSION_DENIED ? "denied" : "error");
        setError(geoError.message);
      },
      { enableHighAccuracy: false, timeout: 10_000, maximumAge: 5 * 60 * 1000 },
    );
  }, []);

  const clear = useCallback(() => {
    setCoordinate(null);
    setStatus("idle");
    setError(null);
  }, []);

  return { status, coordinate, error, request, clear };
}
