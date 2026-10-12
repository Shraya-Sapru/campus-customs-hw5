import type { AgentEvent, AgentName } from "../types";
import { AGENT_ORDER } from "../constants";
import { AgentCard } from "./AgentCard";
import { ActivityFeed } from "./ActivityFeed";

interface Props {
  activeAgent: AgentName | null;
  latestByAgent: Partial<Record<AgentName, string>>;
  recentEvents: AgentEvent[];
  selectedTicketId: number | null;
}

export function AgentDesk({ activeAgent, latestByAgent, recentEvents, selectedTicketId }: Props) {
  return (
    <section className="column column--desk">
      <h2 className="column__title">The Desk</h2>
      <div className="agent-grid">
        {AGENT_ORDER.map((name) => (
          <AgentCard
            key={name}
            name={name}
            active={activeAgent === name}
            latest={latestByAgent[name]}
          />
        ))}
      </div>

      <h3 className="column__subtitle">
        Activity{selectedTicketId !== null ? ` — ticket #${selectedTicketId}` : ""}
      </h3>
      <ActivityFeed events={recentEvents} selectedTicketId={selectedTicketId} />
    </section>
  );
}
