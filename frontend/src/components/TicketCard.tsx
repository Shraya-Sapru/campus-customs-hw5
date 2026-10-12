import type { AgentName, Ticket } from "../types";
import { AGENT_META, AGENT_ORDER } from "../constants";

interface Props {
  ticket: Ticket;
  selected: boolean;
  running: boolean;
  summaries: Partial<Record<AgentName, string>> | undefined;
  onSelect: () => void;
  onRun: () => void;
}

export function TicketCard({ ticket, selected, running, summaries, onSelect, onRun }: Props) {
  // A ticket can be in three states, not two: still open, genuinely resolved (green
  // check/stamp), or resolved-by-Boss-but-still-awaiting-a-human-decision (amber badge).
  // "resolved" alone used to decide both whether to show the stamp AND whether to hide
  // the run button - that's wrong for the "awaiting" state, which also shouldn't be
  // re-runnable even though it isn't truly resolved. Gate the button on status itself.
  const isOpen = ticket.status === "open";
  const needsHumanDecision = !isOpen && !ticket.resolved;
  const canRun = isOpen && !running;

  return (
    <div
      className={
        "ticket-card" +
        (ticket.resolved ? " ticket-card--resolved" : "") +
        (needsHumanDecision ? " ticket-card--awaiting" : "") +
        (selected ? " ticket-card--selected" : "") +
        (running ? " ticket-card--running" : "")
      }
      onClick={onSelect}
    >
      {ticket.resolved && <div className="ticket-stamp">RESOLVED</div>}

      <div className="ticket-card__header">
        <span className="ticket-card__id">#{ticket.id}</span>
        <span className="ticket-card__type">{ticket.type.replace(/_/g, " ")}</span>
        {ticket.resolved && <span className="ticket-card__check">&#10003;</span>}
      </div>

      <div className="ticket-card__subject">{ticket.subject}</div>
      <div className="ticket-card__requester">from {ticket.requester}</div>

      {ticket.sku && (
        <div className="ticket-card__detail">
          {ticket.qty}&times; {ticket.sku}
          {ticket.size ? ` (${ticket.size})` : ""}
        </div>
      )}

      <div className="ticket-card__status">
        status: <span className={`status-pill status-pill--${ticket.status}`}>{ticket.status}</span>
      </div>

      {needsHumanDecision && (
        <div className="ticket-badge ticket-badge--awaiting">{"⏳ Needs a human decision"}</div>
      )}

      {isOpen && (
        <button
          className="btn btn--gold"
          disabled={!canRun}
          onClick={(e) => {
            e.stopPropagation();
            onRun();
          }}
        >
          {running ? "Running…" : "Start agent team"}
        </button>
      )}

      {!isOpen && summaries && (
        <details className="ticket-card__summaries" onClick={(e) => e.stopPropagation()}>
          <summary>What each agent did</summary>
          <ul>
            {AGENT_ORDER.filter((name) => summaries[name]).map((name) => (
              <li key={name}>
                <span className="agent-chip" style={{ color: AGENT_META[name].color }}>
                  {AGENT_META[name].icon} {AGENT_META[name].label}
                </span>
                <p>{summaries[name]}</p>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
