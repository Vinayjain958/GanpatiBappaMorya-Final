"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "@/lib/auth/AuthContext";
import { listSavedExperiences } from "@/lib/api/experiences";
import { recordExperienceSave } from "@/lib/api/feedback";

const EMPTY_SET: Set<string> = new Set();

export function useSavedExperienceIds() {
  const { isAuthenticated, user } = useAuth();
  const userId = isAuthenticated && user?.role === "traveler" ? user.id : null;
  const [savedIds, setSavedIds] = useState<Set<string>>(EMPTY_SET);
  const [loadedFor, setLoadedFor] = useState<string | null>(null);
  const savedIdsRef = useRef<Set<string>>(EMPTY_SET);

  useEffect(() => {
    const controller = new AbortController();
    savedIdsRef.current = EMPTY_SET;
    setSavedIds(EMPTY_SET);
    setLoadedFor(userId);

    if (!userId) return () => controller.abort();

    listSavedExperiences(controller.signal)
      .then((response) => {
        if (controller.signal.aborted) return;
        const next = new Set(response.items.map((item) => item.id));
        savedIdsRef.current = next;
        setSavedIds(next);
      })
      .catch(() => {
        // Saved-state is an enhancement; discovery remains usable if it is unavailable.
      });

    return () => controller.abort();
  }, [userId]);

  const toggleSaved = useCallback(async (experienceId: string, saved: boolean) => {
    if (!userId) return;
    const wasSaved = savedIdsRef.current.has(experienceId);
    if (wasSaved === saved) return;

    const optimistic = new Set(savedIdsRef.current);
    if (saved) optimistic.add(experienceId);
    else optimistic.delete(experienceId);
    savedIdsRef.current = optimistic;
    setSavedIds(optimistic);

    try {
      await recordExperienceSave(experienceId, saved);
    } catch (error) {
      const rolledBack = new Set(savedIdsRef.current);
      if (wasSaved) rolledBack.add(experienceId);
      else rolledBack.delete(experienceId);
      savedIdsRef.current = rolledBack;
      setSavedIds(rolledBack);
      throw error;
    }
  }, [userId]);

  return {
    savedIds: userId && loadedFor === userId ? savedIds : EMPTY_SET,
    toggleSaved,
  };
}
