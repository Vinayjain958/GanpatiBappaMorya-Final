"use client";

import Link from "next/link";
import { useState } from "react";
import type { FormEvent } from "react";
import { useRouter } from "next/navigation";
import { AuthCard } from "@/components/common/AuthCard";
import { Input, Textarea } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/utils/cn";
import { useAuth } from "@/lib/auth/AuthContext";
import { ApiError } from "@/lib/api/client";
import type { RegisterPayload } from "@/types/auth";

type Role = "traveler" | "provider";

export function RegisterForm() {
  const { register } = useAuth();
  const router = useRouter();

  const [role, setRole] = useState<Role>("traveler");
  const [displayName, setDisplayName] = useState("");
  const [businessName, setBusinessName] = useState("");
  const [description, setDescription] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    if (role === "provider" && !businessName.trim()) {
      setError("Business name is required for provider accounts.");
      return;
    }

    setIsSubmitting(true);

    try {
      const payload: RegisterPayload =
        role === "traveler"
          ? { email, password, role: "traveler", display_name: displayName }
          : {
              email,
              password,
              role: "provider",
              display_name: displayName,
              business_name: businessName,
              description: description || undefined,
            };

      const user = await register(payload);
      router.push(user.role === "provider" ? "/provider" : "/discover");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AuthCard
      title="Create your account"
      description="Join LocaLens as a traveler or a local provider."
      footer={
        <>
          Already have an account?{" "}
          <Link href="/login" className="font-medium text-accent hover:underline">
            Log in
          </Link>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-5" noValidate>
        <div
          role="radiogroup"
          aria-label="Account type"
          className="grid grid-cols-2 gap-2 rounded-2xl bg-surface-raised p-1.5"
        >
          {(["traveler", "provider"] as const).map((option) => (
            <button
              key={option}
              type="button"
              role="radio"
              aria-checked={role === option}
              onClick={() => setRole(option)}
              className={cn(
                "rounded-xl border px-3 py-2.5 text-sm font-medium capitalize transition-colors",
                role === option
                  ? "border-accent/25 bg-accent-soft text-accent shadow-sm"
                  : "border-transparent text-ink-muted hover:text-ink",
              )}
            >
              {option}
            </button>
          ))}
        </div>

        <Input
          label="Full name"
          name="name"
          placeholder="Jordan Rao"
          required
          autoComplete="name"
          value={displayName}
          onChange={(event) => setDisplayName(event.target.value)}
        />

        {role === "provider" ? (
          <>
            <Input
              label="Business name"
              name="business_name"
              placeholder="Fort Heritage Walks"
              required
              value={businessName}
              onChange={(event) => setBusinessName(event.target.value)}
            />
            <Textarea
              label="Description (optional)"
              name="description"
              placeholder="Tell travelers what you offer."
              value={description}
              onChange={(event) => setDescription(event.target.value)}
            />
          </>
        ) : null}

        <Input
          type="email"
          label="Email"
          name="email"
          placeholder="you@example.com"
          required
          autoComplete="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
        <Input
          type="password"
          label="Password"
          name="password"
          placeholder="••••••••"
          required
          minLength={8}
          autoComplete="new-password"
          hint="At least 8 characters."
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          errorMessage={error ?? undefined}
        />
        <Button type="submit" className="w-full rounded-full" loading={isSubmitting}>
          Create account
        </Button>
      </form>
    </AuthCard>
  );
}