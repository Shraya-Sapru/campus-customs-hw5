# Campus Customs MCP Server

A FastMCP server that gives the Campus Customs agents read/write access to the shop database. It connects only to the working copy, `data/campus_customs_new.db` (the path is set in one place, `mcp_server/db.py`, so it's easy to change — it can also be overridden with the `CAMPUS_CUSTOMS_DB_PATH` environment variable, used only by the throwaway-copy test harness). The original `data/campus_customs.db` is never opened by this server.

There is no separate layer that reads the database directly: every shop fact an agent uses comes from one of these tools.

## Schema additions

The original schema didn't have anywhere to store drafts or pending payments, so `mcp_server/db.py` applies a small, additive, idempotent migration the first time any tool connects:

- new table `drafts` (`id`, `ticket_id`, `message`, `created_at`)
- new table `payment_proposals` (`id`, `kind`, `ref_id`, `amount`, `account`, `reason`, `proposed_by`, `proposed_at`, `status`, `approved_by`, `approved_at`)
- new nullable column `leases.last_paid`

No existing table, column, or row is changed or removed by this migration.

## Tools

**Read-only**

1. **`get_inventory(sku, size)`** — on-hand quantity and location from `inventory`. Built for ticket 101 (`CC-TEE-WHITE` size `S`, stock 0).
2. **`get_lease(lease_id)`** — a lease's rent, due date, and `last_paid` from `leases`. Built for ticket 102 (`lease_id = 1`).
3. **`get_pricing(sku)`** — unit cost and list price from `pricing`. Built for ticket 103's bulk discount math on `CC-HOOD-NAVY`.
4. **`get_today()`** — the shop's simulated "today" from `desk`. Every overdue/due-soon check must use this, never the real clock.
5. **`list_tickets(status=None)`** — tickets from `tickets`, optionally filtered by status.
6. **`get_ticket(ticket_id)`** — a single ticket's full row from `tickets`.
7. **`list_vendors()`** — all vendors from `vendors`, including `specialty` and `lead_days`.
8. **`get_invoice(invoice_id)`** — a single invoice from `invoices`. Resolves ticket 101's `invoice_id = 501`.
9. **`list_open_invoices_for_vendor(vendor_id)`** — open invoices for a vendor from `invoices`, e.g. to check whether a restock vendor is blocked.
10. **`get_cash_balance(account)`** — balance and as-of date for a named account from `cash_accounts`.
11. **`list_payment_proposals(status=None)`** — proposed payments from `payment_proposals`, optionally filtered by status.

**Write**

12. **`update_ticket_status(ticket_id, status, notes=None)`** — updates `tickets.status` (and optionally `notes`). Touches only `tickets`.
13. **`save_draft(ticket_id, message)`** — inserts a customer-facing draft into `drafts`. Never sends email or contacts anyone; the draft just sits on the board.
14. **`propose_payment(kind, ref_id, amount, account, proposed_by, reason=None)`** — inserts a pending row into `payment_proposals`. `kind` is `"invoice"` (ref_id = an `invoices.id`) or `"rent"` (ref_id = a `leases.id`). This is the only way Accounting can initiate a payment, and it moves no money and touches no other table.
15. **`approve_payment(proposal_id, approved_by)`** — the only tool that can ever move money, and the only human-approval checkpoint. Requires a non-empty `approved_by` name. Refuses if the proposal isn't `pending`, if its invoice is no longer `open`, or if paying would take `cash_accounts.balance` negative — in every refusal case, no table is written and the proposal stays `pending`. On success it atomically: inserts into `payments`, debits `cash_accounts.balance`, marks the proposal `paid`, and marks the invoice `paid` (kind `"invoice"`) or stamps `leases.last_paid` (kind `"rent"`).

## Rules enforced in the tool code (not just prompts)

- **Human approval required for every payment.** `propose_payment` only ever inserts into `payment_proposals`; no tool it calls touches `payments` or `cash_accounts`. `approve_payment` is the sole path to those two tables, and it requires a human name in `approved_by`.
- **Cash can never go negative.** `approve_payment` computes the post-payment balance and refuses before writing anything if it would drop below zero.
- **Cash only goes out.** No tool in this server ever increases a `cash_accounts.balance` — the only write to `balance` is the subtraction in `approve_payment`.
- **Simulated clock only.** Every timestamp a tool writes (`proposed_at`, `approved_at`, `paid_at`, `created_at` on drafts) is read from `desk.date_today` via the internal `_today()` helper, never from the system clock.
- **Drafts never leave the board.** `save_draft` only inserts a row into `drafts`. No tool sends email, calls an API, or contacts anyone.
- **No invented data.** Every tool uses parameterized SQL against real rows and returns a clear `{"found": False, ...}` / `{"approved": False, ...}` style result instead of guessing when something doesn't exist.
- **Working copy only.** Every tool connects through `mcp_server/db.py`'s `DB_PATH`, which defaults to `data/campus_customs_new.db`; `data/campus_customs.db` is never opened by this server.

## Testing write tools

The write tools (`update_ticket_status`, `save_draft`, `propose_payment`, `approve_payment`) were exercised against a **throwaway copy** of `campus_customs_new.db`, never the real working file:

1. Copied `data/campus_customs_new.db` to a scratch path outside the project.
2. Set the `CAMPUS_CUSTOMS_DB_PATH` environment variable to that scratch copy before importing the server module, so every tool call in the test run pointed at the throwaway file instead of the real one.
3. Ran a script that proposed and approved an invoice payment and a rent payment (both succeeded and updated `payments`/`cash_accounts`/`invoices`/`leases` correctly on the throwaway copy), proposed a payment that would have overdrawn the account (correctly refused, balance unchanged, proposal left `pending`), tried to re-approve an already-paid proposal (correctly refused), and tried invalid `kind`/account values (correctly refused).
4. Deleted the throwaway copy afterward and confirmed the real `data/campus_customs_new.db` still showed the original `checking` balance ($3400), zero rows in `payments`, and empty `drafts`/`payment_proposals` tables — the write tests never touched it.

Read-only tools were called directly against the real `campus_customs_new.db` (safe, since they can't mutate anything), which is also what applied the schema migration described above.

## Running

```powershell
.\.venv\Scripts\python.exe -m mcp_server.server
```
