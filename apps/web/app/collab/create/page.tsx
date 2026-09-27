import type { Metadata } from "next";
import { RequireRole } from "@/components/common/RequireRole";
import { CollabCreateForm } from "@/components/collab/CollabCreateForm";

export const metadata: Metadata = { title: "Create Collab group" };

export default function CreateCollabPage() {
  return <RequireRole role="traveler"><CollabCreateForm /></RequireRole>;
}
