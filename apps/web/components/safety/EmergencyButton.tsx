import Link from "next/link";
import { ShieldAlert } from "lucide-react";

export function EmergencyButton() {
  return (
    <Link
      href="/safety/emergency"
      className="flex min-h-16 items-center justify-center gap-2 rounded-2xl bg-danger px-5 py-4 text-base font-semibold text-white shadow-soft transition hover:brightness-105 active:brightness-95 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-danger"
    >
      <ShieldAlert className="size-5" aria-hidden="true" />
      Emergency help
    </Link>
  );
}