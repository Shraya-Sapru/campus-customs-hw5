import type { AgentEvent } from "../types";
import { AGENT_META } from "../constants";

interface Props {
  events: AgentEvent[]; // newest first
  selectedTicketId: number | null;
}

function lineFor(event: AgentEvent): string {
  if (event.step === "delegation") {
    const target = (event.arguments?.target_agent as string | undefined) ?? "?";
    const fromLabel = event.agent ? AGENT_META[event.agent].label : "?";
    const toLabel =
      target in AGENT_META ? AGENT_META[target as keyof typeof AGENT_META].label : target;
    return `${fromLabel} → ${toLabel}`;
  }
  if (event.step === "tool_call") {
    return `called ${event.tool ?? "a tool"}`;
  }
  if (event.step === "model_call") {
    return "thinking…";
  }
  return event.summary ?? "finished";
}

export function ActivityFeed({ events, selectedTicketId }: Props) {
  if (selectedTicketId === null) {
    return <p className="muted">Select a ticket to watch the agents work.</p>;
  }
  if (events.length === 0) {
    return <p className="muted">No activity yet for ticket #{selectedTicketId}.</p>;
  }

  return (
    <ul className="activity-feed">
      {events.map((event, i) => {
        const meta = event.agent ? AGENT_META[event.agent] : undefined;
        return (
          <li
            key={`${event.timestamp}-${i}`}
            className={"activity-feed__item" + (event.error ? " activity-feed__item--error" : "")}
          >
            <span className="activity-feed__icon" style={{ color: meta?.color }}>
              {meta?.icon ?? "•"}
            </span>
            <span className="activity-feed__line">{lineFor(event)}</span>
          </li>
        );
      })}
    </ul>
  );
}
