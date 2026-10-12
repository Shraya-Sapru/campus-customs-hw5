import type {
  AgentEvent,
  ApprovePaymentResult,
  CashBalance,
  Ticket,
} from "./types";

export const BASE_URL = "http://localhost:8000";

/** Thrown for every failure. `status` is set for HTTP error responses and left
 * undefined for network-level failures (backend unreachable), which is how
 * callers tell "the backend said no" apart from "the backend is offline". */
export class ApiError extends Error {
  status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...init,
    });
  } catch {
    throw new ApiError(`Can't reach the backend at ${BASE_URL}. Is uvicorn running?`);
  }

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      // body wasn't JSON - keep the status text
    }
    throw new ApiError(detail, response.status);
  }

  return (await response.json()) as T;
}

export function fetchTickets(): Promise<{ tickets: Ticket[] }> {
  return request("/tickets");
}

export function runTicket(ticketId: number): Promise<{ started: boolean; ticket_id: number }> {
  return request(`/tickets/${ticketId}/run`, { method: "POST" });
}

export function fetchEvents(limit = 100): Promise<{ events: AgentEvent[] }> {
  return request(`/events?limit=${limit}`);
}

export function approvePayment(
  proposalId: number,
  approvedBy: string,
): Promise<ApprovePaymentResult> {
  return request(`/payments/${proposalId}/approve`, {
    method: "POST",
    body: JSON.stringify({ approved_by: approvedBy }),
  });
}

export function fetchBalance(): Promise<CashBalance> {
  return request("/cash/balance");
}

export function resetDatabase(): Promise<{ reset: boolean }> {
  return request("/reset", { method: "POST" });
}
