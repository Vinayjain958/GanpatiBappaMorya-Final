"use client";

import { useEffect, useState } from "react";
import { getHealth, type HealthResponse } from "@/lib/api";

type Status = "idle" | "loading" | "success" | "error";

/** Thin hook around the one live API call in Phase 1 — GET /api/v1/health. */
export function useHealthCheck() {
  const [status, setStatus] = useState<Status>("loading");
  const [data, setData] = useState<HealthResponse | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    getHealth(controller.signal)
      .then((response) => {
        setData(response);
        setStatus("success");
      })
      .catch(() => {
        if (!controller.signal.aborted) setStatus("error");
      });

    return () => controller.abort();
  }, []);

  return { status, data };
}
