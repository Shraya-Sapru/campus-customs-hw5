import type { CSSProperties } from "react";
import type { AgentName } from "../types";
import { AGENT_META } from "../constants";

interface Props {
  name: AgentName;
  active: boolean;
  latest: string | undefined;
}

export function AgentCard({ name, active, latest }: Props) {
  const meta = AGENT_META[name];
  return (
    <div
      className={"agent-card" + (active ? " agent-card--active" : " agent-card--idle")}
      style={{ "--agent-color": meta.color } as CSSProperties}
    >
      <div className="agent-card__icon">{meta.icon}</div>
      <div className="agent-card__label">{meta.label}</div>
      <div className="agent-card__latest">{latest ?? "Idle"}</div>
      {active && <span className="agent-card__pulse" aria-hidden="true" />}
    </div>
  );
}
