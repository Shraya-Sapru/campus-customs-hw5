import type { AgentName } from "./types";

export interface AgentMeta {
  label: string;
  icon: string;
  color: string;
}

export const AGENT_ORDER: AgentName[] = [
  "boss",
  "inventory",
  "accounting",
  "facilities",
  "customer_service",
];

export const AGENT_META: Record<AgentName, AgentMeta> = {
  boss: { label: "Boss", icon: "\u{1F451}", color: "#e8c468" },
  inventory: { label: "Inventory", icon: "\u{1F4E6}", color: "#4fd1c5" },
  accounting: { label: "Accounting", icon: "\u{1F4B0}", color: "#6fcf7a" },
  facilities: { label: "Facilities", icon: "\u{1F3E2}", color: "#e2984e" },
  customer_service: { label: "Customer Service", icon: "\u{1F4AC}", color: "#8a9dfe" },
};

export const HEARTBEAT_INTERVAL_MS = 5000;
export const LIVE_POLL_INTERVAL_MS = 1500;
export const APPROVER_NAME_STORAGE_KEY = "campus-customs-approver-name";
