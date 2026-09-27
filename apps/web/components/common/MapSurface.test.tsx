import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ExperienceFeatureCollection } from "@/lib/geo/geojson";
import type { MapAnnotationCollection } from "@/types/map";

const mapMock = vi.hoisted(() => ({
  instance: null as {
    handlers: Record<string, (event?: unknown) => void>;
    sources: Record<string, { setData: ReturnType<typeof vi.fn> }>;
    layers: Array<{ id: string; source: string }>;
    options: Record<string, unknown>;
    controls: unknown[];
    addControl: ReturnType<typeof vi.fn>;
    fitBounds: ReturnType<typeof vi.fn>;
    remove: ReturnType<typeof vi.fn>;
    easeTo: ReturnType<typeof vi.fn>;
    jumpTo: ReturnType<typeof vi.fn>;
  } | null,
  popupHtml: "",
}));

vi.mock("maplibre-gl", () => {
  class FakeMap {
    handlers: Record<string, (event?: unknown) => void> = {};
    sources: Record<string, { setData: ReturnType<typeof vi.fn> }> = {};
    layers: Array<{ id: string; source: string }> = [];
    controls: unknown[] = [];
    options: Record<string, unknown>;
    addControl = vi.fn((control: unknown) => this.controls.push(control));
    fitBounds = vi.fn();
    remove = vi.fn();
    easeTo = vi.fn();
    jumpTo = vi.fn();

    constructor(options: Record<string, unknown>) {
      this.options = options;
      mapMock.instance = this;
    }

    on(event: string, layerOrHandler: string | ((event?: unknown) => void), handler?: (event?: unknown) => void) {
      const layer = typeof layerOrHandler === "string" ? layerOrHandler : "";
      this.handlers[`${event}:${layer}`] = handler ?? layerOrHandler as (event?: unknown) => void;
      return this;
    }

    addSource(id: string) {
      this.sources[id] = { setData: vi.fn() };
    }

    addLayer(layer: { id: string; source: string }) {
      this.layers.push(layer);
    }

    getSource(id: string) {
      return this.sources[id];
    }

    getCanvas() {
      return { style: { cursor: "" } };
    }

    getBounds() {
      return {
        getSouth: () => 18.9,
        getNorth: () => 19.0,
        getWest: () => 72.8,
        getEast: () => 72.9,
      };
    }

    queryRenderedFeatures() {
      return [];
    }
  }

  class FakePopup {
    setLngLat() { return this; }
    setHTML(html: string) { mapMock.popupHtml = html; return this; }
    addTo() { return this; }
    remove() { return this; }
  }

  return {
    Map: FakeMap,
    Popup: FakePopup,
    NavigationControl: class { constructor(public options: unknown) {} },
    AttributionControl: class { constructor(public options: unknown) {} },
    setWorkerUrl: vi.fn(),
  };
});

import { MapSurface } from "@/components/common/MapSurface";

const experiences: ExperienceFeatureCollection = {
  type: "FeatureCollection",
  features: [{
    type: "Feature",
    geometry: { type: "Point", coordinates: [72.83, 18.93] },
    properties: { id: "experience-1", title: "Tea & Art", category: "culture", categoryLabel: "Gallery", price: 300, isSynthetic: false, selected: true },
  }],
};
const annotations: MapAnnotationCollection = {
  type: "FeatureCollection",
  features: [{
    type: "Feature",
    geometry: { type: "Point", coordinates: [72.84, 18.94] },
    properties: { id: "stop-1", label: "1", title: "<First stop>", description: "Selected stop", kind: "stop", tone: "selected", locked: false, affected: false },
  }],
};

let root: Root | null = null;
let container: HTMLDivElement;

function renderSurface(props: Parameters<typeof MapSurface>[0]) {
  container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
  act(() => root?.render(<MapSurface {...props} />));
}

beforeEach(() => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  mapMock.instance = null;
  mapMock.popupHtml = "";
  vi.stubGlobal("matchMedia", () => ({ matches: false }));
});

afterEach(() => {
  if (root) act(() => root?.unmount());
  root = null;
  container?.remove();
  vi.unstubAllGlobals();
});

describe("MapSurface", () => {
  it("keeps the experience map and adds generic stop, origin, route and fit sources", () => {
    renderSurface({
      features: experiences,
      annotations,
      origin: { lat: 18.92, lng: 72.82 },
      routeGeometry: { type: "LineString", coordinates: [[72.82, 18.92], [72.83, 18.93]] },
      routeGeometries: [{ type: "LineString", coordinates: [[72.83, 18.93], [72.84, 18.94]] }],
      fitBounds: [[72.8, 18.9], [72.9, 19.0]],
      fitBoundsRequestId: 1,
      label: "Trip map",
    });

    const map = mapMock.instance;
    expect(map?.options.style).toContain("openfreemap");
    expect(container.querySelector('[role="img"]')?.getAttribute("aria-label")).toBe("Trip map");
    expect(map?.controls).toHaveLength(2);
    act(() => map?.handlers["load:"]());

    expect(map?.layers.some((layer) => layer.id === "experience-clusters")).toBe(true);
    expect(map?.layers.some((layer) => layer.id === "map-annotation-labels")).toBe(true);
    expect(map?.sources.experiences.setData).toHaveBeenLastCalledWith(experiences);
    expect(map?.sources["map-annotations"].setData).toHaveBeenLastCalledWith(annotations);
    expect(map?.sources["map-origin"].setData).toHaveBeenLastCalledWith(expect.objectContaining({
      features: [expect.objectContaining({ geometry: { type: "Point", coordinates: [72.82, 18.92] } })],
    }));
    expect(map?.sources["map-route"].setData).toHaveBeenLastCalledWith(expect.objectContaining({ features: expect.arrayContaining([
      expect.objectContaining({ geometry: { type: "LineString", coordinates: [[72.82, 18.92], [72.83, 18.93]] } }),
      expect.objectContaining({ geometry: { type: "LineString", coordinates: [[72.83, 18.93], [72.84, 18.94]] } }),
    ]) }));
    expect(map?.fitBounds).toHaveBeenCalledWith([[72.8, 18.9], [72.9, 19.0]], expect.objectContaining({ maxZoom: 14 }));
  });

  it("keeps map selection, popup safety and Search this area interactions", () => {
    const onSelectFeature = vi.fn();
    const onSelectAnnotation = vi.fn();
    const onSearchThisArea = vi.fn();
    renderSurface({ features: experiences, annotations, onSelectFeature, onSelectAnnotation, onSearchThisArea });
    const map = mapMock.instance;
    act(() => map?.handlers["load:"]());

    act(() => map?.handlers["click:experience-points"]({ features: [{
      geometry: experiences.features[0]?.geometry,
      properties: experiences.features[0]?.properties,
    }] }));
    expect(onSelectFeature).toHaveBeenCalledWith("experience-1");
    expect(mapMock.popupHtml).toContain("Tea & Art");

    act(() => map?.handlers["click:map-annotation-points"]({ features: [{
      geometry: annotations.features[0]?.geometry,
      properties: annotations.features[0]?.properties,
    }] }));
    expect(onSelectAnnotation).toHaveBeenCalledWith("stop-1");
    expect(mapMock.popupHtml).toContain("&lt;First stop&gt;");

    act(() => map?.handlers["dragend:"]());
    const searchButton = Array.from(container.querySelectorAll("button")).find((button) => button.textContent?.includes("Search this area"));
    expect(searchButton).toBeDefined();
    act(() => searchButton?.click());
    expect(onSearchThisArea).toHaveBeenCalledWith({ minLat: 18.9, maxLat: 19, minLng: 72.8, maxLng: 72.9 });
  });
});
