"use client";

import { useEffect } from "react";
import { PageContainer } from "@/components/layout/PageContainer";
import { ErrorState } from "@/components/ui/ErrorState";

export default function RootError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <PageContainer className="py-16 sm:py-24">
      <ErrorState
        title="LocaLens hit a snag"
        description="An unexpected error occurred while rendering this page."
        onRetry={reset}
      />
    </PageContainer>
  );
}