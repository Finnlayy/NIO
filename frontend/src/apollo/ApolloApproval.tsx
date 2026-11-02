import React, { useState } from "react";
import { Badge, SectionCard, EmptyHint } from "./ui";

interface ApolloApprovalProps {
  intent?: {
    action: string;
    target: string;
    cost: number;
    dataOutflow: string;
  };
  onApprove: (pin: string) => void;
  onDeny: () => void;
  expirySeconds?: number;
}

export function ApolloApprovalCard({ intent, onApprove, onDeny, expirySeconds = 60 }: ApolloApprovalProps) {
  const [pin, setPin] = useState("");

  if (!intent) {
    return (
      <SectionCard title="Pending Approvals" hint="Actions requiring operator oversight">
        <EmptyHint>No actions currently pending approval.</EmptyHint>
      </SectionCard>
    );
  }

  const handleApprove = () => {
    onApprove(pin);
    setPin("");
  };

  return (
    <SectionCard title="Action Approval" hint="Requires explicit operator consent">
      <div className="flex flex-col gap-3 rounded border border-white/10 bg-white/[0.02] p-3 text-slate-300">
        <div className="flex justify-between items-center border-b border-white/10 pb-2">
          <Badge tone="amber">Action Required</Badge>
          <span className="text-[10px] text-slate-500">Expires in {expirySeconds}s</span>
        </div>

        <div className="grid grid-cols-2 gap-2 text-[12px]">
          <div><span className="text-slate-500 text-[10px] uppercase">Action</span><br/>{intent.action}</div>
          <div><span className="text-slate-500 text-[10px] uppercase">Target</span><br/>{intent.target}</div>
          <div><span className="text-slate-500 text-[10px] uppercase">Cost Estimate</span><br/>${intent.cost.toFixed(2)}</div>
          <div><span className="text-slate-500 text-[10px] uppercase">Data Outflow</span><br/>{intent.dataOutflow}</div>
        </div>

        <div className="mt-1">
          <label className="text-slate-500 text-[10px] uppercase mb-1 block">Operator PIN</label>
          <input
            type="password"
            value={pin}
            onChange={e => setPin(e.target.value)}
            className="w-full bg-black/40 border border-white/10 rounded px-2 py-1 text-sm text-slate-200 focus:outline-none focus:border-cyan-400/50"
            placeholder="****"
          />
        </div>

        <div className="flex gap-3 pt-2">
          <button
            onClick={handleApprove}
            className="flex-1 bg-cyan-400/20 text-cyan-300 border border-cyan-400/30 rounded py-1 text-[11px] font-medium tracking-wide uppercase hover:bg-cyan-400/30"
          >
            Approve
          </button>
          <button
            onClick={onDeny}
            className="flex-1 bg-rose-400/10 text-rose-300 border border-rose-400/30 rounded py-1 text-[11px] font-medium tracking-wide uppercase hover:bg-rose-400/20"
          >
            Deny
          </button>
        </div>
        <p className="text-[9px] text-slate-500 mt-1">Note: Voice commands cannot approve actions.</p>
      </div>
    </SectionCard>
  );
}
