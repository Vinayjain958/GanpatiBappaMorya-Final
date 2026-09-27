import type { Metadata } from "next";
import { RequireRole } from "@/components/common/RequireRole";
import { PageContainer } from "@/components/layout/PageContainer";
import { ShowcaseWorkspace } from "@/components/showcase/ShowcaseWorkspace";

export const metadata: Metadata = { title: "LocaLens Showcase" };

export default function ShowcasePage() {
  return (
    <RequireRole role="traveler">
      <PageContainer className="space-y-7 py-8 sm:py-10">
        <ShowcaseWorkspace />
      </PageContainer>
    </RequireRole>
  );
}
