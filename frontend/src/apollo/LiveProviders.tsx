"use client";

import { useCallback, useEffect, useState } from "react";
import type { ProviderStatus } from "../server/providers";
import { useApolloStore } from "./store";

/** Presence, measured availability and configuration are deliberately separate. */
export function LiveProviders() {
  const config = useApolloStore((s) => s.config);
  const apply = useApolloStore((s) => s.applyConfig);
  const [providers, setProviders] = useState<ProviderStatus[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const load = useCallback(async (probe = false) => {
    setBusy(true);
    setError(null);
    try {
      const response = await fetch("/api/apollo/providers", { method: probe ? "POST" : "GET", cache: "no-store" });
      const data = await response.json();
      if (Array.isArray(data.providers)) setProviders(data.providers);
      if (!response.ok) setError(data.error ?? "Kein Provider erfolgreich geprüft. Details siehe Statusliste.");
    } catch { setProviders([]); setError("Providerstatus nicht erreichbar."); }
    finally { setBusy(false); }
  }, []);
  useEffect(() => {
    void load();
    const timer = setInterval(() => void load(), 30_000);
    return () => clearInterval(timer);
  }, [load]);
  return (
    <section className="rounded-xl border border-white/10 bg-black/20 p-3" aria-label="Live-Providerstatus">
      <h3 className="text-sm font-semibold text-slate-100">Serverseitige Provider & Secrets</h3>
      <p className="mt-1 text-xs text-slate-400">Keine Keys im Browser. „ready“ gilt nur nach einer echten Completion und höchstens fünf Minuten. Vorhanden ≠ erreichbar.</p>
      <label className="mt-3 flex flex-wrap items-center gap-2 text-xs text-slate-300">
        Apollo-Provider
        <select aria-label="Apollo-Provider" className="rounded border border-white/15 bg-[#101725] p-2"
          value={config.freeLLMRouting.providerId ?? ""}
          onChange={(event) => apply({ ...config, freeLLMRouting: { ...config.freeLLMRouting, providerId: event.target.value || undefined, endpointUrl: "" } })}>
          <option value="">Serverstandard (NIO_LLM_PROVIDER)</option>
          {providers.map((provider) => <option key={provider.id} value={provider.id}>{provider.name} · {provider.status}</option>)}
        </select>
      </label>
      <ul className="mt-3 space-y-2">
        {providers.map((provider) => (
          <li key={provider.id} className="rounded border border-white/[0.07] p-2 text-xs" data-provider-id={provider.id}>
            <div className="flex flex-wrap justify-between gap-1">
              <strong className="text-slate-200">{provider.name}</strong>
              <span className={provider.status === "ready" ? "text-emerald-300" : provider.status === "unchecked" ? "text-amber-200" : "text-rose-300"}>{provider.status}</span>
            </div>
            <p className="mt-1 break-words text-slate-400">Credential: {provider.configured ? "vorhanden" : "fehlt"} · Modell: {provider.model || "nicht konfiguriert"}</p>
            {provider.checkedAt && <p className="mt-1 text-slate-400">Geprüft: {provider.checkedAt} · {provider.latencyMs} ms{provider.httpStatus ? ` · HTTP ${provider.httpStatus}` : ""}</p>}
          </li>
        ))}
      </ul>
      {error && <p role="alert" className="mt-2 text-xs text-rose-300">{error}</p>}
      <button type="button" disabled={busy} onClick={() => void load(true)} className="mt-3 rounded border border-cyan-400/30 px-3 py-2 text-xs text-cyan-200 disabled:opacity-50">
        {busy ? "Prüfung läuft…" : "Alle vorhandenen Provider live testen (max. 16 Tokens je Anfrage)"}
      </button>
      <p className="mt-2 text-[11px] text-slate-400">Ein Test kann Providerkosten verursachen. Ohne Secret/Modell keine Anfrage. Keine automatischen Retries oder simulierten Antworten.</p>
    </section>
  );
}
