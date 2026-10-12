"""Thin async wrappers, one per MCP server tool, that agents call directly.

Every function here takes a RunContext so it knows which agent/ticket is running (for the audit
trail), then does nothing but call mcp_client.call(...) and hand back the result. This is the
only way any agent touches shop data - there is no direct database import anywhere in backend/.
Each agent in backend/agents.py is given only the subset of these functions that matches its
role. Every call is appended to output/audit_trail.json as a "tool_call" step (see audit.py).
"""

from pydantic_ai import RunContext

from . import audit, events
from .mcp_client import mcp_client
from .models import TicketContext


async def _call(ctx: RunContext[TicketContext], tool_name: str, **arguments) -> dict:
    try:
        result = await mcp_client.call(tool_name, **arguments)
    except Exception as exc:
        entry = audit.record(
            {
                "agent": ctx.deps.agent_name,
                "ticket_id": ctx.deps.ticket_id,
                "step": "tool_call",
                "tool": tool_name,
                "arguments": arguments,
                "summary": f"ERROR: {exc}",
                "error": True,
            }
        )
        events.publish(entry)
        raise
    entry = audit.record(
        {
            "agent": ctx.deps.agent_name,
            "ticket_id": ctx.deps.ticket_id,
            "step": "tool_call",
            "tool": tool_name,
            "arguments": arguments,
            "summary": audit.summarize(result),
        }
    )
    events.publish(entry)
    return result


async def get_today(ctx: RunContext[TicketContext]) -> dict:
    """Return the shop's simulated 'today' (desk.date_today) and any desk notes.
    Always use this for "is X overdue/due soon" questions - never assume a real calendar date."""
    return await _call(ctx, "get_today")


async def list_tickets(ctx: RunContext[TicketContext], status: str | None = None) -> dict:
    """List tickets, optionally filtered by status (e.g. 'open')."""
    return await _call(ctx, "list_tickets", status=status)


async def get_ticket(ctx: RunContext[TicketContext], ticket_id: int) -> dict:
    """Look up a single ticket by id, with all of its fields."""
    return await _call(ctx, "get_ticket", ticket_id=ticket_id)


async def update_ticket_status(
    ctx: RunContext[TicketContext], ticket_id: int, status: str, notes: str | None = None
) -> dict:
    """Update a ticket's status (and optionally replace its notes). Only Boss calls this,
    as the final record of how a ticket was resolved."""
    return await _call(ctx, "update_ticket_status", ticket_id=ticket_id, status=status, notes=notes)


async def get_inventory(ctx: RunContext[TicketContext], sku: str, size: str) -> dict:
    """Look up on-hand quantity and location for a SKU and size."""
    return await _call(ctx, "get_inventory", sku=sku, size=size)


async def list_vendors(ctx: RunContext[TicketContext]) -> dict:
    """List all vendors with their specialty and restock lead time (lead_days)."""
    return await _call(ctx, "list_vendors")


async def get_invoice(ctx: RunContext[TicketContext], invoice_id: int) -> dict:
    """Look up a single invoice by id (vendor, amount, due date, status)."""
    return await _call(ctx, "get_invoice", invoice_id=invoice_id)


async def list_open_invoices_for_vendor(ctx: RunContext[TicketContext], vendor_id: int) -> dict:
    """List open (unpaid) invoices for a given vendor id. An open invoice means that
    vendor will not ship new stock until it is paid."""
    return await _call(ctx, "list_open_invoices_for_vendor", vendor_id=vendor_id)


async def get_pricing(ctx: RunContext[TicketContext], sku: str) -> dict:
    """Look up unit cost and list price for a SKU."""
    return await _call(ctx, "get_pricing", sku=sku)


async def get_cash_balance(ctx: RunContext[TicketContext], account: str) -> dict:
    """Look up the balance and as-of date for a cash account by name (e.g. 'checking')."""
    return await _call(ctx, "get_cash_balance", account=account)


async def list_payment_proposals(ctx: RunContext[TicketContext], status: str | None = None) -> dict:
    """List payment proposals, optionally filtered by status ('pending', 'paid', ...)."""
    return await _call(ctx, "list_payment_proposals", status=status)


async def propose_payment(
    ctx: RunContext[TicketContext],
    kind: str,
    ref_id: int,
    amount: float,
    account: str,
    proposed_by: str,
    reason: str | None = None,
) -> dict:
    """Propose a payment (kind='invoice' or 'rent', ref_id = invoice id or lease id) for a human
    to approve later. Only Accounting calls this. This never moves money by itself - it only
    records a pending proposal for a human to act on outside this agent system."""
    return await _call(
        ctx,
        "propose_payment",
        kind=kind,
        ref_id=ref_id,
        amount=amount,
        account=account,
        proposed_by=proposed_by,
        reason=reason,
    )


async def get_lease(ctx: RunContext[TicketContext], lease_id: int) -> dict:
    """Look up a lease by id, including monthly rent, next due date, and last_paid."""
    return await _call(ctx, "get_lease", lease_id=lease_id)


async def save_draft(ctx: RunContext[TicketContext], ticket_id: int, message: str) -> dict:
    """Save a draft customer-facing message to the board for a ticket. Only Customer Service
    calls this. This never sends anything to anyone - the draft just sits on the board for a
    human to review and send later."""
    return await _call(ctx, "save_draft", ticket_id=ticket_id, message=message)
