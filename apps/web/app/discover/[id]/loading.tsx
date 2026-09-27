import { PageContainer } from "@/components/layout/PageContainer";
import { Skeleton } from "@/components/ui/Skeleton";

export default function ExperienceDetailLoading() {
  return (
    <PageContainer
      className="space-y-7 py-8 sm:py-10"
      aria-busy="true"
      aria-live="polite"
    >
      <Skeleton className="aspect-[16/9] w-full rounded-3xl sm:aspect-[21/9]" />
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px] lg:gap-8">
        <div className="space-y-4">
          <Skeleton className="h-10 w-2/3 rounded-xl" />
          <Skeleton className="h-5 w-1/2 rounded-lg" />
          <Skeleton className="h-28 w-full rounded-2xl" />
        </div>
        <Skeleton className="h-64 w-full rounded-3xl" />
      </div>
    </PageContainer>
  );
}