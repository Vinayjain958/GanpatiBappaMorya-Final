import { Camera } from "lucide-react";
import type { ExperienceImage } from "@/types/experience";

/** Compact Wikimedia Commons attribution, expanding into full credit —
 * never just "Image from Wikimedia": author/license come from the
 * actual per-image metadata (apps/api/src/services/experience_images.py),
 * since not every Commons image shares the same license. Renders nothing
 * for LocaLens's own category fallback art (isFallback) or when there is
 * no attribution text to show. */
export function ImageAttribution({ image }: { image: ExperienceImage }) {
  if (image.isFallback || !image.attributionText) return null;

  const content = (
    <span className="inline-flex items-center gap-1">
      <Camera className="size-3" aria-hidden="true" />
      {image.attributionText}
    </span>
  );

  return (
    <div className="text-[11px] leading-tight text-ink-subtle">
      {image.sourceUrl ? (
        <a
          href={image.sourceUrl}
          target="_blank"
          rel="noopener noreferrer nofollow"
          className="inline-flex items-center gap-1 hover:text-ink-muted hover:underline"
        >
          {content}
        </a>
      ) : (
        content
      )}
      {!image.isPlaceSpecific ? <span className="ml-1.5 italic">(representative image)</span> : null}
    </div>
  );
}
