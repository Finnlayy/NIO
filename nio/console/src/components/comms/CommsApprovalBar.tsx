"use client";

import { useState } from "react";
import type { FormattedInterAgentLine } from "@/lib/manifest-types";
import { postInterAgentApproval } from "@/lib/nio-client";

export default function CommsApprovalBar({
  line,
  onComplete,
}: {
  line: FormattedInterAgentLine;
  onComplete?: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<"approved" | "denied" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleAction = async (approved: boolean) => {
    setBusy(true);
    setError(null);
    try {
      await postInterAgentApproval({ messageId: line.messageId, approved });
      setDone(approved ? "approved" : "denied");
      onComplete?.();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Approval failed";
      setError(msg);
    } finally {
      setBusy(false);
    }
  };

  if (done) {
    return (
      <p className="mt-2 text-xs text-emerald-300">
        {done === "approved" ? "Approved" : "Denied"} — recorded on audit bus.
      </p>
    );
  }

  return (
    <div className="mt-3 flex flex-wrap items-center gap-2">
      <button
        type="button"
        disabled={busy}
        onClick={() => void handleAction(true)}
        className="text-xs px-3 py-1.5 rounded-lg bg-emerald-500/15 border border-emerald-500/30 text-emerald-200 hover:bg-emerald-500/25 disabled:opacity-50"
      >
        Approve
      </button>
      <button
        type="button"
        disabled={busy}
        onClick={() => void handleAction(false)}
        className="text-xs px-3 py-1.5 rounded-lg bg-rose-500/15 border border-rose-500/30 text-rose-200 hover:bg-rose-500/25 disabled:opacity-50"
      >
        Deny
      </button>
      {error ? (
        <span className="text-[11px] text-amber-300/90">
          {error.includes("404") || error.includes("failed")
            ? "Awaiting backend — see COMMS_AUDIT_API.md"
            : error}
        </span>
      ) : null}
    </div>
  );
}
