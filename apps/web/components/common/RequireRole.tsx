"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { ShieldAlert } from "lucide-react";
import { useAuth } from "@/lib/auth/AuthContext";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import type { UserRole } from "@/types/auth";

/**
 * Client-side render guard for role-specific pages. This is a UX
 * convenience, not the security boundary — proxy.ts does an optimistic
 * pre-check, and the FastAPI backend independently enforces role and
 * ownership on every request regardless of what this component renders.
 */
export function RequireRole({ role, children }: { role: UserRole; children: ReactNode }) {
  const { user, isLoading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!isLoading && !user) {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    }
  }, [isLoading, user, router, pathname]);

  if (isLoading) {
    return (
      <div className="mx-auto w-full max-w-7xl space-y-4 px-4 py-8 sm:px-6 lg:px-8">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-40 w-full rounded-xl" />
      </div>
    );
  }

  if (!user) return null;

  if (user.role !== role) {
    return (
      <div className="mx-auto w-full max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
        <EmptyState
          icon={ShieldAlert}
          title="This page isn't available for your account"
          description={`This area is for ${role} accounts. You're signed in as a ${user.role}.`}
        />
      </div>
    );
  }

  return <>{children}</>;
}
