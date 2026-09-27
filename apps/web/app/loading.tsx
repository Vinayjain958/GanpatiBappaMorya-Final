import { Loader2 } from "lucide-react";

export default function RootLoading() {
  return (
    <div className="flex flex-1 items-center justify-center py-32" role="status" aria-live="polite">
      <Loader2 className="size-6 animate-spin text-accent" aria-hidden="true" />
      <span className="sr-only">Loading LocaLens&hellip;</span>
    </div>
  );
}
