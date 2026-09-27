import type { Metadata } from "next";
import { RequireRole } from "@/components/common/RequireRole";
import { CollabHome } from "@/components/collab/CollabHome";

export const metadata: Metadata = { title: "Collab" };

export default function CollabPage() {
  return <RequireRole role="traveler"><CollabHome /></RequireRole>;
}
