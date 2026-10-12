import sqlite3

from mcp.server.fastmcp import FastMCP

from mcp_server.db import DB_PATH, ensure_schema

mcp = FastMCP("campus-customs")


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    ensure_schema(con)
    return con


def _today(con: sqlite3.Connection) -> str:
    row = con.execute("SELECT date_today FROM desk LIMIT 1").fetchone()
    return row["date_today"]


@mcp.tool()
def get_inventory(sku: str, size: str) -> dict:
    """Look up on-hand quantity and location for a SKU and size."""
    con = _connect()
    try:
        row = con.execute(
            "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ? AND size = ?",
            (sku, size),
        ).fetchone()
    finally:
        con.close()
    if row is None:
        return {"found": False, "message": f"No inventory row for sku={sku!r} size={size!r}"}
    return {"found": True, **dict(row)}


@mcp.tool()
def get_lease(lease_id: int) -> dict:
    """Look up a lease by its id, including rent amount and next due date."""
    con = _connect()
    try:
        row = con.execute(
            "SELECT id, space_name, landlord, monthly_rent, next_due, notes, last_paid FROM leases WHERE id = ?",
            (lease_id,),
        ).fetchone()
    finally:
        con.close()
    if row is None:
        return {"found": False, "message": f"No lease row for id={lease_id!r}"}
    return {"found": True, **dict(row)}


@mcp.tool()
def get_pricing(sku: str) -> dict:
    """Look up unit cost and list price for a SKU."""
    con = _connect()
    try:
        row = con.execute(
            "SELECT sku, unit_cost, list_price FROM pricing WHERE sku = ?",
            (sku,),
        ).fetchone()
    finally:
        con.close()
    if row is None:
        return {"found": False, "message": f"No pricing row for sku={sku!r}"}
    return {"found": True, **dict(row)}


@mcp.tool()
def get_today() -> dict:
    """Return the shop's simulated 'today' (desk.date_today) and any desk notes. All overdue/due-soon logic must use this, never the real clock."""
    con = _connect()
    try:
        row = con.execute("SELECT date_today, notes FROM desk LIMIT 1").fetchone()
    finally:
        con.close()
    if row is None:
        return {"found": False, "message": "desk table has no row"}
    return {"found": True, **dict(row)}


@mcp.tool()
def list_tickets(status: str | None = None) -> dict:
    """List tickets, optionally filtered by status (e.g. 'open')."""
    con = _connect()
    try:
        if status is None:
            rows = con.execute("SELECT * FROM tickets ORDER BY id").fetchall()
        else:
            rows = con.execute(
                "SELECT * FROM tickets WHERE status = ? ORDER BY id", (status,)
            ).fetchall()
    finally:
        con.close()
    tickets = [dict(r) for r in rows]
    return {"count": len(tickets), "tickets": tickets}


@mcp.tool()
def get_ticket(ticket_id: int) -> dict:
    """Look up a single ticket by its id, with all of its fields."""
    con = _connect()
    try:
        row = con.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    finally:
        con.close()
    if row is None:
        return {"found": False, "message": f"No ticket with id={ticket_id!r}"}
    return {"found": True, **dict(row)}


@mcp.tool()
def list_vendors() -> dict:
    """List all vendors with their specialty and restock lead time."""
    con = _connect()
    try:
        rows = con.execute("SELECT * FROM vendors ORDER BY id").fetchall()
    finally:
        con.close()
    vendors = [dict(r) for r in rows]
    return {"count": len(vendors), "vendors": vendors}


@mcp.tool()
def get_invoice(invoice_id: int) -> dict:
    """Look up a single invoice by its id."""
    con = _connect()
    try:
        row = con.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
    finally:
        con.close()
    if row is None:
        return {"found": False, "message": f"No invoice with id={invoice_id!r}"}
    return {"found": True, **dict(row)}


@mcp.tool()
def list_open_invoices_for_vendor(vendor_id: int) -> dict:
    """List open (unpaid) invoices for a given vendor id."""
    con = _connect()
    try:
        rows = con.execute(
            "SELECT * FROM invoices WHERE vendor_id = ? AND status = 'open' ORDER BY id",
            (vendor_id,),
        ).fetchall()
    finally:
        con.close()
    invoices = [dict(r) for r in rows]
    return {"count": len(invoices), "invoices": invoices}


@mcp.tool()
def get_cash_balance(account: str) -> dict:
    """Look up the balance and as-of date for a cash account by name (e.g. 'checking')."""
    con = _connect()
    try:
        row = con.execute(
            "SELECT name, balance, date FROM cash_accounts WHERE name = ?", (account,)
        ).fetchone()
    finally:
        con.close()
    if row is None:
        return {"found": False, "message": f"No cash account named {account!r}"}
    return {"found": True, **dict(row)}


@mcp.tool()
def update_ticket_status(ticket_id: int, status: str, notes: str | None = None) -> dict:
    """Update a ticket's status (and optionally replace its notes). Does not touch any other table."""
    if not status or not status.strip():
        return {"updated": False, "message": "status must be a non-empty string"}
    con = _connect()
    try:
        existing = con.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if existing is None:
            return {"updated": False, "message": f"No ticket with id={ticket_id!r}"}
        if notes is None:
            con.execute("UPDATE tickets SET status = ? WHERE id = ?", (status, ticket_id))
        else:
            con.execute(
                "UPDATE tickets SET status = ?, notes = ? WHERE id = ?",
                (status, notes, ticket_id),
            )
        con.commit()
        row = con.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    finally:
        con.close()
    return {"updated": True, **dict(row)}


@mcp.tool()
def save_draft(ticket_id: int, message: str) -> dict:
    """Save a draft customer-facing message to the board for a ticket. Never sends anything anywhere."""
    if not message or not message.strip():
        return {"saved": False, "message": "message must be a non-empty string"}
    con = _connect()
    try:
        ticket = con.execute("SELECT id FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if ticket is None:
            return {"saved": False, "message": f"No ticket with id={ticket_id!r}"}
        today = _today(con)
        cur = con.execute(
            "INSERT INTO drafts (ticket_id, message, created_at) VALUES (?, ?, ?)",
            (ticket_id, message, today),
        )
        con.commit()
        draft_id = cur.lastrowid
        row = con.execute("SELECT * FROM drafts WHERE id = ?", (draft_id,)).fetchone()
    finally:
        con.close()
    return {"saved": True, **dict(row)}


@mcp.tool()
def propose_payment(
    kind: str, ref_id: int, amount: float, account: str, proposed_by: str, reason: str | None = None
) -> dict:
    """Propose a payment (kind='invoice' or 'rent', ref_id = invoice id or lease id). This only records
    a pending proposal; no money moves and no table except payment_proposals is touched. Use approve_payment
    with a human name to actually pay it."""
    if kind not in ("invoice", "rent"):
        return {"proposed": False, "message": "kind must be 'invoice' or 'rent'"}
    if amount is None or amount <= 0:
        return {"proposed": False, "message": "amount must be a positive number"}
    if not proposed_by or not proposed_by.strip():
        return {"proposed": False, "message": "proposed_by must be a non-empty name"}

    con = _connect()
    try:
        if kind == "invoice":
            ref = con.execute("SELECT id FROM invoices WHERE id = ?", (ref_id,)).fetchone()
            if ref is None:
                return {"proposed": False, "message": f"No invoice with id={ref_id!r}"}
        else:
            ref = con.execute("SELECT id FROM leases WHERE id = ?", (ref_id,)).fetchone()
            if ref is None:
                return {"proposed": False, "message": f"No lease with id={ref_id!r}"}

        acct = con.execute("SELECT name FROM cash_accounts WHERE name = ?", (account,)).fetchone()
        if acct is None:
            return {"proposed": False, "message": f"No cash account named {account!r}"}

        today = _today(con)
        cur = con.execute(
            """
            INSERT INTO payment_proposals
                (kind, ref_id, amount, account, reason, proposed_by, proposed_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
            """,
            (kind, ref_id, amount, account, reason, proposed_by, today),
        )
        con.commit()
        proposal_id = cur.lastrowid
        row = con.execute("SELECT * FROM payment_proposals WHERE id = ?", (proposal_id,)).fetchone()
    finally:
        con.close()
    return {"proposed": True, **dict(row)}


@mcp.tool()
def list_payment_proposals(status: str | None = None) -> dict:
    """List payment proposals, optionally filtered by status ('pending', 'paid', ...)."""
    con = _connect()
    try:
        if status is None:
            rows = con.execute("SELECT * FROM payment_proposals ORDER BY id").fetchall()
        else:
            rows = con.execute(
                "SELECT * FROM payment_proposals WHERE status = ? ORDER BY id", (status,)
            ).fetchall()
    finally:
        con.close()
    proposals = [dict(r) for r in rows]
    return {"count": len(proposals), "proposals": proposals}


@mcp.tool()
def approve_payment(proposal_id: int, approved_by: str) -> dict:
    """The only tool that can ever move money. Requires a human approver name. Refuses if the proposal
    isn't pending, if its invoice/lease is no longer payable, or if paying it would take the cash account
    negative. On success, atomically records the payment, debits the cash account, and marks the invoice
    paid (or stamps the lease's last_paid date)."""
    if not approved_by or not approved_by.strip():
        return {"approved": False, "message": "approved_by must be a non-empty human name"}

    con = _connect()
    try:
        proposal = con.execute(
            "SELECT * FROM payment_proposals WHERE id = ?", (proposal_id,)
        ).fetchone()
        if proposal is None:
            return {"approved": False, "message": f"No payment proposal with id={proposal_id!r}"}
        if proposal["status"] != "pending":
            return {
                "approved": False,
                "message": f"Proposal {proposal_id} is already '{proposal['status']}', not pending",
            }

        kind, ref_id, amount, account = (
            proposal["kind"],
            proposal["ref_id"],
            proposal["amount"],
            proposal["account"],
        )

        if kind == "invoice":
            ref_row = con.execute("SELECT * FROM invoices WHERE id = ?", (ref_id,)).fetchone()
            if ref_row is None:
                return {"approved": False, "message": f"No invoice with id={ref_id!r}"}
            if ref_row["status"] != "open":
                return {
                    "approved": False,
                    "message": f"Invoice {ref_id} is already '{ref_row['status']}', not open",
                }
        else:
            ref_row = con.execute("SELECT * FROM leases WHERE id = ?", (ref_id,)).fetchone()
            if ref_row is None:
                return {"approved": False, "message": f"No lease with id={ref_id!r}"}

        acct_row = con.execute(
            "SELECT * FROM cash_accounts WHERE name = ?", (account,)
        ).fetchone()
        if acct_row is None:
            return {"approved": False, "message": f"No cash account named {account!r}"}

        new_balance = acct_row["balance"] - amount
        if new_balance < 0:
            return {
                "approved": False,
                "message": (
                    f"Insufficient funds: {account} balance is {acct_row['balance']}, "
                    f"payment is {amount}. Proposal left pending."
                ),
            }

        today = _today(con)
        try:
            con.execute(
                "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (kind, ref_id, amount, account, today, approved_by),
            )
            con.execute(
                "UPDATE cash_accounts SET balance = ? WHERE name = ?", (new_balance, account)
            )
            con.execute(
                "UPDATE payment_proposals SET status = 'paid', approved_by = ?, approved_at = ? "
                "WHERE id = ?",
                (approved_by, today, proposal_id),
            )
            if kind == "invoice":
                con.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (ref_id,))
            else:
                con.execute("UPDATE leases SET last_paid = ? WHERE id = ?", (today, ref_id))
            con.commit()
        except Exception:
            con.rollback()
            raise

        payment = con.execute("SELECT * FROM payments ORDER BY id DESC LIMIT 1").fetchone()
    finally:
        con.close()

    return {"approved": True, "payment": dict(payment), "new_balance": new_balance}


if __name__ == "__main__":
    mcp.run()
