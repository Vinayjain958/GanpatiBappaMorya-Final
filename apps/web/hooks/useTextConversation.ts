"use client";

import { useCallback, useRef, useState } from "react";
import { createConversation, sendConversationMessage } from "@/lib/api/conversation";
import { travelerContextToDiscoveryPatch } from "@/lib/discovery/travelerContextToPatch";
import type { DiscoveryState } from "@/types/discovery";
import type { ConversationTurnResponse } from "@/types/conversation";

export type TextConversationStatus = "idle" | "loading" | "error";

/**
 * Text-mode conversational discovery: lazily creates a conversation
 * session on first message, sends each turn, and deterministically
 * merges the returned TravelerContext into the shared DiscoveryState
 * (the app controls this translation, never the model — see
 * lib/discovery/travelerContextToPatch.ts).
 */
export function useTextConversation(onDiscoveryPatch: (patch: Partial<DiscoveryState>) => void) {
  const [status, setStatus] = useState<TextConversationStatus>("idle");
  const [lastTurn, setLastTurn] = useState<ConversationTurnResponse | null>(null);
  const conversationIdRef = useRef<string | null>(null);

  const sendMessage = useCallback(
    async (text: string): Promise<ConversationTurnResponse | null> => {
      setStatus("loading");
      try {
        if (!conversationIdRef.current) {
          const conversation = await createConversation();
          conversationIdRef.current = conversation.id;
        }
        const turn = await sendConversationMessage(conversationIdRef.current, text);
        onDiscoveryPatch(travelerContextToDiscoveryPatch(turn.traveler_context));
        setLastTurn(turn);
        setStatus("idle");
        return turn;
      } catch {
        setStatus("error");
        return null;
      }
    },
    [onDiscoveryPatch],
  );

  return { sendMessage, status, lastTurn };
}
