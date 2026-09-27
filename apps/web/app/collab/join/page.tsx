import type { Metadata } from "next";
import { RequireRole } from "@/components/common/RequireRole";
import { CollabJoinForm } from "@/components/collab/CollabJoinForm";

export const metadata: Metadata = { title: "Join Collab group" };

export default function JoinCollabPage() {
  return <RequireRole role="traveler"><CollabJoinForm /></RequireRole>;
}
