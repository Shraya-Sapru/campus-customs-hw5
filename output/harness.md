# Campus Customs — Database Harness

Reference notes on the schema of `data/campus_customs.db`. One section per table: fields (with types) and why the table matters to the agents. This file grows in later problems.

## desk

- `date_today` (TEXT, not null) — the simulated "today." All overdue/due-soon checks must compare against this, never the real system clock.
- `notes` (TEXT, nullable)

Why it matters: every agent that reasons about deadlines (Accounting for invoices/rent, Inventory for lead times) must anchor on `desk.date_today`, not `datetime.now()`.

## tickets

- `id` (INTEGER, PK)
- `type` (TEXT, not null) — e.g. `customer_order`, `rent_notice`, `price_override`
- `requester` (TEXT, not null)
- `subject` (TEXT, not null)
- `sku` (TEXT, nullable)
- `size` (TEXT, nullable)
- `qty` (INTEGER, nullable)
- `lease_id` (INTEGER, nullable, FK → `leases.id`)
- `invoice_id` (INTEGER, nullable, FK → `invoices.id`)
- `status` (TEXT, not null)
- `notes` (TEXT, nullable)
- `created_at` (TEXT, not null, ISO timestamp with offset)

Why it matters: this is the board itself — the unit of work the Boss triages and routes to Inventory / Accounting / Facilities / Customer Service.

## inventory

- `sku` (TEXT, part of composite PK)
- `name` (TEXT, not null)
- `size` (TEXT, part of composite PK)
- `qty` (INTEGER, not null)
- `location` (TEXT, not null)

Why it matters: Inventory's source of truth for stock-on-hand by SKU+size; it's what Inventory checks to detect shortfalls against ticket requests.

## pricing

- `sku` (TEXT, PK)
- `unit_cost` (REAL, not null)
- `list_price` (REAL, not null)

Why it matters: Accounting needs `unit_cost` vs `list_price` to evaluate margin on any discount request before approving a price override.

## vendors

- `id` (INTEGER, PK)
- `name` (TEXT, not null)
- `specialty` (TEXT, not null)
- `lead_days` (INTEGER, not null)

Why it matters: Inventory uses `specialty` to pick which vendor can restock a given product, and `lead_days` to estimate when restocked items would arrive.

## leases

- `id` (INTEGER, PK)
- `space_name` (TEXT, not null)
- `landlord` (TEXT, not null)
- `monthly_rent` (REAL, not null)
- `next_due` (TEXT, not null)
- `notes` (TEXT, nullable)

Why it matters: Facilities uses this to track rent obligations and due dates for the shop space.

## cash_accounts

- `name` (TEXT, PK)
- `balance` (REAL, not null)
- `date` (TEXT, not null) — balance as-of date

Why it matters: Accounting checks `balance` before approving any payment; the pay tool must refuse if a payment would take balance negative.

## payments

- `id` (INTEGER, PK)
- `kind` (TEXT, not null) — what's being paid (e.g. invoice, rent)
- `ref_id` (INTEGER, nullable) — id of the invoice/lease/etc. being paid
- `amount` (REAL, not null)
- `account` (TEXT, not null) — which cash account it was paid from
- `paid_at` (TEXT, not null)
- `approved_by` (TEXT, not null) — the human approver

Why it matters: this is the audit trail of every human-approved payment; currently empty (0 rows) since nothing has been paid yet.

## invoices

- `id` (INTEGER, PK)
- `vendor_id` (INTEGER, not null, FK → `vendors.id`)
- `amount` (REAL, not null)
- `due_date` (TEXT, not null)
- `status` (TEXT, not null) — e.g. `open`
- `description` (TEXT, nullable)

Why it matters: Accounting watches open invoices for payment; also gates vendor shipping — a vendor with an open unpaid invoice won't ship new stock.

---

## The three open tickets

### Ticket 101 — customer order, Bulldog tee, size S
Requester Tauhid Zaman wants 1 `CC-TEE-WHITE` in size S. It links to:
- **inventory**: `CC-TEE-WHITE`/`S` has `qty = 0` — this exact item is out of stock.
- **invoices**: `invoice_id = 501`, which belongs to vendor 1 (Bulldog Print Co), for $840, due `2026-08-28`, status `open`, described as "Rush reprint CC-TEE-WHITE S" — the same SKU/size as this ticket.
- **vendors**: vendor 1, Bulldog Print Co, specialty "apparel reprint," `lead_days = 5` — the vendor who'd normally restock this tee.

Plain language: a customer wants a white tee in size S, but it's out of stock, and the vendor who makes that tee already has an unpaid invoice from a previous rush reprint of the exact same item — so by the shop's rules, that vendor won't ship a new batch until the old invoice is paid.

### Ticket 102 — rent notice
Requester Elm City Properties (the landlord) flags that rent is due in 2 days. It links to:
- **leases**: `lease_id = 1`, "Chapel Street shop," landlord Elm City Properties, `monthly_rent = $2400`, `next_due = 2026-09-02` (2 days after `desk.date_today = 2026-08-31`, matching the note).
- **cash_accounts**: `checking` balance is $3400 — enough to cover rent alone, but combined with invoice 501 ($840) that's $3240 of near-term obligations against $3400 cash.

Plain language: the landlord is reminding the shop that the $2400 rent payment on the Chapel Street lease is due in two days.

### Ticket 103 — price override / bulk discount request
Requester Yale AI Club wants 20 `CC-HOOD-NAVY` hoodies in size M with a bulk discount. It links to:
- **inventory**: `CC-HOOD-NAVY`/`M` has `qty = 8` — current stock can't cover the requested 20 (shortfall of 12).
- **pricing**: `CC-HOOD-NAVY` has `unit_cost = $22`, `list_price = $58` (~62% margin at list) — needed to evaluate how much discount the shop can afford to give.
- **vendors**: no explicit SKU→vendor mapping exists; the closest match by `specialty` is Bulldog Print Co ("apparel reprint"), the same vendor blocked by invoice 501.

Plain language: a student club wants to buy 20 navy hoodies in size M at a bulk discount, but the shop only has 8 in stock, so fulfilling it in full would also require restocking — from the same vendor currently blocked by an unpaid invoice.

## What I found, especially anything surprising

- **The core puzzle is intentional and cross-ticket**: ticket 101's exact SKU/size (`CC-TEE-WHITE`/S) is both out of stock (`qty = 0`) *and* its restock vendor (Bulldog Print Co) is blocked by an already-overdue invoice (501, due 2026-08-28, 3 days overdue as of `desk.date_today = 2026-08-31`) for a prior rush reprint of that same item. An agent can't just "reorder stock" — it has to recognize the invoice needs paying first.
- **Cash is tight on purpose**: checking has $3400; rent ($2400, due in 2 days) plus invoice 501 ($840) alone total $3240, leaving only $160 of slack. If ticket 103's hoodie restock gets priced in too, the shop could easily go cash-negative — this is clearly set up to force Accounting to sequence/prioritize payments rather than approve everything at once.
- **No vendor can be inferred with certainty for hoodies**: there's no SKU→vendor table; vendor selection has to be inferred from the free-text `specialty` field. Bulldog Print Co's specialty is "apparel reprint" which covers both tees and hoodies, but nothing formally ties a SKU to a vendor ID. Worth deciding/documenting how Inventory should do this matching.
- **`QuickShip CT`'s role is unclear**: its specialty is "local courier" (`lead_days = 1`), unlike the other two vendors which are goods producers. It's not referenced by any ticket or invoice yet — possibly meant for expedited delivery after production, or possibly a distractor in the data.
- **`payments` table is empty by design**: zero rows, consistent with "every payment needs human approval" — nothing has been paid yet, so this table is purely an audit log to be filled in as the human approves things.
- **No revenue/sales model anywhere**: ticket 101 is a "customer order" but there's no mechanism to record money coming in from the customer — consistent with the stated rule that cash only goes out and no revenue is modeled. Fulfilling a customer order is apparently just about moving inventory, not collecting payment.
- **Invoice-to-ticket linkage is partly implicit**: `invoices.description` ("Rush reprint CC-TEE-WHITE S") is the only thing connecting invoice 501 to the SKU/size in ticket 101 — there's no formal FK from `invoices` to a SKU. Agents (or the MCP tools) will need to parse that text or otherwise be told how these connect.

## MCP server tools (`mcp_server/server.py`)

Three read-only tools, each built for one of the three open tickets.

| Tool | Table it reads | Ticket | Why it's the right tool for that ticket |
|---|---|---|---|
| `get_inventory(sku, size)` | `inventory` | 101 | Ticket 101 asks for 1 `CC-TEE-WHITE` in size S; this tool is the only way to confirm the on-hand `qty = 0` that makes this a shortfall rather than a normal fulfillment. |
| `get_lease(lease_id)` | `leases` | 102 | Ticket 102 carries `lease_id = 1` and no other details; this tool resolves it to the actual rent figures (`monthly_rent = $2400`, `next_due = 2026-09-02`) the Facilities agent needs to confirm the "due in 2 days" claim in the ticket notes. |
| `get_pricing(sku)` | `pricing` | 103 | Ticket 103 asks for a bulk discount on 20 `CC-HOOD-NAVY`; this tool returns `unit_cost = $22` and `list_price = $58`, the exact numbers Accounting needs to judge how much discount still leaves a positive margin. |

None of the three tools attempt to resolve a SKU to a vendor, since that link only exists in free text (e.g. invoice 501's description) and isn't a real foreign key — see "What I found" above.

## The full MCP tool list (`mcp_server/server.py`)

The server grew from the original 3 tools to 15 as the agent team needed more facts and a safe way to record writes. Every tool is parameterized SQL against `data/campus_customs_new.db` only, and returns a clear `{"found": False, ...}`-style result instead of guessing when something doesn't exist.

| Tool | Table(s) | Read/Write | Notes |
|---|---|---|---|
| `get_today` | `desk` | read | the simulated "today"; every overdue/due-soon check anywhere in the system must use this |
| `list_tickets` | `tickets` | read | optional status filter |
| `get_ticket` | `tickets` | read | full row by id |
| `get_inventory` | `inventory` | read | on-hand qty + location by sku/size |
| `list_vendors` | `vendors` | read | specialty + lead_days for every vendor |
| `get_invoice` | `invoices` | read | full row by id |
| `list_open_invoices_for_vendor` | `invoices` | read | the check for "is this vendor blocked from shipping" |
| `get_pricing` | `pricing` | read | unit_cost + list_price by sku |
| `get_cash_balance` | `cash_accounts` | read | balance + as-of date by account name |
| `list_payment_proposals` | `payment_proposals` | read | optional status filter |
| `update_ticket_status` | `tickets` | write | status (+ optional notes) only; touches no other table |
| `save_draft` | `drafts` | write | inserts a customer-facing draft; never sends anything |
| `propose_payment` | `payment_proposals` | write | inserts a *pending* proposal only; never touches `payments` or `cash_accounts` |
| `approve_payment` | `payment_proposals`, `payments`, `cash_accounts`, `invoices`/`leases` | write | the only tool that ever moves money; requires a human `approved_by`; refuses on insufficient funds or a non-pending proposal. **Not exposed to any agent** - see Safety below |
| `get_lease` | `leases` | read | rent, due date, last_paid by id |

`drafts` and `payment_proposals` (plus `leases.last_paid`) are small additive schema migrations applied by `mcp_server/db.py` the first time any tool connects - no existing table, column, or row is changed. Full detail and the write-tool test methodology (throwaway-copy only) are in `mcp_server/README.md`.

## The agent team (`backend/agents.py`)

Five PydanticAI agents, all on the single shared model `gpt-6-luna` (`backend/model.py`), reach every one of the tools above only through `backend/tools.py` (no agent, or any other code in `backend/`, ever imports `sqlite3` or opens a database file).

| Agent | Role | Tools it's allowed to use | Never does |
|---|---|---|---|
| **Boss** | Reads each ticket, decides who should work on it, delegates, makes the final call | `get_today`, `list_tickets`, `get_ticket`, `update_ticket_status`, `delegate_to` | Never touches inventory/cash/lease facts directly - gets them from specialists |
| **Inventory** | Checks stock by SKU/size, spots shortfalls, picks a restock vendor from `vendors.specialty` + `lead_days` (there is no formal SKU→vendor table, so this is always a stated inference, never a guaranteed link) | `get_today`, `get_ticket`, `get_inventory`, `list_vendors`, `get_invoice`, `list_open_invoices_for_vendor`, `delegate_to` | Never proposes or approves a payment |
| **Accounting** | Watches cash and invoices, checks margin with `unit_cost`/`list_price`, prepares payments or purchase orders | `get_today`, `get_ticket`, `get_cash_balance`, `get_pricing`, `get_invoice`, `list_open_invoices_for_vendor`, `list_payment_proposals`, `propose_payment`, `delegate_to` | Never approves its own proposal; never lets a proposal exceed the cash balance |
| **Facilities** | Handles leases and rent - amount, due date, overdue status | `get_today`, `get_ticket`, `get_lease`, `delegate_to` | Never proposes a payment itself - delegates that to Accounting |
| **Customer Service** | Drafts customer-facing messages | `get_today`, `get_ticket`, `save_draft`, `delegate_to` | Never sends a draft anywhere; never states a fact it didn't get from a tool or another agent |

Every agent shares one `delegate_to` tool, so any agent can hand a question to any other (full connectivity) - see Safety below for how that's kept from looping forever. Every agent returns the same structured `SpecialistReply` shape (`backend/models.py`): a plain-language summary, the real facts behind it, a recommendation, and `needs_human_approval`/`unresolved` flags.

## Safety

Guardrails a real business would want before letting agents touch real customers and real money:

- **Human approval for every payment.** `propose_payment` only ever inserts a `pending` row into `payment_proposals`; it never touches `payments` or `cash_accounts`. `approve_payment` is the only tool that can move money, it requires a non-empty human `approved_by` name, and it is **not given to any agent** - it's reserved for a human acting outside this agent system entirely.
- **Refusal on insufficient cash.** `approve_payment` computes the post-payment balance and refuses, writing nothing, if it would go negative. Cash only ever decreases - no tool in the server increases a `cash_accounts.balance`, since there's no revenue model.
- **Drafts only, never sent.** `save_draft` writes to an internal `drafts` table and nothing else. No tool in the server (or anywhere in `backend/`) sends email, calls an external API, or otherwise contacts a real person.
- **Audit trail.** Every agent-loop step - a model call, a tool call, a delegation, or a final result - is appended to `output/audit_trail.json` (`backend/audit.py`), with the agent, the ticket, the tool and arguments where relevant, a short result summary, and a timestamp. The file is read-appended-written back, never truncated, and a missing file is treated as empty. The Portkey API key is never written to it, or anywhere else - `backend/model.py` is the only place that ever reads it from `.env`.
- **No secrets in the repo.** `.env` and anything matching `*token*`/`*.key` are gitignored (project root `.gitignore`); the key is read once via `python-dotenv` and only ever passed as an HTTP auth header to Portkey.
- **Simulated clock only.** Every "is this overdue/due soon" check, in every agent and every tool, compares against `desk.date_today` via `get_today` - never the real system clock.
- **Working copy only.** Every tool connects through `mcp_server/db.py`'s `DB_PATH` (`data/campus_customs_new.db`); the original `data/campus_customs.db` is never opened.

Limits that keep token/cost use in check:

- **One shared, named model.** Every agent uses exactly `gpt-6-luna` through Portkey, built in the single shared `backend/model.py` - easy to audit that nothing else ever appears.
- **Delegation depth cap.** `TicketContext.max_depth` (default 4) - `delegate_to` refuses once a ticket's delegation chain gets this deep.
- **Delegation count cap.** `RunBudget.max_delegations` (default 6) - one shared counter per ticket across the whole delegation tree (not per agent), so a Boss→Inventory→Accounting→Boss→... cycle can't run indefinitely.
- **No self-delegation.** `delegate_to` refuses if an agent names itself as the target (Boss can't call Boss) - a real run hit this before the guard existed, wasting budget on a pointless hop.
- **Per-ticket request cap.** Whoever starts a ticket passes `usage_limits=UsageLimits(request_limit=...)` to `backend.runner.run_agent`, capping total model requests for that ticket regardless of how delegation unfolds. The dashboard's `backend/main.py` uses 40 (raised from an initial 20, which proved too tight for Boss's own closing reply after a full multi-specialist run); `backend/smoke_test.py` uses a small cap (3) since its questions are each answerable in one tool call.
- **Least-privilege tools.** Each agent only gets the MCP tools its role needs (see the table above) - e.g. Customer Service can't call `propose_payment`, so a drafting task can't accidentally also move toward a payment.
- **No unhandled background-task failures.** If a ticket's run raises (e.g. it hits the request cap), `backend/main.py`'s `_run_ticket_task` catches it - `backend.runner.run_agent` already records it as a `result` event with `error: true` - and, only if Boss never got the chance to set any status, marks the ticket `"awaiting human review"` instead of leaving it silently `"open"`.

## Ticket status: "resolved" vs. "awaiting ..."

A ticket's `resolved` flag (used by `/tickets` and the dashboard's green check/stamp) is **not** just "status changed from open." `backend/main.py`'s `_is_resolved()` treats any status starting with the word `"awaiting"` as *not* resolved - Boss is instructed (`backend/prompts/boss.md`) to always use an `"awaiting ..."` status (e.g. `"awaiting payment approval"`, `"awaiting pricing decision"`) whenever a human still needs to approve a payment or make a decision, and a non-`"awaiting"` status (e.g. `"resolved"`) only once nothing further is needed. `POST /payments/{id}/approve` marks the ticket that proposal came from `"resolved"` on success, found by scanning `output/audit_trail.json` for the `propose_payment` call that produced it (read-only; `payment_proposals` itself has no `ticket_id` column, only an invoice/lease id).

A price-override ticket should never end "awaiting" - Accounting has a standing discount floor
(never below 30% margin over `unit_cost`) *as* its policy, so Boss doesn't need a human to set a
discount cap before making a final call: fill what's actually in stock, price at or above the
floor, decline any restock the cash balance can't cover (there's no tool to action a new
purchase anyway), have Customer Service draft the reply, and mark it resolved.

Approving a payment isn't an agent action, so it wouldn't normally appear in the event feed at
all - `POST /payments/{id}/approve` deliberately also records one (`tool: "approve_payment"`,
`agent: null`), purely so a fresh dashboard load can tell a proposal was already approved and
not show it as pending again. Without this, every page reload after an approval would
incorrectly re-show that proposal's card.

## Backend API routes (`backend/main.py`)

A thin FastAPI wrapper around the same agents/tools/MCP-client code already described above - every route gets shop facts or makes shop writes only through the MCP tools, no route runs its own SQL. Run from inside `backend/` with `uvicorn main:app --reload --port 8000`.

| Method | URL | What it does |
|---|---|---|
| GET | `/tickets` | The three tickets, each with its status and whether it's genuinely resolved (see above - "awaiting ..." statuses are not resolved). |
| POST | `/tickets/{ticket_id}/run` | Starts the agent team (Boss) on that ticket in the background and returns right away; refuses if the ticket isn't `"open"` or already has a run in progress. |
| GET | `/events` | Recent agent events (agent, tool, summary) from the in-memory live feed - separate from `output/audit_trail.json`, which stays append-only on disk. Hydrated from that file on startup so a backend restart doesn't lose visibility into still-pending work. |
| POST | `/payments/{proposal_id}/approve` | Human-approves a pending payment proposal via the `approve_payment` MCP tool - the only route that can move money - and marks that proposal's ticket `"resolved"`. |
| GET | `/cash/balance` | The current `checking` account balance. |
| POST | `/reset` | Resets the working database from the untouched original and clears the in-memory event feed; never writes to the original, never touches `output/audit_trail.json`. |

CORS is open (`allow_origins=["*"]`) so a React dev server on another port can call these during local development.

## Dashboard (`frontend/`)

A React + Vite + TypeScript app (`npm run dev` from `frontend/`, served at `localhost:5173`) that calls only the six routes above - no direct database or agent-code access, and no routes beyond those six. Full visual design rationale (the navy/gold theme, per-agent colors/icons, the active/idle glow, the resolved stamp vs. the "awaiting" badge, the animated cash balance) is in `output/design.md`; this is the functional summary.

- **Tickets column** - one card per ticket from `GET /tickets`, with a "Start agent team" button that only shows while `status === "open"`. Clicking it calls `POST /tickets/{id}/run` and adds the ticket to a client-side "running" set.
- **The Desk** - one card per agent (Boss, Inventory, Accounting, Facilities, Customer Service) plus a live activity feed, built entirely by polling `GET /events` every 1.5s while any ticket is in that "running" set (and stopping once `GET /tickets` reports it resolved) - the events are accumulated client-side (not replaced) so a ticket's history survives even after the backend's recent-events buffer moves past it.
- **Pending approvals** - reconstructed from `propose_payment` tool-call events in that same accumulated stream (there is no dedicated "list pending approvals" route - see the ticket-status section above). Clicking Approve calls `POST /payments/{id}/approve`; Reject only hides the card locally, since there's no reject tool in the backend.
- **Cash panel** - `GET /cash/balance`, refreshed after every approval and animated toward the new value.
- **Reset button** - `POST /reset`, behind a confirmation dialog.
- **Resolved vs. awaiting** - a ticket card shows the green check/stamp only when `resolved: true`; a status that isn't `"open"` but also isn't resolved gets an amber "needs a human decision" badge instead (see the status-convention section above).

## Where the actual three-ticket run is recorded

Everything above describes how the system is built. What actually happened when the three tickets were run for real - which agents did what, what each one delegated, which MCP tools fired, how cash moved, and the final outcome - is recorded in:

- `output/desk_tickets.html` - the Problem 6 planning page, with an "Actual" section filled in under each ticket's "Expected" prediction so they can be compared directly.
- `output/resolved_tickets.json` - a structured per-ticket summary (status, outcome, each agent's contribution, human approvals).
- `output/resolved_board.html` - the saved dashboard screenshots for all three resolved tickets.
- `output/audit_trail.json` - the full, real, append-only event-by-event record everything else above is built from.
