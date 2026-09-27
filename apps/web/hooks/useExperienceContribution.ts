"use client";

import { useCallback, useRef, useState } from "react";
import { ApiError } from "@/lib/api/client";
import { submitExperienceContribution } from "@/lib/api/contributions";
import type { ContributionFormValues, ContributionPublishResponse, DuplicateFoundResponse } from "@/types/contribution";

type Status = "idle" | "submitting" | "success" | "duplicate" | "error";

/** Orchestrates the traveler contribution submit/loading/error/success/
 * duplicate lifecycle. Generates one Idempotency-Key per hook instance
 * (i.e. per mount of the contribution page) so a network retry or an
 * accidental double-click never publishes twice — kept in a
 * ref, not state, since it must not change across re-renders or
 * re-submissions of the *same* attempt. */
export function useExperienceContribution() {
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const [published, setPublished] = useState<ContributionPublishResponse | null>(null);
  const [duplicate, setDuplicate] = useState<{ blocking: boolean; info: DuplicateFoundResponse } | null>(null);
  const idempotencyKeyRef = useRef<string>(crypto.randomUUID());

  const submit = useCallback(
    async (values: ContributionFormValues, image: File, overrideDuplicateCheck = false) => {
      setStatus("submitting");
      setError(null);
      setDuplicate(null);

      try {
        const result = await submitExperienceContribution(values, image, idempotencyKeyRef.current, {
          overrideDuplicateCheck,
        });
        if (result.kind === "duplicate") {
          setDuplicate({ blocking: result.blocking, info: result.data });
          setStatus("duplicate");
          return result;
        }
        setPublished(result.data);
        setStatus("success");
        return result;
      } catch (err) {
        setError(
          err instanceof ApiError
            ? err.message
            : "We couldn't publish this experience right now. Your information was not published.",
        );
        setStatus("error");
        throw err;
      }
    },
    [],
  );

  const reset = useCallback(() => {
    setStatus("idle");
    setError(null);
    setPublished(null);
    setDuplicate(null);
    idempotencyKeyRef.current = crypto.randomUUID();
  }, []);

  return {
    status,
    isSubmitting: status === "submitting",
    error,
    published,
    duplicate,
    submit,
    reset,
  };
}
