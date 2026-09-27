import type { ReactNode } from "react";
import Link from "next/link";
import { Compass } from "lucide-react";
import { PageContainer } from "@/components/layout/PageContainer";
import { Card, CardBody } from "@/components/ui/Card";

export function AuthCard({
  title,
  description,
  children,
  footer,
}: {
  title: string;
  description: string;
  children: ReactNode;
  footer: ReactNode;
}) {
  return (
    <PageContainer className="flex min-h-[calc(100vh-4rem)] items-center justify-center py-10 sm:py-14">
      <div className="w-full max-w-md space-y-6">
        <Link
          href="/"
          className="mx-auto flex w-fit items-center gap-2 rounded-full px-4 py-2 font-semibold text-ink transition-colors hover:bg-surface-raised"
        >
          <span className="flex size-9 items-center justify-center rounded-xl bg-accent text-accent-ink shadow-sm">
            <Compass className="size-4.5" aria-hidden="true" />
          </span>
          LocaLens
        </Link>

        <Card className="rounded-3xl shadow-soft">
          <CardBody className="space-y-6 p-6 sm:p-8">
            <div className="space-y-2 text-center">
              <h1 className="text-2xl font-semibold tracking-tight text-ink">{title}</h1>
              <p className="text-sm leading-6 text-ink-muted">{description}</p>
            </div>
            {children}
          </CardBody>
        </Card>

        <p className="text-center text-sm text-ink-muted">{footer}</p>
      </div>
    </PageContainer>
  );
}