import type { Metadata } from "next";
import { RequireRole } from "@/components/common/RequireRole";
import { CollabGroupWorkspace } from "@/components/collab/CollabGroupWorkspace";

export const metadata: Metadata = { title: "Collab group" };

export default async function CollabGroupPage({ params }: PageProps<"/collab/[groupId]">) {
  const { groupId } = await params;
  return <RequireRole role="traveler"><CollabGroupWorkspace groupId={groupId} /></RequireRole>;
}
