"""The one entry point for actually invoking an agent.

Call run_agent(...) instead of Agent.run(...) directly - anywhere in this project, including
delegate_to in agents.py and backend/smoke_test.py - so every run shows up in
output/audit_trail.json as a "model_call" step (the agent being invoked) followed by a "result"
step (its structured reply). Tool calls log their own "tool_call" steps (backend/tools.py) and
delegate_to logs its own "delegation" step, all in the same file.
"""

from pydantic_ai.agent import AgentRunResult
from pydantic_ai.usage import RunUsage, UsageLimits

from . import audit, events
from .models import SpecialistReply, TicketContext


async def run_agent(
    agent_name: str,
    question: str,
    deps: TicketContext,
    *,
    usage: RunUsage | None = None,
    usage_limits: UsageLimits | None = None,
) -> AgentRunResult[SpecialistReply]:
    from .agents import AGENT_REGISTRY  # deferred: agents.py imports run_agent at module load

    deps.agent_name = agent_name

    entry = audit.record(
        {
            "agent": agent_name,
            "ticket_id": deps.ticket_id,
            "step": "model_call",
            "summary": audit.summarize(question),
        }
    )
    events.publish(entry)

    agent = AGENT_REGISTRY[agent_name]
    try:
        result = await agent.run(question, deps=deps, usage=usage, usage_limits=usage_limits)
    except Exception as exc:
        entry = audit.record(
            {
                "agent": agent_name,
                "ticket_id": deps.ticket_id,
                "step": "result",
                "summary": f"ERROR: {exc}",
                "error": True,
            }
        )
        events.publish(entry)
        raise
    reply = result.output

    entry = audit.record(
        {
            "agent": agent_name,
            "ticket_id": deps.ticket_id,
            "step": "result",
            "summary": reply.summary,
            "needs_human_approval": reply.needs_human_approval,
            "unresolved": reply.unresolved,
        }
    )
    events.publish(entry)
    return result
