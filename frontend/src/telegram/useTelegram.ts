"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, del, get, post } from "./api";
import { applyEvent, emptyData, mergeMessages } from "./state";
import type { Allowlist, Approval, AskResult, Dialog, Message, Pairing, Signal, Status, Suggestion, TelegramData, TickReport } from "./types";

const REFRESH_MS = 30_000;
const EVENTS = ["message", "signal", "suggestion", "approval", "kanban_task"];

export interface TelegramActions {
  setMonitored(peer: number, on: boolean): void;
  setAllowed(peer: number, on: boolean): void;
  setPairing(source: number, target: number | null): void;
  approve(id: string): void;
  dismiss(id: string): void;
  retry(id: string): void;
  decide(id: string, approved: boolean): void;
  gather(): void;
  ask(question: string): Promise<AskResult | null>;
  clearError(): void;
}

export function useTelegram() {
  const [data, setData] = useState<TelegramData>(emptyData);
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState<ReadonlySet<string>>(new Set());
  const [live, setLive] = useState(false);
  const [lastTick, setLastTick] = useState<TickReport | null>(null);
  const busyRef = useRef(new Set<string>());

  const refresh = useCallback(async () => {
    try {
      const status = await get<Status>("status");
      const [monitored, pairings, allowlist, suggestions, approvals, signals, messages] = await Promise.all([
        get<number[]>("monitored"),
        get<Pairing[]>("pairings"),
        get<Allowlist>("allowlist"),
        get<Suggestion[]>("suggestions"),
        get<Approval[]>("approvals?status=pending"),
        get<Signal[]>("signals"),
        get<Message[]>("messages?limit=200"),
      ]);
      const dialogs = status.state === "authorized" ? await get<Dialog[]>("dialogs").catch(() => null) : [];
      setErrorCode(null);
      setData((prev) => ({
        status,
        monitored,
        pairings,
        allowlist,
        suggestions,
        approvals,
        signals,
        dialogs: dialogs ?? prev.dialogs,
        messages: mergeMessages(prev.messages, messages),
      }));
    } catch (e) {
      setErrorCode(e instanceof ApiError ? (e.code ?? "backend_down") : "backend_down");
    }
  }, []);

  useEffect(() => {
    const first = setTimeout(refresh, 0);
    const timer = setInterval(refresh, REFRESH_MS);
    return () => {
      clearTimeout(first);
      clearInterval(timer);
    };
  }, [refresh]);

  const connected = errorCode === null && data.status !== null;
  useEffect(() => {
    if (!connected) return;
    const source = new EventSource("/api/telegram/events");
    source.onopen = () => setLive(true);
    source.onerror = () => setLive(false);
    for (const name of EVENTS) {
      source.addEventListener(name, (event) => {
        const payload: unknown = JSON.parse((event as MessageEvent<string>).data);
        setData((prev) => applyEvent(prev, name, payload));
      });
    }
    return () => source.close();
  }, [connected]);

  /** One action per key at a time: a double click must not fire twice. */
  const run = useCallback(
    async (key: string, action: () => Promise<unknown>) => {
      if (busyRef.current.has(key)) return;
      busyRef.current.add(key);
      setBusy(new Set(busyRef.current));
      setActionError(null);
      try {
        await action();
      } catch (e) {
        const wait = e instanceof ApiError && e.retryAfterS ? ` (erneut in ${e.retryAfterS} s)` : "";
        setActionError(`${e instanceof Error ? e.message : "Aktion fehlgeschlagen"}${wait}`);
      } finally {
        busyRef.current.delete(key);
        setBusy(new Set(busyRef.current));
        await refresh();
      }
    },
    [refresh],
  );

  const actions: TelegramActions = {
    setMonitored: (peer, on) => void run(`monitor:${peer}`, () => (on ? post("monitored", { peer }) : del(`monitored/${peer}`))),
    setAllowed: (peer, on) => void run(`allow:${peer}`, () => (on ? post("allowlist", { peer }) : del(`allowlist/${peer}`))),
    setPairing: (source, target) =>
      void run(`pair:${source}`, () => (target === null ? del(`pairings/${source}`) : post("pairings", { source, target }))),
    approve: (id) => void run(`suggestion:${id}`, () => post(`suggestions/${encodeURIComponent(id)}/approve`)),
    dismiss: (id) => void run(`suggestion:${id}`, () => post(`suggestions/${encodeURIComponent(id)}/dismiss`)),
    retry: (id) => void run(`suggestion:${id}`, () => post(`suggestions/${encodeURIComponent(id)}/retry`)),
    decide: (id, approved) => void run(`approval:${id}`, () => post(`approvals/${encodeURIComponent(id)}/decide`, { approved })),
    gather: () =>
      void run("gather", async () => {
        setLastTick(await post<TickReport>("gather/run"));
      }),
    ask: async (question) => {
      setActionError(null);
      try {
        return await post<AskResult>("ask", { question });
      } catch (e) {
        setActionError(e instanceof Error ? e.message : "Frage fehlgeschlagen");
        return null;
      }
    },
    clearError: () => setActionError(null),
  };

  return { data, errorCode, actionError, busy, live, lastTick, actions };
}
