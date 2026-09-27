"use client";

import type { ReactNode } from "react";
import { useEffect } from "react";
import { usePathname } from "next/navigation";
import { SiteHeader } from "@/components/layout/SiteHeader";
import { SiteFooter } from "@/components/layout/SiteFooter";
import { MobileTabBar } from "@/components/navigation/MobileTabBar";
import { TravelDoodles } from "@/components/common/TravelDoodles";
import { SmoothScroll } from "@/components/common/SmoothScroll";

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  // Ambient cursor-following glow behind the app shell — purely visual,
  // desktop mouse only (skipped for touch input), and disabled entirely
  // for anyone who prefers reduced motion (see globals.css's
  // .ambient-surface rules under @media (prefers-reduced-motion: reduce)).
  useEffect(() => {
    const surface = document.querySelector<HTMLElement>(".ambient-surface");
    const motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    let frame = 0;

    if (!surface || motionQuery.matches) return;

    function handlePointerMove(event: PointerEvent) {
      if (event.pointerType !== "mouse") return;
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        surface?.style.setProperty("--cursor-x", `${event.clientX}px`);
        surface?.style.setProperty("--cursor-y", `${event.clientY}px`);
      });
    }

    document.addEventListener("pointermove", handlePointerMove, { passive: true });
    return () => {
      cancelAnimationFrame(frame);
      document.removeEventListener("pointermove", handlePointerMove);
    };
  }, []);

  return (
    <div className="ambient-surface min-h-screen text-ink">
      <SmoothScroll />

      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[60] focus:rounded-lg focus:bg-primary focus:px-4 focus:py-2 focus:text-primary-ink"
      >
        Skip to main content
      </a>

      <SiteHeader />

      <div className="app-content flex min-h-screen min-w-0 flex-col lg:pl-60">
        <main
          id="main-content"
          className="min-w-0 flex-1 pb-20 md:pb-0"
        >
          {children}
        </main>

        <SiteFooter />
      </div>

      <MobileTabBar />

      {pathname === "/login" ? <TravelDoodles key="login" variant="auth" /> : null}
    </div>
  );
}
