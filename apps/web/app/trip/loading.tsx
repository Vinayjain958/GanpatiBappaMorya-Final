import { PageContainer } from "@/components/layout/PageContainer";
import { Skeleton } from "@/components/ui/Skeleton";

export default function TripLoading() {
  return (
    <PageContainer
      className="space-y-7 py-8 sm:py-10"
      aria-busy="true"
      aria-live="polite"
    >
      <Skeleton className="h-10 w-56 rounded-xl" />
      <Skeleton className="h-28 w-full rounded-2xl" />
      <Skeleton className="h-28 w-full rounded-2xl" />
    </PageContainer>
  );
}