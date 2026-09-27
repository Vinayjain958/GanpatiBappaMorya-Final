import type { Metadata } from "next";
import { PageContainer } from "@/components/layout/PageContainer";
import { ProviderInsightsDashboard } from "@/components/provider/ProviderInsightsDashboard";

export const metadata: Metadata = { title: "Provider insights" };

export default function ProviderInsightsPage() {
  return (
    <PageContainer className="space-y-8 py-8 sm:py-10">
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-3xl border border-line bg-surface-raised p-5 shadow-soft sm:p-7">
        <div className="space-y-2">
          <h1 className="text-3xl font-semibold tracking-tight text-ink sm:text-4xl">
            Insights
          </h1>
          <p className="max-w-3xl text-sm leading-6 text-ink-muted">
            Demand intelligence and provider analytics.
          </p>
        </div>
      </div>

      <ProviderInsightsDashboard />
    </PageContainer>
  );
}
