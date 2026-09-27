import { Suspense } from "react";
import type { Metadata } from "next";
import { DiscoverExperience } from "./DiscoverExperience";

export const metadata: Metadata = { title: "Discover" };

export default function DiscoverPage() {
  return (
    <Suspense fallback={null}>
      <DiscoverExperience />
    </Suspense>
  );
}
