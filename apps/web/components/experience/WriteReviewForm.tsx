"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import type { FormEvent } from "react";
import { CheckCircle2, PenLine, Star } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Input, Textarea } from "@/components/ui/Input";
import { useAuth } from "@/lib/auth/AuthContext";
import { createExperienceReview } from "@/lib/api/experiences";
import { mapApiRatingSummary, mapApiReview } from "@/lib/api/experienceAdapter";
import { ApiError } from "@/lib/api/client";
import type { ExperienceRatingSummary, ReviewItem } from "@/types/experience";
import { cn } from "@/lib/utils/cn";

const RATING_LABELS = ["", "Poor", "Fair", "Good", "Very good", "Excellent"];

export interface WriteReviewFormProps {
  experienceId: string;
  onSubmitted: (review: ReviewItem, ratingSummary: ExperienceRatingSummary) => void;
}

/** Lets a signed-in traveler post a real review. The server derives the
 * author, provenance and synthetic flag — the form only sends rating,
 * title and text — and returns the recomputed rating summary. */
export function WriteReviewForm({ experienceId, onSubmitted }: WriteReviewFormProps) {
  const { user } = useAuth();
  const pathname = usePathname();
  const [expanded, setExpanded] = useState(false);
  const [rating, setRating] = useState(0);
  const [hoverRating, setHoverRating] = useState(0);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  if (!user) {
    return (
      <div className="rounded-2xl border border-dashed border-line bg-surface-raised/40 p-4 text-sm text-ink-muted">
        <Link
          href={`/login?next=${encodeURIComponent(pathname)}`}
          className="font-semibold text-accent hover:underline"
        >
          Log in
        </Link>{" "}
        as a traveler to write a review.
      </div>
    );
  }

  if (user.role !== "traveler") return null;

  if (success) {
    return (
      <div className="motion-arrive flex items-center gap-2 rounded-2xl border border-success/30 bg-success-soft/60 p-4 text-sm text-ink">
        <CheckCircle2 className="size-4 text-success" aria-hidden="true" />
        Thanks — your review has been posted.
      </div>
    );
  }

  if (!expanded) {
    return (
      <Button variant="outline" size="sm" onClick={() => setExpanded(true)} className="rounded-full">
        <PenLine className="size-4" aria-hidden="true" />
        Write a review
      </Button>
    );
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (rating < 1 || rating > 5) {
      setError("Please choose a star rating.");
      return;
    }
    if (!title.trim() || !body.trim()) {
      setError("Please fill in both a title and your review.");
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      const response = await createExperienceReview(experienceId, {
        rating_value: rating,
        title: title.trim(),
        body: body.trim(),
      });
      onSubmitted(mapApiReview(response.review), mapApiRatingSummary(response.rating_summary));
      setSuccess(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not submit your review. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  const shownRating = hoverRating || rating;

  return (
    <form
      onSubmit={handleSubmit}
      className="motion-arrive space-y-4 rounded-2xl border border-line bg-surface-raised/40 p-4 sm:p-5"
    >
      <div>
        <p className="mb-1.5 text-sm font-medium text-ink">Your rating</p>
        <div className="flex items-center gap-3">
          <div
            className="flex gap-1"
            onMouseLeave={() => setHoverRating(0)}
            role="radiogroup"
            aria-label="Star rating"
          >
            {[1, 2, 3, 4, 5].map((star) => (
              <button
                key={star}
                type="button"
                role="radio"
                aria-checked={rating === star}
                aria-label={`${star} star${star === 1 ? "" : "s"}`}
                onMouseEnter={() => setHoverRating(star)}
                onClick={() => setRating(star)}
                className="rounded-md p-0.5 transition-transform duration-150 hover:scale-110 active:scale-95"
              >
                <Star
                  className={cn(
                    "size-6 transition-colors",
                    star <= shownRating ? "fill-highlight text-highlight" : "text-line-strong",
                  )}
                  aria-hidden="true"
                />
              </button>
            ))}
          </div>
          <span className="text-xs font-medium text-ink-muted" aria-live="polite">
            {RATING_LABELS[shownRating]}
          </span>
        </div>
      </div>

      <Input
        label="Title"
        value={title}
        onChange={(event) => setTitle(event.target.value)}
        maxLength={160}
        placeholder="Sum up your visit"
        required
      />

      <Textarea
        label="Your review"
        value={body}
        onChange={(event) => setBody(event.target.value)}
        maxLength={4000}
        rows={4}
        placeholder="What stood out during your visit?"
        required
      />

      {error ? (
        <p role="alert" className="text-xs text-danger">
          {error}
        </p>
      ) : null}

      <div className="flex gap-2">
        <Button type="submit" size="sm" loading={submitting} className="rounded-full">
          Post review
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => setExpanded(false)}
          disabled={submitting}
          className="rounded-full"
        >
          Cancel
        </Button>
      </div>
    </form>
  );
}
