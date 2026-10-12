import type { AgentName, Ticket } from "../types";
import { TicketCard } from "./TicketCard";

interface Props {
  tickets: Ticket[] | null;
  selectedTicketId: number | null;
  runningTicketIds: Set<number>;
  ticketSummaries: Record<number, Partial<Record<AgentName, string>>>;
  onSelect: (ticketId: number) => void;
  onRun: (ticketId: number) => void;
}

export function TicketColumn({
  tickets,
  selectedTicketId,
  runningTicketIds,
  ticketSummaries,
  onSelect,
  onRun,
}: Props) {
  return (
    <section className="column column--tickets">
      <h2 className="column__title">Tickets</h2>
      {tickets === null && <p className="muted">{"Loading tickets…"}</p>}
      {tickets !== null && tickets.length === 0 && <p className="muted">No tickets.</p>}
      {tickets?.map((ticket) => (
        <TicketCard
          key={ticket.id}
          ticket={ticket}
          selected={ticket.id === selectedTicketId}
          running={runningTicketIds.has(ticket.id)}
          summaries={ticketSummaries[ticket.id]}
          onSelect={() => onSelect(ticket.id)}
          onRun={() => onRun(ticket.id)}
        />
      ))}
    </section>
  );
}
