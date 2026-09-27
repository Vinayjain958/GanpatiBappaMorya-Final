"use client";

import { useEffect } from "react";
import Lenis from "lenis";

/**
 * Site-wide fluid/inertial scrolling (mount once in AppShell). Replaces
 * native discrete wheel/trackpad scrolling with Lenis's eased momentum
 * scroll — purely a feel/motion enhancement, no layout or functional
 * change to any page.
 *
 * Respects prefers-reduced-motion: Lenis is never instantiated at all in
 * that case, so scrolling stays native/instant rather than merely
 * shortening the animation (matching how the rest of this app's motion
 * treatments handle reduced motion — see globals.css).
 */
export function SmoothScroll() {
  useEffect(() => {
    const motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (motionQuery.matches) return;

    const lenis = new Lenis({
      duration: 1.1,
      easing: (t: number) => Math.min(1, 1 - Math.pow(2, -10 * t)),
      smoothWheel: true,
    });

    let frameId: number;
    function raf(time: number) {
      lenis.raf(time);
      frameId = requestAnimationFrame(raf);
    }
    frameId = requestAnimationFrame(raf);

    return () => {
      cancelAnimationFrame(frameId);
      lenis.destroy();
    };
  }, []);

  return null;
}
