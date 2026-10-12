"""The five-agent team: Boss, Inventory, Accounting, Facilities, Customer Service.

Each agent is a pydantic_ai.Agent built from the shared MODEL (backend/model.py), a role prompt
(backend/prompts/<name>.md), a subset of the MCP-backed tools in backend/tools.py, and the shared
delegate_to tool below. Full connectivity: any agent can delegate to any other agent (including
itself being delegated to), but two guards stop it from looping forever:

- max_depth on TicketContext caps how many delegation hops deep a single ticket can go.
- RunBudget.max_delegations caps the total number of delegate_to calls across the whole run,
  shared by reference across every delegation so the cap applies to the tree as a whole, not
  per-agent.

On top of that, whoever kicks off a ticket (see backend/smoke_test.py) should pass
`usage_limits=UsageLimits(request_limit=...)` to cap the total number of model requests spent on
one ticket - that's the "cap on model requests per ticket" backstop.
"""

from dataclasses import replace
from pathlib import Path

from pydantic_ai import Agent, RunContext

from . import audit, events, tools
from .model import MODEL
from .models import AgentName, SpecialistReply, TicketContext
from .runner import run_agent

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def _load_prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")


# Populated after all agents are constructed; delegate_to looks agents up here by name.
AGENT_REGISTRY: dict[AgentName, Agent[TicketContext, SpecialistReply]] = {}


async def delegate_to(ctx: RunContext[TicketContext], target_agent: AgentName, question: str) -> str:
    """Delegate a specific question to another agent (boss, inventory, accounting, facilities,
    or customer_service) and get back their structured reply as JSON. Include the ticket id and
    any numbers you already know in the question, so the other agent doesn't have to guess."""
    if target_agent == ctx.deps.agent_name:
        return (
            f"You are {ctx.deps.agent_name} - you can't delegate to yourself. Use your own "
            "tools, or delegate to a different agent if you genuinely need another specialist."
        )
    if target_agent not in AGENT_REGISTRY:
        return f"Unknown agent {target_agent!r}. Valid agents: {', '.join(AGENT_REGISTRY)}."
    if ctx.deps.depth >= ctx.deps.max_depth:
        return (
            f"Delegation depth limit ({ctx.deps.max_depth}) reached for this ticket - "
            "do not delegate further. Resolve with what you already know, or say you're unsure."
        )
    if not ctx.deps.budget.take():
        return (
            f"This ticket has used its delegation budget ({ctx.deps.budget.max_delegations} "
            "calls) - resolve with what you already know, or say you're unsure."
        )

    entry = audit.record(
        {
            "agent": ctx.deps.agent_name,
            "ticket_id": ctx.deps.ticket_id,
            "step": "delegation",
            "tool": "delegate_to",
            "arguments": {"target_agent": target_agent, "question": question},
            "summary": f"{ctx.deps.agent_name} -> {target_agent}",
        }
    )
    events.publish(entry)

    child_deps = replace(ctx.deps, depth=ctx.deps.depth + 1)
    result = await run_agent(target_agent, question, child_deps, usage=ctx.usage)
    return result.output.model_dump_json()


boss_agent = Agent(
    MODEL,
    name="boss",
    deps_type=TicketContext,
    output_type=SpecialistReply,
    instructions=_load_prompt("boss"),
    tools=[tools.get_today, tools.list_tickets, tools.get_ticket, tools.update_ticket_status, delegate_to],
)

inventory_agent = Agent(
    MODEL,
    name="inventory",
    deps_type=TicketContext,
    output_type=SpecialistReply,
    instructions=_load_prompt("inventory"),
    tools=[
        tools.get_today,
        tools.get_ticket,
        tools.get_inventory,
        tools.list_vendors,
        tools.get_invoice,
        tools.list_open_invoices_for_vendor,
        delegate_to,
    ],
)

accounting_agent = Agent(
    MODEL,
    name="accounting",
    deps_type=TicketContext,
    output_type=SpecialistReply,
    instructions=_load_prompt("accounting"),
    tools=[
        tools.get_today,
        tools.get_ticket,
        tools.get_cash_balance,
        tools.get_pricing,
        tools.get_invoice,
        tools.list_open_invoices_for_vendor,
        tools.list_payment_proposals,
        tools.propose_payment,
        delegate_to,
    ],
)

facilities_agent = Agent(
    MODEL,
    name="facilities",
    deps_type=TicketContext,
    output_type=SpecialistReply,
    instructions=_load_prompt("facilities"),
    tools=[tools.get_today, tools.get_ticket, tools.get_lease, delegate_to],
)

customer_service_agent = Agent(
    MODEL,
    name="customer_service",
    deps_type=TicketContext,
    output_type=SpecialistReply,
    instructions=_load_prompt("customer_service"),
    tools=[tools.get_today, tools.get_ticket, tools.save_draft, delegate_to],
)

AGENT_REGISTRY.update(
    {
        "boss": boss_agent,
        "inventory": inventory_agent,
        "accounting": accounting_agent,
        "facilities": facilities_agent,
        "customer_service": customer_service_agent,
    }
)
