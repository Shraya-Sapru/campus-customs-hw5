"""Tiny, cheap smoke check: can each agent answer one simple, read-only question?

This does NOT run the team on the real tickets - each question below is answerable with a
single MCP tool call and a small UsageLimits.request_limit, so no agent should need to delegate.
Run with:

    .\\.venv\\Scripts\\python.exe -m backend.smoke_test
"""

import asyncio

from pydantic_ai.usage import UsageLimits

from .mcp_client import mcp_client
from .models import TicketContext
from .runner import run_agent

QUESTIONS: dict[str, tuple[str, int | None]] = {
    "boss": ("What is today's date according to the shop desk (desk.date_today)?", None),
    "inventory": ("How many CC-TEE-WHITE size S do we have on hand right now?", 101),
    "accounting": ("What is the current balance of the 'checking' cash account?", None),
    "facilities": ("What is the monthly rent and next due date for lease 1?", 102),
    "customer_service": ("What is ticket 101 about? Just summarize it, don't draft anything.", 101),
}

# Cheap and tight: each question needs at most one tool call plus the final reply.
SMOKE_LIMITS = UsageLimits(request_limit=3)


async def main() -> None:
    await mcp_client.connect()
    try:
        for agent_name, (question, ticket_id) in QUESTIONS.items():
            deps = TicketContext(ticket_id=ticket_id)
            result = await run_agent(agent_name, question, deps, usage_limits=SMOKE_LIMITS)
            reply = result.output
            print(f"=== {agent_name} ===")
            print(f"Q: {question}")
            print(f"summary: {reply.summary}")
            print(f"key_facts: {reply.key_facts}")
            print()
    finally:
        await mcp_client.close()


if __name__ == "__main__":
    asyncio.run(main())
