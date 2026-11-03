"use client";

import React from "react";
import {
  ApprovalsPanel,
  AskPanel,
  ChatsPanel,
  ErrorBanner,
  FeedPanel,
  GatherPanel,
  SetupHint,
  SignalsPanel,
  StatusBar,
  SuggestionsPanel,
} from "./Panels";
import { useTelegram } from "./useTelegram";

export const TelegramConsole: React.FC = () => {
  const { data, errorCode, actionError, busy, live, lastTick, actions } = useTelegram();
  const ready = errorCode === null && data.status !== null;
  return (
    <main className="min-h-screen overflow-x-hidden bg-[#090b12] px-4 py-5 text-slate-200 sm:px-6">
      <div className="mx-auto flex max-w-[1500px] flex-col gap-4">
        <header className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">NIO</p>
            <h1 className="text-xl font-semibold text-white">Telegram</h1>
          </div>
          <StatusBar status={data.status} errorCode={errorCode} live={live} />
        </header>

        <ErrorBanner message={actionError} onClose={actions.clearError} />
        <SetupHint status={data.status} errorCode={errorCode} />

        {ready && (
          <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-[minmax(0,320px)_minmax(0,1fr)_minmax(0,360px)]">
            <div className="flex min-w-0 flex-col gap-4">
              <ChatsPanel data={data} busy={busy} actions={actions} />
              <GatherPanel status={data.status} lastTick={lastTick} busy={busy} actions={actions} />
            </div>
            <div className="flex min-w-0 flex-col gap-4">
              <AskPanel ask={actions.ask} />
              <FeedPanel messages={data.messages} dialogs={data.dialogs} monitored={data.monitored} />
            </div>
            <div className="flex min-w-0 flex-col gap-4">
              <SuggestionsPanel data={data} busy={busy} actions={actions} />
              <ApprovalsPanel approvals={data.approvals} busy={busy} actions={actions} />
              <SignalsPanel signals={data.signals} dialogs={data.dialogs} />
            </div>
          </div>
        )}
      </div>
    </main>
  );
};
