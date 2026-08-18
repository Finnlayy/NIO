"use client";

import { useCallback, useEffect, useState } from "react";
import { sendCodyChatMessage } from "@/lib/nio-client";
import type { CodyChatMessage } from "@/lib/manifest-types";
import { loadPublishToBusPref } from "@/hooks/useCommsAudit";

const SESSION_KEY = "cody-console-session";

function newId(): string {
  return `msg-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export function useCodyChat() {
  const [messages, setMessages] = useState<CodyChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string>("");

  useEffect(() => {
    const stored = sessionStorage.getItem(SESSION_KEY);
    if (stored) {
      setSessionId(stored);
      return;
    }
    const id = crypto.randomUUID();
    sessionStorage.setItem(SESSION_KEY, id);
    setSessionId(id);
  }, []);

  function sessionIdStorage(id: string) {
    sessionStorage.setItem(SESSION_KEY, id);
  }

  const appendSystemMessage = useCallback((content: string) => {
    setMessages((prev) => [
      ...prev,
      {
        id: newId(),
        role: "system",
        content,
        timestamp: new Date().toISOString(),
      },
    ]);
  }, []);

  const send = useCallback(
    async (text?: string) => {
      const message = (text ?? input).trim();
      if (!message || sending) return;

      setError(null);
      setInput("");
      setSending(true);

      const userMsg: CodyChatMessage = {
        id: newId(),
        role: "user",
        content: message,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, userMsg]);

      const history = [...messages, userMsg]
        .filter((m) => m.role === "user" || m.role === "assistant")
        .map((m) => ({ role: m.role as "user" | "assistant", content: m.content }));

      try {
        const res = await sendCodyChatMessage({
          message,
          sessionId: sessionId || undefined,
          history,
          publishToBus: loadPublishToBusPref(),
        });
        if (res.sessionId && res.sessionId !== sessionId) {
          setSessionId(res.sessionId);
          sessionIdStorage(res.sessionId);
        }
        setMessages((prev) => [
          ...prev,
          {
            id: newId(),
            role: "assistant",
            content: res.reply,
            timestamp: new Date().toISOString(),
          },
        ]);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Send failed");
      } finally {
        setSending(false);
      }
    },
    [input, messages, sending, sessionId],
  );

  return {
    messages,
    input,
    setInput,
    sending,
    error,
    send,
    appendSystemMessage,
  };
}
