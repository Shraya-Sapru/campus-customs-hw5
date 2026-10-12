"""Shared data types for the agent team.

SpecialistReply is the one structured output shape every agent (Boss and
all four specialists) returns, whether answering a delegated question or
making a final call on a ticket. Keeping one shape everywhere means the
delegation tool can always hand a caller back the same kind of object,
instead of five different per-role schemas.

TicketContext/RunBudget are the dependencies passed through every agent run
and every delegation, carrying the ticket id plus the delegation-depth and
delegation-count guards described in backend/agents.py.
"""

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

AgentName = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]


class SpecialistReply(BaseModel):
    """A structured answer from one agent, whether delegated-to or final."""

    summary: str = Field(description="Plain-language answer to the question or ticket.")
    key_facts: list[str] = Field(
        default_factory=list,
        description="Specific facts pulled from MCP tool calls that back up the summary "
        "(exact numbers, IDs, SKUs, dates) - not paraphrased, the real values.",
    )
    recommendation: str | None = Field(
        default=None,
        description="What should happen next, if anything. None if this is purely informational.",
    )
    needs_human_approval: bool = Field(
        default=False,
        description="True if acting on the recommendation would move money, change a lease, "
        "or otherwise needs a human to sign off before it happens.",
    )
    unresolved: bool = Field(
        default=False,
        description="True if this agent could not reach a confident answer with the tools and "
        "data available, and said so instead of guessing.",
    )


@dataclass
class RunBudget:
    """Shared, mutable delegation-call counter for one ticket's whole run tree."""

    max_delegations: int = 6
    used: int = 0

    def take(self) -> bool:
        if self.used >= self.max_delegations:
            return False
        self.used += 1
        return True


@dataclass
class TicketContext:
    """Dependencies passed to every agent run and copied (same budget, deeper depth) on delegation.

    agent_name is set by backend.runner.run_agent right before each run/delegation starts, so
    tool calls (backend/tools.py) and delegation (backend/agents.py) know which agent is
    currently running for audit-trail purposes - it isn't meant to be set by callers directly.
    """

    ticket_id: int | None
    depth: int = 0
    max_depth: int = 4
    budget: RunBudget = field(default_factory=RunBudget)
    agent_name: str | None = None
