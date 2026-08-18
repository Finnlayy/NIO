"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { checkBackendHealth, fetchCodyComms, fetchCodySupervisor } from "@/lib/nio-client";
import type { CommsFilterScope, FormattedInterAgentLine } from "@/lib/manifest-types";
import {
  applyCommsFilters,
  countRelevantUnread,
  hasExtendedApiFields,
  type CommsChannelFilter,
  type CommsSeverityFilter,
} from "@/components/comms/comms-filter";

const POLL_MS = 5000;
const MAX_LINES = 100;
export const COMMS_READ_KEY = "nio-comms-read-at";
export const COMMS_PUBLISH_KEY = "cody-publish-to-bus";

export const COMMS_OPEN_EVENT = "comms:open";

export function openCommsView(): void {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(COMMS_OPEN_EVENT));
  }
}

export function loadPublishToBusPref(): boolean {
  try {
    return localStorage.getItem(COMMS_PUBLISH_KEY) === "true";
  } catch {
    return false;
  }
}

export function savePublishToBusPref(value: boolean): void {
  localStorage.setItem(COMMS_PUBLISH_KEY, value ? "true" : "false");
}

export function useCommsAudit(opts?: { enabled?: boolean }) {
  const enabled = opts?.enabled ?? true;
  const [lines, setLines] = useState<FormattedInterAgentLine[]>([]);
  const [filteredLines, setFilteredLines] = useState<FormattedInterAgentLine[]>([]);
  const [scope, setScope] = useState<CommsFilterScope>("relevant");
  const [channel, setChannel] = useState<CommsChannelFilter>("all");
  const [severity, setSeverity] = useState<CommsSeverityFilter>("all");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [apiLive, setApiLive] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [apiExtended, setApiExtended] = useState(false);
  const [newMessageIds, setNewMessageIds] = useState<Set<string>>(new Set());
  const [unreadRelevant, setUnreadRelevant] = useState(0);
  const [publishToBus, setPublishToBus] = useState(false);

  const lastMessageIdRef = useRef<string | null>(null);
  const seenRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    setPublishToBus(loadPublishToBusPref());
  }, []);

  const poll = useCallback(async () => {
    if (!enabled) return;
    setLoading(true);
    try {
      const healthy = await checkBackendHealth();
      setApiLive(healthy);
      if (!healthy) {
        setLines([]);
        return;
      }

      const [comms, sup] = await Promise.all([
        fetchCodyComms({
          since: scope === "relevant" ? undefined : lastMessageIdRef.current ?? undefined,
          filter: scope,
          limit: 50,
        }).catch(() => null),
        fetchCodySupervisor().catch(() => null),
      ]);

      let incoming: FormattedInterAgentLine[] = [];

      if (comms?.timeline?.length) {
        incoming = comms.timeline;
        if (comms.latestMessageId) {
          lastMessageIdRef.current = comms.latestMessageId;
        }
        setApiExtended(hasExtendedApiFields(comms.timeline) || comms.filter !== undefined);
      } else if (sup?.interAgentTimeline?.length) {
        incoming = sup.interAgentTimeline;
        setApiExtended(hasExtendedApiFields(sup.interAgentTimeline));
      }

      const freshIds = incoming.filter((l) => !seenRef.current.has(l.messageId)).map((l) => l.messageId);
      for (const line of incoming) {
        seenRef.current.add(line.messageId);
      }

      if (freshIds.length > 0) {
        setNewMessageIds((prev) => {
          const next = new Set(prev);
          for (const id of freshIds) next.add(id);
          return next;
        });
        setTimeout(() => {
          setNewMessageIds((prev) => {
            const next = new Set(prev);
            for (const id of freshIds) next.delete(id);
            return next;
          });
        }, 4000);
      }

      setLines((prev) => {
        const merged = [...incoming, ...prev];
        const byId = new Map(merged.map((l) => [l.messageId, l]));
        return Array.from(byId.values())
          .sort((a, b) => b.timestamp.localeCompare(a.timestamp))
          .slice(0, MAX_LINES);
      });

      const readAt = localStorage.getItem(COMMS_READ_KEY);
      const allForUnread = comms?.timeline?.length
        ? comms.timeline
        : (sup?.interAgentTimeline ?? []);
      setUnreadRelevant(countRelevantUnread(allForUnread, readAt));
      setLastUpdated(new Date());
    } catch {
      setApiLive(false);
    } finally {
      setLoading(false);
    }
  }, [enabled, scope]);

  useEffect(() => {
    setFilteredLines(applyCommsFilters(lines, { scope, channel, severity, search }));
  }, [lines, scope, channel, severity, search]);

  useEffect(() => {
    void poll();
    const id = setInterval(() => void poll(), POLL_MS);
    return () => clearInterval(id);
  }, [poll]);

  const markRead = useCallback(() => {
    localStorage.setItem(COMMS_READ_KEY, new Date().toISOString());
    setUnreadRelevant(0);
  }, []);

  const togglePublishToBus = useCallback((value: boolean) => {
    setPublishToBus(value);
    savePublishToBusPref(value);
  }, []);

  return {
    lines,
    filteredLines,
    scope,
    setScope,
    channel,
    setChannel,
    severity,
    setSeverity,
    search,
    setSearch,
    loading,
    apiLive,
    lastUpdated,
    apiExtended,
    newMessageIds,
    unreadRelevant,
    publishToBus,
    togglePublishToBus,
    refresh: poll,
    markRead,
  };
}
