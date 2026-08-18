"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  checkBackendHealth,
  fetchCodyComms,
  fetchCodyStats,
  fetchCodySupervisor,
} from "@/lib/nio-client";
import type {
  CodyStats,
  CodySupervisorStatus,
  FormattedInterAgentLine,
} from "@/lib/manifest-types";
import { deriveCodyMood } from "@/components/cody/cody-mood";

const POLL_MS = 5000;
const STORAGE_KEY = "cody-pet-anchor";
const DEFAULT_ANCHOR = { right: 24, bottom: 24 };

export interface CodyPetAnchor {
  right: number;
  bottom: number;
}

function loadAnchor(): CodyPetAnchor {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as CodyPetAnchor;
      if (Number.isFinite(parsed.right) && Number.isFinite(parsed.bottom)) {
        return parsed;
      }
    }
  } catch {
    /* ignore */
  }
  return DEFAULT_ANCHOR;
}

export function useCodyPet(opts?: { listening?: boolean; thinking?: boolean }) {
  const [stats, setStats] = useState<CodyStats | null>(null);
  const [supervisor, setSupervisor] = useState<CodySupervisorStatus | null>(null);
  const [commsLines, setCommsLines] = useState<FormattedInterAgentLine[]>([]);
  const [apiLive, setApiLive] = useState(false);
  const lastMessageIdRef = useRef<string | null>(null);
  const seenCommsRef = useRef<Set<string>>(new Set());

  const [anchor, setAnchor] = useState<CodyPetAnchor>(DEFAULT_ANCHOR);
  const [anchorReady, setAnchorReady] = useState(false);

  useEffect(() => {
    setAnchor(loadAnchor());
    setAnchorReady(true);
  }, []);

  const saveAnchor = useCallback((next: CodyPetAnchor) => {
    setAnchor(next);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  }, []);

  const poll = useCallback(async () => {
    const healthy = await checkBackendHealth();
    setApiLive(healthy);
    if (!healthy) return;

    try {
      const [s, sup] = await Promise.all([
        fetchCodyStats().catch(() => null),
        fetchCodySupervisor().catch(() => null),
      ]);
      setStats(s);
      setSupervisor(sup);

      const comms = await fetchCodyComms({ since: lastMessageIdRef.current ?? undefined });
      if (comms.latestMessageId) {
        lastMessageIdRef.current = comms.latestMessageId;
      }

      const newLines = comms.timeline.filter((l) => !seenCommsRef.current.has(l.messageId));
      for (const line of newLines) {
        seenCommsRef.current.add(line.messageId);
      }

      if (newLines.length > 0) {
        setCommsLines((prev) => {
          const merged = [...newLines, ...prev];
          const byId = new Map(merged.map((l) => [l.messageId, l]));
          return Array.from(byId.values()).slice(0, 30);
        });
      } else if (seenCommsRef.current.size === 0 && sup?.interAgentTimeline?.length) {
        for (const line of sup.interAgentTimeline) {
          seenCommsRef.current.add(line.messageId);
        }
        setCommsLines(sup.interAgentTimeline.slice(0, 20));
      }
    } catch {
      setApiLive(false);
    }
  }, []);

  useEffect(() => {
    void poll();
    const id = setInterval(() => void poll(), POLL_MS);
    return () => clearInterval(id);
  }, [poll]);

  const mood = deriveCodyMood(stats, supervisor, {
    listening: opts?.listening,
    thinking: opts?.thinking,
  });

  return {
    stats,
    supervisor,
    commsLines,
    mood,
    apiLive,
    anchor,
    anchorReady,
    saveAnchor,
    refresh: poll,
  };
}

export const CODY_OPEN_EVENT = "cody:open";

export function openCodyPet(): void {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(CODY_OPEN_EVENT));
  }
}
