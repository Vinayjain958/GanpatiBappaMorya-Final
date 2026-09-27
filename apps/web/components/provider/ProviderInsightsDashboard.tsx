"use client";

import React, { useEffect, useState } from "react";
import { getProviderInsights, getProviderNotifications, markNotificationRead } from "@/lib/api/providers";
import type { ProviderInsightResponse, ProviderNotificationListResponse } from "@/types/provider-intelligence";
import { cn } from "@/lib/utils/cn";

export function ProviderInsightsDashboard() {
  const [insights, setInsights] = useState<ProviderInsightResponse | null>(null);
  const [notifications, setNotifications] = useState<ProviderNotificationListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [windowState, setWindowState] = useState("30d");

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const [resInsights, resNotif] = await Promise.all([
          getProviderInsights(windowState),
          getProviderNotifications(false)
        ]);
        setInsights(resInsights);
        setNotifications(resNotif);
      } catch (err) {
        console.error("Failed to load provider insights", err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [windowState]);

  if (loading) {
    return <div className="p-8 text-center text-ink-muted">Loading intelligence data...</div>;
  }

  if (!insights) {
    return <div className="p-8 text-center text-ink-muted">Failed to load data.</div>;
  }

  return (
    <div className="space-y-8">
      {/* Window Selector */}
      <div className="inline-flex gap-1 rounded-full border border-line bg-surface p-1">
        {["7d", "30d", "90d"].map(w => (
          <button
            key={w}
            onClick={() => setWindowState(w)}
            className={cn(
              "rounded-full px-4 py-1.5 text-sm font-medium transition-colors",
              windowState === w
                ? "bg-primary text-primary-ink"
                : "text-ink-muted hover:bg-surface-raised hover:text-ink",
            )}
          >
            {w}
          </button>
        ))}
      </div>

      {insights.provenance.has_synthetic_data && (
        <div className="rounded-2xl bg-warning-soft p-4 text-sm font-medium text-warning">
          Contains pre-aggregated synthetic data for demonstration.
        </div>
      )}

      {/* KPIs */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-2xl border border-line bg-surface p-4 shadow-soft">
          <div className="mb-1 text-sm font-medium text-ink-muted">Views</div>
          <div className="text-2xl font-semibold tracking-tight text-ink">{insights.kpis.views}</div>
        </div>
        <div className="rounded-2xl border border-line bg-surface p-4 shadow-soft">
          <div className="mb-1 text-sm font-medium text-ink-muted">Saves</div>
          <div className="text-2xl font-semibold tracking-tight text-ink">{insights.kpis.saves}</div>
        </div>
        <div className="rounded-2xl border border-line bg-surface p-4 shadow-soft">
          <div className="mb-1 text-sm font-medium text-ink-muted">Booking Requests</div>
          <div className="text-2xl font-semibold tracking-tight text-ink">{insights.kpis.booking_requests}</div>
        </div>
        <div className="rounded-2xl border border-line bg-surface p-4 shadow-soft">
          <div className="mb-1 text-sm font-medium text-ink-muted">Accepted</div>
          <div className="text-2xl font-semibold tracking-tight text-ink">{insights.kpis.accepted_bookings}</div>
        </div>
      </div>

      {/* Segments */}
      <div className="rounded-2xl border border-line bg-surface p-5 shadow-soft sm:p-6">
        <h3 className="mb-4 text-lg font-semibold tracking-tight text-ink">Traveler Interest Segments</h3>
        <div className="space-y-3">
          {insights.segments.map((seg, idx) => (
            <div key={idx} className="flex items-center justify-between rounded-xl bg-surface-raised px-3.5 py-2.5 text-sm">
              <span className="font-medium text-ink">
                {seg.label} <span className="text-xs text-ink-muted">({seg.segment_type})</span>
              </span>
              <span className="text-ink-muted">
                {seg.minimum_sample_met ? (
                  `${(seg.share! * 100).toFixed(1)}% (${seg.interactions} interactions)`
                ) : (
                  <span className="italic">Insufficient data</span>
                )}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Notifications */}
      {notifications && notifications.items.length > 0 && (
        <div className="rounded-2xl border border-line bg-surface p-5 shadow-soft sm:p-6">
          <h3 className="mb-4 text-lg font-semibold tracking-tight text-ink">Recent Match & Booking Alerts</h3>
          <div className="space-y-3">
            {notifications.items.map(n => (
              <div
                key={n.id}
                className={cn(
                  "flex items-start justify-between gap-3 rounded-2xl p-4",
                  n.is_read
                    ? "bg-surface-raised opacity-70"
                    : "border border-accent/20 bg-accent-soft",
                )}
              >
                <div className="min-w-0">
                  <h4 className="text-sm font-semibold text-ink">{n.title}</h4>
                  <p className="mt-1 text-sm text-ink-muted">{n.body}</p>
                  {n.segment_summary && (
                    <div className="mt-2 flex flex-wrap gap-2">
                      {n.segment_summary.map((s, idx) => (
                        <span key={idx} className="rounded-full bg-surface px-2.5 py-1 text-xs text-ink-muted">{s}</span>
                      ))}
                    </div>
                  )}
                  {n.booking_request_id && (
                    <div className="mt-2 font-mono text-xs text-ink-subtle">Ref: {n.booking_request_id}</div>
                  )}
                </div>
                {!n.is_read && (
                  <button
                    onClick={async () => {
                      await markNotificationRead(n.id);
                      setNotifications(prev => prev ? {
                        ...prev,
                        items: prev.items.map(x => x.id === n.id ? {...x, is_read: true} : x)
                      } : prev);
                    }}
                    className="shrink-0 text-xs font-medium text-accent hover:underline"
                  >
                    Mark Read
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
