"use client";

import { useState } from "react";
import { Download } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { getOvertureCatalogAddon, getOvertureSourceDataset } from "@/lib/api/experiences";
import { downloadJsonFile } from "@/lib/utils/downloadJson";

export function SourceDataDownloadButton() {
  const [loading, setLoading] = useState<"snapshot" | "catalog" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleDownload(kind: "snapshot" | "catalog") {
    setLoading(kind);
    setError(null);
    try {
      const dataset = kind === "catalog"
        ? await getOvertureCatalogAddon()
        : await getOvertureSourceDataset();
      const version = dataset.snapshot_version.replace(/[^a-z0-9.-]+/gi, "-");
      const label = kind === "catalog" ? "mumbai-catalog" : "places-snapshot";
      downloadJsonFile(`localens-overture-${label}-${version}.json`, dataset);
    } catch {
      setError("The Overture data could not be downloaded.");
    } finally {
      setLoading(null);
    }
  }

  return (
    <div className="flex flex-col items-start gap-1">
      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => void handleDownload("snapshot")}
          loading={loading === "snapshot"}
          disabled={loading !== null}
          aria-label="Download source-derived Overture place data as JSON"
        >
          <Download className="size-4" aria-hidden="true" />
          Download source data
        </Button>
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => void handleDownload("catalog")}
          loading={loading === "catalog"}
          disabled={loading !== null}
          aria-label="Download the expanded non-synthetic Mumbai catalog snapshot as JSON"
        >
          <Download className="size-4" aria-hidden="true" />
          Full Mumbai catalog
        </Button>
      </div>
      {error ? <span className="text-xs text-danger" role="status">{error}</span> : null}
    </div>
  );
}
