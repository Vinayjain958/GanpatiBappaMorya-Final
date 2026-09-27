"use client";

import Image from "next/image";
import { useState } from "react";
import type { ImageProps } from "next/image";

const GENERIC_FALLBACK_IMAGE = "https://images.unsplash.com/photo-1499892477393-f675706cbe6e?w=800&q=80";

/** Wraps next/image with a broken-image fallback: if the resolved image
 * URL (Wikimedia or category art) fails to load, swaps to a single
 * generic fallback rather than showing a broken-image icon. Distinct
 * from the "no image resolved" case (handled by experienceAdapter.ts's
 * category fallback) — this covers a URL that resolves but 404s/errors
 * at render time. */
export function ExperienceImageView({ src, alt, ...rest }: ImageProps) {
  const [currentSrc, setCurrentSrc] = useState(src);
  // Traveler-uploaded photos are served by the API (proxied same-origin at
  // /api/v1/media/*) and are already resized/re-encoded server-side, so
  // they skip the Next image optimizer rather than round-tripping through
  // the rewrite a second time.
  const isUploadedMedia = typeof currentSrc === "string" && currentSrc.startsWith("/api/v1/media/");

  return (
    <Image
      {...rest}
      unoptimized={rest.unoptimized ?? isUploadedMedia}
      src={currentSrc}
      alt={alt}
      onError={() => {
        if (currentSrc !== GENERIC_FALLBACK_IMAGE) setCurrentSrc(GENERIC_FALLBACK_IMAGE);
      }}
    />
  );
}
