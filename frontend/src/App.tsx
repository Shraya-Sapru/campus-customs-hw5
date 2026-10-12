import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { AgentEvent, AgentName, PendingApproval, Ticket } from "./types";
import {
  ApiError,
  approvePayment,
  fetchBalance,
  fetchEvents,
  fetchTickets,
  resetDatabase,
  runTicket,
} from "./api";
import {
  APPROVER_NAME_STORAGE_KEY,
  HEARTBEAT_INTERVAL_MS,
  LIVE_POLL_INTERVAL_MS,
} from "./constants";
import { useInterval } from "./hooks/useInterval";
import { Header } from "./components/Header";
import { TicketColumn } from "./components/TicketColumn";
import { AgentDesk } from "./components/AgentDesk";
import { CashPanel } from "./components/CashPanel";
import { ApprovalsPanel } from "./components/ApprovalsPanel";

function deriveTicketSummaries(events: AgentEvent[]): Record<number, Partial<Record<AgentName, string>>> {
  const map: Record<number, Partial<Record<AgentName, string>>> = {};
  for (const e of events) {
    if (e.step === "result" && e.ticket_id !== null && e.agent && e.summary) {
      map[e.ticket_id] = { ...map[e.ticket_id], [e.agent]: e.summary };
    }
  }
  return map;
}

function deriveLatestByAgent(events: AgentEvent[]): Partial<Record<AgentName, string>> {
  const map: Partial<Record<AgentName, string>> = {};
  for (const e of events) {
    if (!e.agent) continue;
    if (e.step === "tool_call") map[e.agent] = `used ${e.tool ?? "a tool"}`;
    else if (e.step === "delegation") map[e.agent] = "delegating…";
    else if (e.step === "model_call") map[e.agent] = "thinking…";
    else if (e.step === "result") map[e.agent] = e.summary ?? "done";
  }
  return map;
}

/** The audit log's `summary` field is a human-readable truncated string, not a
 * guaranteed-complete JSON document - a long `reason` from Accounting can push a
 * propose_payment result past the truncation limit, landing mid-object. A strict
 * JSON.parse on that fails outright even though the `id` field near the start of the
 * object is still intact, so pull it out with a tolerant regex instead. Everything
 * else about the proposal is read from `arguments`, which is the raw tool-call
 * arguments and is never truncated. */
function extractProposalId(summary: string): number | null {
  const match = summary.match(/"id"\s*:\s*(\d+)/);
  return match ? Number(match[1]) : null;
}

function derivePendingApprovals(events: AgentEvent[], dismissed: Set<number>): PendingApproval[] {
  const byId = new Map<number, PendingApproval>();
  const approvedIds = new Set<number>();
  for (const e of events) {
    if (e.step !== "tool_call" || !e.summary) continue;
    // A human approving a payment isn't an agent tool call, but backend/main.py's
    // approve route records it as one anyway, specifically so a fresh page load can
    // tell a proposal was already approved - without this, approving does nothing
    // agents/events can see, so the card would keep reappearing on every reload.
    if (e.tool === "approve_payment") {
      const proposalId = (e.arguments?.proposal_id as number | undefined) ?? null;
      if (proposalId !== null) approvedIds.add(proposalId);
      continue;
    }
    if (e.tool !== "propose_payment") continue;
    const id = extractProposalId(e.summary);
    if (id === null) continue;
    const args = e.arguments ?? {};
    byId.set(id, {
      id,
      kind: (args.kind as string | undefined) ?? "invoice",
      refId: (args.ref_id as number | undefined) ?? 0,
      amount: (args.amount as number | undefined) ?? 0,
      account: (args.account as string | undefined) ?? "checking",
      reason: (args.reason as string | null | undefined) ?? null,
      proposedBy: (args.proposed_by as string | undefined) ?? "accounting-agent",
      ticketId: e.ticket_id,
    });
  }
  return [...byId.values()].filter((p) => !dismissed.has(p.id) && !approvedIds.has(p.id));
}

export default function App() {
  const [tickets, setTickets] = useState<Ticket[] | null>(null);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [balance, setBalance] = useState<number | null>(null);
  const [displayedBalance, setDisplayedBalance] = useState<number | null>(null);
  const [droppingBalance, setDroppingBalance] = useState(false);
  const [runningTicketIds, setRunningTicketIds] = useState<Set<number>>(new Set());
  const [selectedTicketId, setSelectedTicketId] = useState<number | null>(null);
  const [dismissedApprovalIds, setDismissedApprovalIds] = useState<Set<number>>(new Set());
  const [offline, setOffline] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [approverName, setApproverName] = useState(
    () => localStorage.getItem(APPROVER_NAME_STORAGE_KEY) ?? "",
  );

  const lastSeenTimestamp = useRef<string | null>(null);
  const balanceRef = useRef<number | null>(null);

  useEffect(() => {
    localStorage.setItem(APPROVER_NAME_STORAGE_KEY, approverName);
  }, [approverName]);

  const refreshTickets = useCallback(async () => {
    try {
      const { tickets: fresh } = await fetchTickets();
      setTickets(fresh);
      setOffline(false);
      setRunningTicketIds((prev) => {
        const next = new Set(prev);
        for (const t of fresh) if (t.resolved) next.delete(t.id);
        return next;
      });
    } catch (err) {
      if (err instanceof ApiError && err.status === undefined) setOffline(true);
    }
  }, []);

  const refreshBalance = useCallback(async () => {
    try {
      const fresh = await fetchBalance();
      setBalance(fresh.balance);
      setOffline(false);
    } catch (err) {
      if (err instanceof ApiError && err.status === undefined) setOffline(true);
    }
  }, []);

  const pollEvents = useCallback(async () => {
    try {
      const { events: batch } = await fetchEvents(100);
      setOffline(false);
      // backend returns newest-first; reverse to oldest-first for accumulation
      const oldestFirst = [...batch].reverse();
      const fresh = lastSeenTimestamp.current
        ? oldestFirst.filter((e) => e.timestamp > lastSeenTimestamp.current!)
        : oldestFirst;
      if (fresh.length > 0) {
        lastSeenTimestamp.current = fresh[fresh.length - 1].timestamp;
        setEvents((prev) => [...prev, ...fresh]);
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === undefined) setOffline(true);
    }
  }, []);

  // Initial load.
  useEffect(() => {
    void refreshTickets();
    void refreshBalance();
    void pollEvents();
  }, [refreshTickets, refreshBalance, pollEvents]);

  const isAnyRunning = runningTicketIds.size > 0;

  // Heartbeat: always on, keeps the board fresh and doubles as offline detection.
  useInterval(() => {
    void refreshTickets();
    if (!isAnyRunning) void refreshBalance();
  }, HEARTBEAT_INTERVAL_MS);

  // Live poll: only while a ticket is actually running. Stops once it resolves.
  useInterval(() => {
    void pollEvents();
    void refreshTickets();
    void refreshBalance();
  }, isAnyRunning ? LIVE_POLL_INTERVAL_MS : null);

  // Animate the displayed balance toward the real one whenever it changes.
  useEffect(() => {
    if (balance === null) return;
    const from = balanceRef.current ?? balance;
    const to = balance;
    balanceRef.current = balance;
    if (from === to) {
      setDisplayedBalance(to);
      return;
    }
    setDroppingBalance(to < from);
    const duration = 800;
    const start = performance.now();
    let raf = 0;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      setDisplayedBalance(from + (to - from) * eased);
      if (t < 1) raf = requestAnimationFrame(tick);
      else setDroppingBalance(false);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [balance]);

  const ticketSummaries = useMemo(() => deriveTicketSummaries(events), [events]);
  const latestByAgent = useMemo(() => deriveLatestByAgent(events), [events]);
  const pendingApprovals = useMemo(
    () => derivePendingApprovals(events, dismissedApprovalIds),
    [events, dismissedApprovalIds],
  );

  const ticketEvents = useMemo(
    () =>
      selectedTicketId === null
        ? []
        : [...events].filter((e) => e.ticket_id === selectedTicketId).slice(-20).reverse(),
    [events, selectedTicketId],
  );

  const lastEvent = events.length > 0 ? events[events.length - 1] : null;
  const activeAgent = isAnyRunning ? (lastEvent?.agent ?? null) : null;

  async function handleRun(ticketId: number) {
    setActionError(null);
    try {
      await runTicket(ticketId);
      setRunningTicketIds((prev) => new Set(prev).add(ticketId));
      setSelectedTicketId(ticketId);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Couldn't start the run.");
    }
  }

  async function handleApprove(proposalId: number) {
    setActionError(null);
    if (!approverName.trim()) {
      setActionError("Enter your name before approving a payment.");
      return;
    }
    try {
      const result = await approvePayment(proposalId, approverName.trim());
      if (!result.approved) {
        setActionError(result.message ?? "The backend refused that approval.");
        return;
      }
      setDismissedApprovalIds((prev) => new Set(prev).add(proposalId));
      await refreshBalance();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Approval failed.");
    }
  }

  function handleReject(proposalId: number) {
    setDismissedApprovalIds((prev) => new Set(prev).add(proposalId));
  }

  async function handleReset() {
    const confirmed = window.confirm(
      "Reset the working database to its original values? This clears every ticket's progress, pending proposals, and drafts.",
    );
    if (!confirmed) return;
    setActionError(null);
    try {
      await resetDatabase();
      setEvents([]);
      setDismissedApprovalIds(new Set());
      setRunningTicketIds(new Set());
      setSelectedTicketId(null);
      lastSeenTimestamp.current = null;
      await Promise.all([refreshTickets(), refreshBalance()]);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Reset failed.");
    }
  }

  return (
    <div className="app-shell">
      <Header
        offline={offline}
        live={isAnyRunning}
        approverName={approverName}
        onApproverNameChange={setApproverName}
        onReset={handleReset}
      />

      {offline && (
        <div className="banner banner--offline">
          {"The desk is quiet — can't reach the backend at localhost:8000. Is uvicorn running?"}
        </div>
      )}
      {actionError && (
        <div className="banner banner--error" onClick={() => setActionError(null)}>
          {actionError} <span className="banner__dismiss">(click to dismiss)</span>
        </div>
      )}

      <main className="app-columns">
        <TicketColumn
          tickets={tickets}
          selectedTicketId={selectedTicketId}
          runningTicketIds={runningTicketIds}
          ticketSummaries={ticketSummaries}
          onSelect={setSelectedTicketId}
          onRun={handleRun}
        />

        <AgentDesk
          activeAgent={activeAgent}
          latestByAgent={latestByAgent}
          recentEvents={ticketEvents}
          selectedTicketId={selectedTicketId}
        />

        <section className="column column--side">
          <CashPanel displayedBalance={displayedBalance} dropping={droppingBalance} />
          <ApprovalsPanel
            approvals={pendingApprovals}
            balance={balance}
            approverName={approverName}
            onApprove={handleApprove}
            onReject={handleReject}
          />
        </section>
      </main>
    </div>
  );
}
