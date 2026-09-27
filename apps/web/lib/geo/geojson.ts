import type { Experience } from "@/types/experience";

export interface ExperienceFeatureProperties {
  id: string;
  title: string;
  category: string;
  categoryLabel: string;
  price: number;
  isSynthetic: boolean;
  selected: boolean;
}

export type ExperienceFeature = GeoJSON.Feature<GeoJSON.Point, ExperienceFeatureProperties>;
export type ExperienceFeatureCollection = GeoJSON.FeatureCollection<GeoJSON.Point, ExperienceFeatureProperties>;

/** The single reusable converter from catalog experiences to map-ready
 * GeoJSON — never duplicated per page/component. Only the fields a
 * marker/popup actually needs are included in `properties`. */
export function experiencesToFeatureCollection(
  experiences: Experience[],
  selectedId?: string | null,
): ExperienceFeatureCollection {
  return {
    type: "FeatureCollection",
    features: experiences.map((experience) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: [experience.location.lng, experience.location.lat] },
      properties: {
        id: experience.id,
        title: experience.title,
        category: experience.category,
        categoryLabel: experience.categoryLabel,
        price: experience.priceInr,
        isSynthetic: experience.isSynthetic,
        selected: experience.id === selectedId,
      },
    })),
  };
}
