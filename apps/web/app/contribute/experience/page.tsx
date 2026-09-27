"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { PageContainer } from "@/components/layout/PageContainer";
import { RequireRole } from "@/components/common/RequireRole";
import { Button } from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import {
  ExperienceContributionForm,
  type ContributionFormState,
} from "@/components/contribution/ExperienceContributionForm";
import { useExperienceContribution } from "@/hooks/useExperienceContribution";

export default function AddLocalExperiencePage() {
  const router = useRouter();
  const { status, error, published, duplicate, submit, reset } = useExperienceContribution();
  const [isOverriding, setIsOverriding] = useState(false);
  const lastSubmission = useRef<ContributionFormState | null>(null);

  async function handleSubmit(state: ContributionFormState) {
    lastSubmission.current = state;
    try {
      await submit(state.values, state.image);
    } catch {
      // error state is already set by the hook; nothing further to do here.
    }
  }

  async function handleContinueAnyway() {
    if (!lastSubmission.current) return;
    setIsOverriding(true);
    try {
      await submit(lastSubmission.current.values, lastSubmission.current.image, true);
    } catch {
      // handled by hook state
    } finally {
      setIsOverriding(false);
    }
  }

  function handleStartOver() {
    lastSubmission.current = null;
    reset();
  }

  if (status === "success" && published) {
    return (
      <PageContainer className="max-w-xl space-y-6 py-10 sm:py-14">
        <Card>
          <CardBody className="space-y-5 p-6 text-center sm:p-8">
            <h1 className="text-2xl font-semibold tracking-tight text-ink">
              Your local experience is now live on LocaLens.
            </h1>
            <p className="text-sm text-ink-muted">
              {published.experience.title} is now discoverable by other travelers.
            </p>
            <div className="flex flex-col gap-2 sm:flex-row sm:justify-center">
              <Button onClick={() => router.push(`/discover/${published.experience.id}`)}>
                View Experience
              </Button>
              <Button variant="outline" onClick={handleStartOver}>
                Add Another
              </Button>
            </div>
          </CardBody>
        </Card>
      </PageContainer>
    );
  }

  return (
    <RequireRole role="traveler">
      <PageContainer className="max-w-2xl space-y-7 py-8 sm:py-10">
        <div className="space-y-2">
          <h1 className="text-3xl font-semibold tracking-tight text-ink sm:text-4xl">
            Add a Local Experience
          </h1>
          <p className="text-sm leading-6 text-ink-muted">
            Found a great local spot while exploring? Share it — it goes live immediately after a
            quick automated check.
          </p>
        </div>

        {duplicate ? (
          <Card>
            <CardBody className="space-y-4 p-6">
              <h2 className="text-lg font-semibold text-ink">{duplicate.info.message}</h2>
              <p className="text-sm text-ink-muted">
                {duplicate.blocking
                  ? "This looks like an existing listing, so we didn't create a duplicate."
                  : "We found a similar listing nearby. You can view it, or continue if this is a different place."}
              </p>
              <div className="flex flex-col gap-2 sm:flex-row">
                <Button onClick={() => router.push(`/discover/${duplicate.info.existing_experience_id}`)}>
                  View Existing Experience
                </Button>
                {duplicate.blocking ? (
                  <Button variant="outline" onClick={handleStartOver}>
                    Start Over
                  </Button>
                ) : (
                  <Button variant="outline" loading={isOverriding} onClick={handleContinueAnyway}>
                    Continue Anyway
                  </Button>
                )}
              </div>
            </CardBody>
          </Card>
        ) : (
          <ExperienceContributionForm
            error={error}
            isSubmitting={status === "submitting"}
            onSubmit={handleSubmit}
          />
        )}
      </PageContainer>
    </RequireRole>
  );
}
