import { env } from "@/lib/config/env";

/**
 * Centralized map configuration — never hardcode a style URL inside a
 * component. Swapping to MapTiler or another provider later means
 * changing only NEXT_PUBLIC_MAP_STYLE_URL, not any component code.
 * See docs/DECISIONS.md ADR-025.
 */
export const mapConfig = {
  styleUrl: env.mapStyleUrl,
  defaultCenter: { lat: 18.9346, lng: 72.8356 }, // Fort, Mumbai — initial view only
  defaultZoom: 12,
  maxZoom: 18,
  minZoom: 3,
  /** Shown alongside MapLibre's own attribution control. OpenFreeMap's
   * current guidance: "OpenFreeMap © OpenMapTiles Data from OpenStreetMap".
   * Update this if NEXT_PUBLIC_MAP_STYLE_URL points somewhere else. */
  attributionHtml:
    '<a href="https://openfreemap.org" target="_blank" rel="noopener noreferrer">OpenFreeMap</a> ' +
    '© <a href="https://www.openmaptiles.org/" target="_blank" rel="noopener noreferrer">OpenMapTiles</a> ' +
    'Data from <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a>',
} as const;
