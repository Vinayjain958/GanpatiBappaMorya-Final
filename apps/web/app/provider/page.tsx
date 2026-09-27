"use client";

import { RequireRole } from "@/components/common/RequireRole";
import { ProviderDashboard } from "./ProviderDashboard";

export default function ProviderDashboardPage() {
  return (
    <RequireRole role="provider">
      <ProviderDashboard />
    </RequireRole>
  );
}
