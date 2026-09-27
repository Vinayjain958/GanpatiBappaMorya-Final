import type { Metadata } from "next";
import Link from "next/link";
import { ArrowLeft, MapPin, PhoneCall, ShieldAlert } from "lucide-react";
import { PageContainer } from "@/components/layout/PageContainer";
import { Button } from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";

export const metadata: Metadata = { title: "Emergency" };

const localNumbers = [
  { label: "Police", number: "100" },
  { label: "Ambulance", number: "102" },
  { label: "Fire", number: "101" },
  { label: "Women's helpline", number: "1091" },
];

export default function EmergencyPage() {
  return (
    <PageContainer className="max-w-2xl space-y-6 py-8 sm:py-10">
      <Link
        href="/safety"
        className="inline-flex items-center gap-2 rounded-full px-3 py-2 text-sm font-medium text-ink-muted transition-colors hover:bg-surface-raised hover:text-ink"
      >
        <ArrowLeft className="size-4" aria-hidden="true" />
        Back to Safety Center
      </Link>

      <div className="rounded-3xl border border-danger/25 bg-danger-soft p-5 sm:p-6">
        <div className="flex items-start gap-3">
          <span className="flex size-11 shrink-0 items-center justify-center rounded-2xl bg-surface text-danger shadow-sm">
            <ShieldAlert className="size-5" aria-hidden="true" />
          </span>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-ink">Emergency</h1>
            <p className="mt-2 text-sm leading-6 text-ink-muted">
              If you are in immediate danger, call local emergency services directly. Live
              emergency integrations are not implemented yet in this build.
            </p>
          </div>
        </div>
      </div>

      <Card>
        <CardBody className="space-y-4 p-5 sm:p-6">
          <h2 className="text-base font-semibold text-ink">Local emergency numbers</h2>
          <ul className="space-y-2">
            {localNumbers.map((entry) => (
              <li
                key={entry.label}
                className="flex items-center justify-between gap-3 rounded-2xl bg-surface-raised px-4 py-3"
              >
                <span className="text-sm text-ink-muted">{entry.label}</span>
                <a
                  href={`tel:${entry.number}`}
                  className="inline-flex min-h-10 items-center gap-2 rounded-full bg-surface px-4 font-semibold text-ink shadow-sm transition-colors hover:bg-accent-soft hover:text-accent"
                >
                  <PhoneCall className="size-4 text-danger" aria-hidden="true" />
                  {entry.number}
                </a>
              </li>
            ))}
          </ul>
        </CardBody>
      </Card>

      <Card>
        <CardBody className="space-y-4 p-5 sm:p-6">
          <h2 className="flex items-center gap-2 text-base font-semibold text-ink">
            <span className="flex size-9 items-center justify-center rounded-xl bg-accent-soft text-accent">
              <MapPin className="size-4" aria-hidden="true" />
            </span>
            Your location
          </h2>
          <p className="text-sm leading-6 text-ink-muted">
            Location sharing with emergency contacts is not yet implemented.
          </p>
          <Button variant="outline" disabled title="Not yet implemented" className="rounded-full">
            Share my location
          </Button>
        </CardBody>
      </Card>
    </PageContainer>
  );
}