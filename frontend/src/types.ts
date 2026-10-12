export interface Ticket {
  id: number;
  type: string;
  requester: string;
  subject: string;
  sku: string | null;
  size: string | null;
  qty: number | null;
  lease_id: number | null;
  invoice_id: number | null;
  status: string;
  notes: string | null;
  created_at: string;
  resolved: boolean;
}

export type AgentName =
  | "boss"
  | "inventory"
  | "accounting"
  | "facilities"
  | "customer_service";

export type EventStep = "model_call" | "tool_call" | "delegation" | "result";

export interface AgentEvent {
  timestamp: string;
  agent: AgentName | null;
  ticket_id: number | null;
  step: EventStep;
  tool?: string;
  arguments?: Record<string, unknown>;
  summary?: string;
  needs_human_approval?: boolean;
  unresolved?: boolean;
  error?: boolean;
}

export interface PendingApproval {
  id: number;
  kind: string;
  refId: number;
  amount: number;
  account: string;
  reason: string | null;
  proposedBy: string;
  ticketId: number | null;
}

export interface CashBalance {
  found: boolean;
  name: string;
  balance: number;
  date: string;
}

export interface ApprovePaymentResult {
  approved: boolean;
  message?: string;
  payment?: Record<string, unknown>;
  new_balance?: number;
}
