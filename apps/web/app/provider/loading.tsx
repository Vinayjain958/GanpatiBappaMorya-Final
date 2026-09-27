import { PageContainer } from "@/components/layout/PageContainer";
import { Skeleton } from "@/components/ui/Skeleton";

export default function ProviderLoading() {
  return (
    <PageContainer
      className="space-y-7 py-8 sm:py-10"
      aria-busy="true"
      aria-live="polite"
    >
      <Skeleton className="h-10 w-64 rounded-xl" />
      <div className="grid gap-5 sm:grid-cols-3">
        {Array.from({ length: 3 }).map((_, index) => (
          <Skeleton key={index} className="h-32 w-full rounded-2xl" />
        ))}
      </div>
    </PageContainer>
  );
}