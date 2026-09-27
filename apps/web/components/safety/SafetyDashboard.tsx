"use client";

import { useCallback, useEffect, useState } from "react";
import { Hospital, Phone, ShieldAlert, Siren, Loader2, MapPin, AlertTriangle } from "lucide-react";
import { SafetyResourceCard } from "@/components/safety/SafetyResourceCard";
import { getNearbySafetyResources, getEmergencyContacts } from "@/lib/api/safety";
import { ApiError } from "@/lib/api/client";
import type { SafetyResource, EmergencyContact } from "@/types/safety";
import { Button } from "@/components/ui/Button";

type LocationStatus =
  | "idle"
  | "requesting_permission"
  | "location_received"
  | "location_denied"
  | "location_unavailable"
  | "location_unsupported";

type ResourceStatus = "idle" | "loading" | "loaded" | "failed";

const GEOLOCATION_OPTIONS: PositionOptions = {
  enableHighAccuracy: true,
  timeout: 15000,
  maximumAge: 60000,
};

export function SafetyDashboard() {
  const [locationStatus, setLocationStatus] = useState<LocationStatus>("idle");
  const [coords, setCoords] = useState<{ lat: number; lng: number } | null>(null);

  const [resources, setResources] = useState<SafetyResource[]>([]);
  const [resourceStatus, setResourceStatus] = useState<ResourceStatus>("idle");
  const [resourceError, setResourceError] = useState<string | null>(null);

  const [contacts, setContacts] = useState<EmergencyContact[]>([]);

  const requestLocation = useCallback(() => {
    if (typeof navigator === "undefined" || !navigator.geolocation) {
      setLocationStatus("location_unsupported");
      return;
    }

    setLocationStatus("requesting_permission");
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setCoords({ lat: position.coords.latitude, lng: position.coords.longitude });
        setLocationStatus("location_received");
      },
      (error) => {
        if (error.code === error.PERMISSION_DENIED) {
          setLocationStatus("location_denied");
        } else {
          setLocationStatus("location_unavailable");
        }
      },
      GEOLOCATION_OPTIONS,
    );
  }, []);

  useEffect(() => {
    async function init() {
      requestLocation();
      const fetchedContacts = await getEmergencyContacts().catch(() => []);
      setContacts(fetchedContacts);
    }
    init();
  }, [requestLocation]);

  useEffect(() => {
    if (!coords) return;

    let cancelled = false;

    async function loadResources() {
      setResourceStatus("loading");
      setResourceError(null);
      try {
        const fetched = await getNearbySafetyResources(coords!.lat, coords!.lng);
        if (cancelled) return;
        setResources(fetched);
        setResourceStatus("loaded");
      } catch (err) {
        if (cancelled) return;
        setResourceStatus("failed");
        setResourceError(
          err instanceof ApiError && err.status === 503
            ? "Safety resource provider is temporarily unavailable."
            : "Failed to load local safety resources.",
        );
      }
    }
    loadResources();

    return () => {
      cancelled = true;
    };
  }, [coords]);

  if (locationStatus === "idle" || locationStatus === "requesting_permission") {
    return (
      <div className="flex h-40 flex-col items-center justify-center gap-2 text-center">
        <Loader2 className="size-8 animate-spin text-accent" aria-hidden="true" />
        <p className="text-sm text-ink-muted">Getting your location…</p>
      </div>
    );
  }

  if (locationStatus === "location_denied") {
    return (
      <div className="flex h-40 flex-col items-center justify-center gap-3 rounded-2xl border border-line bg-surface p-6 text-center shadow-soft">
        <AlertTriangle className="size-8 text-danger" aria-hidden="true" />
        <p className="text-sm text-ink">
          Location access is required to find nearby safety resources.
        </p>
        <Button variant="outline" size="sm" onClick={requestLocation}>
          Try again
        </Button>
      </div>
    );
  }

  if (locationStatus === "location_unavailable" || locationStatus === "location_unsupported") {
    return (
      <div className="flex h-40 flex-col items-center justify-center gap-3 rounded-2xl border border-line bg-surface p-6 text-center shadow-soft">
        <AlertTriangle className="size-8 text-danger" aria-hidden="true" />
        <p className="text-sm text-ink">
          {locationStatus === "location_unsupported"
            ? "Your browser does not support location services."
            : "We couldn't determine your location."}
        </p>
        <Button variant="outline" size="sm" onClick={requestLocation}>
          Try again
        </Button>
      </div>
    );
  }

  const hospitals = resources.filter((r) => r.type === "hospital").slice(0, 3);
  const police = resources.filter((r) => r.type === "police").slice(0, 3);
  const consulates = resources.filter((r) => r.type === "consulate").slice(0, 3);
  const usingSimulatedData = resources.length > 0 && resources.every((r) => r.is_synthetic);

  return (
    <div className="space-y-8">
      <div className="inline-flex items-center gap-1.5 rounded-full bg-surface-raised px-3 py-1.5 text-xs text-ink-muted">
        <MapPin className="size-3.5" aria-hidden="true" />
        Using your current location
      </div>

      {resourceStatus === "loading" && (
        <div className="flex h-24 items-center justify-center gap-2 text-sm text-ink-muted">
          <Loader2 className="size-5 animate-spin text-accent" aria-hidden="true" />
          Finding nearby safety resources…
        </div>
      )}

      {resourceStatus === "failed" && (
        <div className="rounded-2xl bg-danger-soft p-4 text-sm text-danger">
          {resourceError}
        </div>
      )}

      {resourceStatus === "loaded" && usingSimulatedData && (
        <div className="flex items-center gap-2 rounded-2xl bg-warning-soft p-3.5 text-sm text-warning">
          <AlertTriangle className="size-4 shrink-0" aria-hidden="true" />
          Live safety data is unavailable right now — showing simulated fallback data.
        </div>
      )}

      {resourceStatus === "loaded" && (
        <>
          <div className="space-y-4">
            <h2 className="text-xl font-semibold tracking-tight text-ink">Nearby Hospitals</h2>
            <div className="grid gap-4 sm:grid-cols-2">
              {hospitals.length > 0 ? hospitals.map(hospital => (
                <SafetyResourceCard
                  key={hospital.id}
                  icon={Hospital}
                  resource={hospital}
                />
              )) : (
                <p className="text-sm text-ink-muted">No hospitals found nearby.</p>
              )}
            </div>
          </div>

          <div className="space-y-4">
            <h2 className="text-xl font-semibold tracking-tight text-ink">Police Stations</h2>
            <div className="grid gap-4 sm:grid-cols-2">
              {police.length > 0 ? police.map(station => (
                <SafetyResourceCard
                  key={station.id}
                  icon={Siren}
                  resource={station}
                />
              )) : (
                <p className="text-sm text-ink-muted">No police stations found nearby.</p>
              )}
            </div>
          </div>

          <div className="space-y-4">
            <h2 className="text-xl font-semibold tracking-tight text-ink">Consulates & Embassies</h2>
            <div className="grid gap-4 sm:grid-cols-2">
              {consulates.length > 0 ? consulates.map(consulate => (
                <SafetyResourceCard
                  key={consulate.id}
                  icon={ShieldAlert}
                  resource={consulate}
                />
              )) : (
                <p className="text-sm text-ink-muted">No consulates found nearby.</p>
              )}
            </div>
          </div>
        </>
      )}

      <div className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-xl font-semibold tracking-tight text-ink">Emergency Contacts</h2>
          <Button variant="outline" size="sm">Add Contact</Button>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          {contacts.length > 0 ? contacts.map(contact => (
            <div key={contact.id} className="rounded-2xl border border-line bg-surface p-4 shadow-soft">
              <p className="font-semibold text-ink">{contact.name}</p>
              <p className="text-sm text-ink-muted">{contact.relationship}</p>
              <a href={`tel:${contact.phone}`} className="mt-2 inline-flex items-center gap-1.5 font-medium text-accent">
                <Phone className="size-4" aria-hidden="true" />
                {contact.phone}
              </a>
            </div>
          )) : (
            <p className="text-sm text-ink-muted">No emergency contacts added yet.</p>
          )}
        </div>
      </div>
    </div>
  );
}
