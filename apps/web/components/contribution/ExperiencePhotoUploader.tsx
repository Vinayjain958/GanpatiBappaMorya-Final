"use client";

import { useRef, useState } from "react";
import { Camera, ImagePlus, X } from "lucide-react";
import { Button } from "@/components/ui/Button";

const ACCEPTED_TYPES = "image/jpeg,image/png,image/webp";

// Phone photos are routinely 5-12 MB; the upload is proxied through the
// frontend host, whose request-body limit is ~4.5 MB. Anything above
// COMPRESS_ABOVE_BYTES is downscaled in the browser first (the server
// re-validates and re-encodes regardless — this only keeps uploads small).
const MAX_PICK_BYTES = 25 * 1024 * 1024;
const COMPRESS_ABOVE_BYTES = 1.5 * 1024 * 1024;
const MAX_DIMENSION_PX = 2000;

async function shrinkPhoto(file: File): Promise<File> {
  if (file.size <= COMPRESS_ABOVE_BYTES) return file;
  const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
  try {
    const scale = Math.min(1, MAX_DIMENSION_PX / Math.max(bitmap.width, bitmap.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round(bitmap.width * scale));
    canvas.height = Math.max(1, Math.round(bitmap.height * scale));
    const context = canvas.getContext("2d");
    if (!context) return file;
    context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.85));
    if (!blob || blob.size >= file.size) return file;
    return new File([blob], file.name.replace(/\.[^.]+$/, "") + ".jpg", { type: "image/jpeg" });
  } finally {
    bitmap.close();
  }
}

/**
 * Photo-first upload for the traveler contribution flow.
 * Two separate file inputs: one with `capture="environment"` so mobile
 * browsers open the rear camera directly, one plain picker for the
 * gallery/desktop file dialog. Client-side type/size checks here are a
 * UX nicety only — the server (services/media_validation.py) is the
 * authoritative check and re-validates real file content regardless of
 * what the browser reports.
 */
export function ExperiencePhotoUploader({
  file,
  onChange,
  maxBytes = 8 * 1024 * 1024,
}: {
  file: File | null;
  onChange: (file: File | null) => void;
  maxBytes?: number;
}) {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [warning, setWarning] = useState<string | null>(null);
  const [preparing, setPreparing] = useState(false);
  const cameraInputRef = useRef<HTMLInputElement>(null);
  const galleryInputRef = useRef<HTMLInputElement>(null);

  async function handlePick(selected: File | undefined) {
    setWarning(null);
    if (!selected) return;

    if (!["image/jpeg", "image/png", "image/webp"].includes(selected.type)) {
      setWarning("Please choose a JPG, PNG, or WebP image.");
      return;
    }
    if (selected.size > MAX_PICK_BYTES) {
      setWarning("That photo is too large — please choose a smaller one.");
      return;
    }

    setPreparing(true);
    let prepared = selected;
    try {
      prepared = await shrinkPhoto(selected);
    } catch {
      // Decoding failed in this browser — fall back to the original file
      // and let the size check below / the server decide.
    } finally {
      setPreparing(false);
    }
    if (prepared.size > maxBytes) {
      setWarning("That photo is too large — please choose a smaller one.");
      return;
    }

    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(URL.createObjectURL(prepared));
    onChange(prepared);
  }

  function clear() {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null);
    setWarning(null);
    onChange(null);
    if (cameraInputRef.current) cameraInputRef.current.value = "";
    if (galleryInputRef.current) galleryInputRef.current.value = "";
  }

  if (file && previewUrl) {
    return (
      <div className="space-y-2">
        <div className="relative aspect-[4/3] w-full overflow-hidden rounded-2xl bg-surface-sunken">
          {/* eslint-disable-next-line @next/next/no-img-element -- local object URL preview, next/image needs a served URL */}
          <img src={previewUrl} alt="" className="size-full object-cover" />
          <button
            type="button"
            onClick={clear}
            aria-label="Remove photo"
            className="absolute right-3 top-3 inline-flex size-9 items-center justify-center rounded-full bg-surface/90 text-ink shadow-sm backdrop-blur hover:bg-danger-soft hover:text-danger"
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-col gap-2 sm:flex-row">
        <Button type="button" variant="outline" loading={preparing} onClick={() => cameraInputRef.current?.click()} className="flex-1">
          <Camera className="size-4" aria-hidden="true" />
          Take Photo
        </Button>
        <Button type="button" variant="outline" disabled={preparing} onClick={() => galleryInputRef.current?.click()} className="flex-1">
          <ImagePlus className="size-4" aria-hidden="true" />
          Choose from Gallery
        </Button>
      </div>

      {/* Rear camera on supporting mobile browsers; falls back to a
          normal file picker everywhere else. */}
      <input
        ref={cameraInputRef}
        type="file"
        accept={ACCEPTED_TYPES}
        capture="environment"
        className="sr-only"
        onChange={(event) => void handlePick(event.target.files?.[0])}
      />
      <input
        ref={galleryInputRef}
        type="file"
        accept={ACCEPTED_TYPES}
        className="sr-only"
        onChange={(event) => void handlePick(event.target.files?.[0])}
      />

      {warning ? <p className="text-xs text-danger">{warning}</p> : null}
    </div>
  );
}
