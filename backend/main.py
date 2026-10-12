"""FastAPI backend for the Campus Customs dashboard (Problem 7).

Run from inside backend/:

    uvicorn main:app --reload --port 8000

Because that command loads this file as a bare top-level module (not as
backend.main), it can't use the same relative imports (`from . import x`) as the
rest of backend/ - so it adds the project root to sys.path itself and imports
everything through the real `backend` package instead, reusing the exact same
agents/tools/MCP-client code as backend/smoke_test.py, unchanged.

Every route below gets shop facts and makes shop writes only through the MCP
tools (backend.mcp_client / backend.tools) - no route runs its own SQL.
"""

import asyncio
import json
import re
import shutil
import sys
from contextlib import asynccontextmanager
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from fastapi import BackgroundTasks, FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel  # noqa: E402
from pydantic_ai.usage import UsageLimits  # noqa: E402

from backend import audit, events  # noqa: E402
from backend.audit import AUDIT_PATH  # noqa: E402
from backend.mcp_client import mcp_client  # noqa: E402
from backend.models import TicketContext  # noqa: E402
from backend.runner import run_agent  # noqa: E402

ORIGINAL_DB = _PROJECT_ROOT / "data" / "campus_customs.db"
WORKING_DB = _PROJECT_ROOT / "data" / "campus_customs_new.db"

# How many model requests one background ticket run may spend in total (shared
# across every delegation hop - see backend/agents.py's delegate_to). A full
# resolution can involve several specialists, each with their own multi-step
# reasoning loop, plus Boss's own triage and final write-up - 20 proved too tight
# in practice (a real run hit the cap on Boss's own closing reply after its
# specialists had already finished). Raised to leave headroom for that final
# answer; combined with the self-delegation guard below (which was also quietly
# burning budget), this should comfortably cover a normal run.
TICKET_REQUEST_LIMIT = 40

# Ticket ids currently being worked by a background run, so a second run can't
# be started for the same ticket while one is still in flight.
running_tickets: set[int] = set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await mcp_client.connect()
    events.hydrate_from_audit_trail(AUDIT_PATH)
    drainer = asyncio.create_task(events.drain_forever())
    try:
        yield
    finally:
        drainer.cancel()
        await mcp_client.close()


app = FastAPI(title="Campus Customs Desk", lifespan=lifespan)

# Local dev only: a React dev server on another port needs to call these routes.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- 1. GET /tickets -------------------------------------------------------

def _is_resolved(status: str) -> bool:
    """True only once a ticket needs nothing further from a human.

    Boss is instructed (backend/prompts/boss.md) to give any ticket that still
    needs a human to approve a payment or make a decision a status starting with
    "awaiting" (e.g. "awaiting payment approval") - everything else that isn't
    "open" (e.g. "resolved", or a more specific "resolved - ...") means the ticket
    is genuinely done. This is what decides whether the dashboard shows the green
    check/"RESOLVED" stamp or an "awaiting" badge.
    """
    return status != "open" and not status.lower().startswith("awaiting")


@app.get("/tickets")
async def get_tickets():
    """The three tickets, each with its status and whether it's open or resolved."""
    result = await mcp_client.call("list_tickets")
    tickets = [{**t, "resolved": _is_resolved(t["status"])} for t in result["tickets"]]
    return {"tickets": tickets}


# --- 2. POST /tickets/{ticket_id}/run --------------------------------------

async def _run_ticket_task(ticket_id: int) -> None:
    try:
        deps = TicketContext(ticket_id=ticket_id)
        question = (
            f"A ticket needs attention: ticket {ticket_id}. Pull its details, decide who "
            "needs to work on it, delegate as needed, and make the final call. Update the "
            "ticket's status when you're done to reflect the outcome."
        )
        await run_agent(
            "boss",
            question,
            deps,
            usage_limits=UsageLimits(request_limit=TICKET_REQUEST_LIMIT),
        )
    except Exception as exc:
        # backend.runner.run_agent already recorded this as a "result" audit/event
        # entry with error=True - this is only to stop it from becoming an unhandled
        # exception in the background task, and to make sure the ticket doesn't sit
        # silently on "open" forever if Boss never got the chance to set any status
        # before failing. If Boss *did* already set a status, leave it alone - it's
        # more informative than a generic one.
        try:
            ticket = await mcp_client.call("get_ticket", ticket_id=ticket_id)
            if ticket.get("found") and ticket["status"] == "open":
                await mcp_client.call(
                    "update_ticket_status",
                    ticket_id=ticket_id,
                    status="awaiting human review",
                    notes=f"The agent run stopped before finishing: {exc}",
                )
        except Exception:
            pass  # a cleanup failure here shouldn't mask the original error
    finally:
        running_tickets.discard(ticket_id)


@app.post("/tickets/{ticket_id}/run", status_code=202)
async def run_ticket(ticket_id: int, background_tasks: BackgroundTasks):
    """Start the agent team on a ticket in the background and return right away."""
    ticket = await mcp_client.call("get_ticket", ticket_id=ticket_id)
    if not ticket.get("found"):
        raise HTTPException(status_code=404, detail=f"No ticket with id {ticket_id}")
    if ticket["status"] != "open":
        raise HTTPException(
            status_code=409,
            detail=f"Ticket {ticket_id} is already resolved (status={ticket['status']!r})",
        )
    if ticket_id in running_tickets:
        raise HTTPException(status_code=409, detail=f"Ticket {ticket_id} is already running")

    running_tickets.add(ticket_id)
    background_tasks.add_task(_run_ticket_task, ticket_id)
    return {"started": True, "ticket_id": ticket_id}


# --- 3. GET /events ----------------------------------------------------------

@app.get("/events")
async def get_events(limit: int = 50):
    """Recent agent events (agent, tool, summary) from the in-memory live feed -
    separate from output/audit_trail.json, which stays append-only on disk."""
    return {"events": events.recent(limit=limit)}


# --- 4. POST /payments/{proposal_id}/approve --------------------------------

class ApproveBody(BaseModel):
    approved_by: str


def _find_ticket_for_proposal(proposal_id: int) -> int | None:
    """Which ticket a payment proposal belongs to, found by scanning the audit trail
    for the propose_payment call that created it (payment_proposals itself has no
    ticket_id column - only kind/ref_id, an invoice or lease id). Read-only; this
    never writes to output/audit_trail.json. The audit summary can be truncated
    (see backend/audit.py), so the id is matched with a tolerant regex rather than a
    strict JSON parse, the same approach the dashboard uses."""
    if not AUDIT_PATH.exists():
        return None
    try:
        events_on_disk = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    for event in events_on_disk:
        if event.get("tool") != "propose_payment":
            continue
        match = re.search(r'"id"\s*:\s*(\d+)', event.get("summary") or "")
        if match and int(match.group(1)) == proposal_id:
            return event.get("ticket_id")
    return None


@app.post("/payments/{proposal_id}/approve")
async def approve_payment_route(proposal_id: int, body: ApproveBody):
    """The only route that can move money - a thin pass-through to the MCP
    approve_payment tool, which is the only thing that writes payments/
    cash_accounts/invoices/leases, and the only thing that can refuse an
    insufficient-funds payment or require a non-empty human approver name.

    On a successful approval: marks the ticket that proposal belongs to resolved -
    a ticket that was only waiting on this one payment has nothing left for a human
    to do once it's approved (this assumes one proposal fully resolves the ticket it
    came from, which holds for the current ticket set) - and records the approval
    itself as an event. Without that second part, a human approving a payment is
    invisible to the dashboard's event feed (it's not an agent tool call), so a
    fresh page load would have no way to know this proposal isn't pending anymore
    and would incorrectly show it as still needing approval.
    """
    result = await mcp_client.call(
        "approve_payment", proposal_id=proposal_id, approved_by=body.approved_by
    )
    if result.get("approved"):
        ticket_id = _find_ticket_for_proposal(proposal_id)
        if ticket_id is not None:
            await mcp_client.call(
                "update_ticket_status",
                ticket_id=ticket_id,
                status="resolved",
                notes=f"Payment proposal #{proposal_id} approved by {body.approved_by}.",
            )
        entry = audit.record(
            {
                "agent": None,
                "ticket_id": ticket_id,
                "step": "tool_call",
                "tool": "approve_payment",
                "arguments": {"proposal_id": proposal_id, "approved_by": body.approved_by},
                "summary": audit.summarize(result),
            }
        )
        events.publish(entry)
    return result


# --- 5. GET /cash/balance ----------------------------------------------------

@app.get("/cash/balance")
async def get_cash_balance():
    """The current checking balance."""
    return await mcp_client.call("get_cash_balance", account="checking")


# --- 6. POST /reset -----------------------------------------------------------

@app.post("/reset")
async def reset_database():
    """Reset the working database from the untouched original, and clear the
    in-memory event feed. Never writes to the original, never touches
    output/audit_trail.json."""
    shutil.copyfile(ORIGINAL_DB, WORKING_DB)
    events.clear()
    return {"reset": True}
