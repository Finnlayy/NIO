import type { DomainId, NetworkNode } from "@/data/network";

export type FeedStatus = "info" | "success" | "warn" | "error" | "trace";

export interface FeedEvent {
  id: number;
  timestamp: string;
  label: string;
  detail: string;
  status: FeedStatus;
}

export type RunState = "idle" | "running" | "success" | "error";

export interface SelectionResult {
  node: NetworkNode;
  preset?: {
    taskDescription: string;
    isComplexWorkflow: boolean;
    domainHint?: DomainId;
  };
}
