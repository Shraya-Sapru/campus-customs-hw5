# Campus Customs Agent Team (backend/)

Five PydanticAI agents - Boss, Inventory, Accounting, Facilities, Customer Service - that read
and write shop facts only through the `campus-customs` MCP server (`mcp_server/server.py`).
Nothing here imports `sqlite3` or opens a database file directly.

## Layout

- `model.py` - the one place a model name and the Portkey-backed client are built. Every agent
  imports `MODEL` from here; nothing else should construct a model.
- `mcp_client.py` - the one shared stdio connection to the MCP server. Every tool function in
  `tools.py` goes through `mcp_client.call(...)`.
- `tools.py` - one thin async wrapper per MCP tool. Each agent in `agents.py` is given only the
  subset matching its role (see below). `approve_payment` is deliberately **not** wrapped here -
  no agent can ever move money; that tool is reserved for a human acting outside this system.
  Every call logs a `tool_call` audit event.
- `models.py` - `SpecialistReply` (the one output shape every agent returns) and
  `TicketContext`/`RunBudget` (the delegation-depth and delegation-count guards).
- `agents.py` - builds the five `Agent` objects and the shared `delegate_to` tool that gives
  full agent-to-agent connectivity, logging a `delegation` audit event per hop.
- `runner.py` - `run_agent(...)`, the one entry point for actually invoking an agent. Logs a
  `model_call` event before the run and a `result` event after. `delegate_to` and
  `smoke_test.py` both go through this instead of calling `Agent.run` directly.
- `audit.py` - append-only writer for `output/audit_trail.json`. Never logs the Portkey key.
  Returns the finalized event so callers can also hand it to `events.publish(...)`.
- `events.py` - the in-memory live feed for the dashboard (Problem 7): an `asyncio.Queue` that
  `tools.py`, `runner.py`, and `agents.py` publish to alongside every audit event, drained into a
  capped recent-events buffer that `GET /events` reads. Separate from `output/audit_trail.json`,
  which stays append-only on disk and is never cleared, even on `POST /reset`.
- `prompts/*.md` - one detailed instructions file per agent, loaded as-is at import time.
- `smoke_test.py` - a cheap, read-only check that each agent answers one simple question.
- `main.py` - the FastAPI app (Problem 7) a React dashboard talks to. See "Backend API" below.

## Why not PydanticAI's built-in MCP client?

PydanticAI's own `MCPToolset` (in `pydantic_ai.mcp`) needs `mcp>=2`, but `mcp_server/server.py`
is built on the v1 `mcp.server.fastmcp.FastMCP` API and is pinned to `mcp<2` (see
`mcp_server/README.md`) - installing pydantic-ai's `[mcp]` extra upgrades the shared `mcp`
package in this venv to 2.x and breaks the server outright (confirmed: it can no longer even
import). So `mcp_client.py` instead uses the plain `mcp` v1 `ClientSession`/`stdio_client` API -
the same API the server speaks - to call the exact same tools. Every agent still only gets shop
facts through the real MCP server; this is just a different (compatible) client for the same
protocol.

## Tool access per role (least privilege)

| Agent | Tools |
|---|---|
| boss | `get_today`, `list_tickets`, `get_ticket`, `update_ticket_status` |
| inventory | `get_today`, `get_ticket`, `get_inventory`, `list_vendors`, `get_invoice`, `list_open_invoices_for_vendor` |
| accounting | `get_today`, `get_ticket`, `get_cash_balance`, `get_pricing`, `get_invoice`, `list_open_invoices_for_vendor`, `list_payment_proposals`, `propose_payment` |
| facilities | `get_today`, `get_ticket`, `get_lease` |
| customer_service | `get_today`, `get_ticket`, `save_draft` |

Every agent also has `delegate_to`, so the division above is about who owns which facts/writes by
default, not a hard wall - e.g. Customer Service gets stock facts by delegating to Inventory
rather than querying inventory itself. Only Boss calls `update_ticket_status`, only Accounting
calls `propose_payment`, only Customer Service calls `save_draft`, and no agent ever calls
`approve_payment`.

## Loop safety

- `TicketContext.max_depth` (default 4) caps how many delegation hops deep one ticket can go.
- `RunBudget.max_delegations` (default 6) caps total `delegate_to` calls across the whole run -
  it's one shared object passed by reference through every delegation, so the cap is on the tree
  as a whole, not per agent.
- Whoever starts a ticket should also pass `usage_limits=UsageLimits(request_limit=...)` to
  `Agent.run`, capping total model requests spent on that ticket regardless of delegation shape.
  See `smoke_test.py` for an example.

## Running the smoke test

```powershell
.\.venv\Scripts\python.exe -m backend.smoke_test
```

This does not touch the real tickets - each question is a single, read-only MCP call.

## Backend API (`main.py`)

```powershell
cd backend
..\.venv\Scripts\uvicorn.exe main:app --reload --port 8000
```

`main.py` is loaded by uvicorn as a bare top-level module (not `backend.main`), so it can't use
the relative imports (`from . import x`) the rest of this package uses - it adds the project root
to `sys.path` itself and imports everything through the real `backend` package instead
(`from backend.agents import ...`), so it's running the exact same code as `smoke_test.py`, not a
separate copy. CORS is wide open (`allow_origins=["*"]`) since this is local-dev-only, for a React
dev server on a different port. Route list and one-line descriptions are in
`output/harness.md`'s "Backend API routes" section.

A couple of things worth knowing if you extend this:
- `POST /tickets/{id}/run` and `POST /reset` aren't mutually locked - resetting the database while
  a background run is still in flight for some ticket isn't guarded against, since the assignment
  only asked for one run per ticket at a time, not cross-route locking.
- `POST /payments/{id}/approve` is a thin pass-through to the `approve_payment` MCP tool and
  nothing else - it's the only way `approve_payment` is ever called, since no agent is given that
  tool (see "Tool access per role" above).
