import type { Metadata } from "next";
import { RequireRole } from "@/components/common/RequireRole";
import { SavedExperiences } from "./SavedExperiences";

export const metadata: Metadata = { title: "Saved" };

export default function SavedPage() {
  return (
    <RequireRole role="traveler">
      <SavedExperiences />
    </RequireRole>
  );
}
