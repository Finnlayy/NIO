"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { checkBackendHealth, fetchCodyComms, fetchCodySupervisor } from "@/lib/nio-client";
import type { FormattedInterAgentLine } from "@/lib/manifest-types";
import { filterByScope } from "@/components/comms/comms-filter";

const POLL_MS = 10_000;
const MAX_LINES = 8;

export function useActivityFeed() {
  const [lines, setLines] = useState<FormattedInterAgentLine[]>([]);
  const [apiLive, setApiLive] = useState(false);
  const [loading, setLoading] = useState(true);
  const lastMessageIdRef = useRef<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const healthy = await checkBackendHealth();
      setApiLive(healthy);
      if (!healthy) {
        setLines([]);
        return;
      }

      const [comms, sup] = await Promise.all([
        fetchCodyComms({ filter: "relevant", limit: MAX_LINES }).catch(() => null),
        fetchCodySupervisor().catch(() => null),
      ]);

      let incoming: FormattedInterAgentLine[] = [];
      if (comms?.timeline?.length) {
        incoming = comms.timeline;
        if (comms.latestMessageId) {
          lastMessageIdRef.current = comms.latestMessageId;
        }
      } else if (sup?.interAgentTimeline?.length) {
        incoming = sup.interAgentTimeline;
      }

      const relevant = filterByScope(incoming, "relevant")
        .sort((a, b) => b.timestamp.localeCompare(a.timestamp))
        .slice(0, MAX_LINES);

      setLines(relevant);
    } catch {
      setApiLive(false);
      setLines([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const id = window.setInterval(() => void refresh(), POLL_MS);
    return () => window.clearInterval(id);
  }, [refresh]);

  return { lines, apiLive, loading, refresh };
}
