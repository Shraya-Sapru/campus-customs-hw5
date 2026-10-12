# Campus Customs — Dashboard Design (Problem 8)

`frontend/` is a React + Vite + TypeScript app that talks only to the six routes in
`backend/main.py` (`GET /tickets`, `POST /tickets/{id}/run`, `GET /events`,
`POST /payments/{id}/approve`, `GET /cash/balance`, `POST /reset`) — nothing invents
a new backend endpoint, and nothing touches the database or agent code directly.

## Layout: three columns

**Left — Tickets.** One card per ticket (101/102/103), each with its subject, requester,
SKU/qty if relevant, current status, and a "Start agent team" button. This is the inbox:
you start here, pick a ticket, and the rest of the board follows it.

**Center — The Desk.** Five agent cards in a fixed grid (Boss, Inventory, Accounting,
Facilities, Customer Service) so the whole team is always visible, whether or not
they're doing anything — the dashboard should look like an actual office with everyone
at their desk, not a list that appears and disappears. Below the cards, a live Activity
feed scoped to whichever ticket is selected.

**Right — Cash + Approvals.** The checking balance up top (the number everything else
ultimately protects), and pending payment approvals below it, closest to the balance
they're about to change.

This ordering mirrors the actual workflow: pick a ticket (left) → watch the team work it
(center) → decide on money (right).

## How each agent "reads" differently

Every agent has a fixed icon, color, and label (`frontend/src/constants.ts`) that's used
consistently everywhere it appears — the agent card, the activity feed icon, the ticket's
expanded per-agent summary:

- Boss — 👑, gold (the desk owner, using the theme's signature color)
- Inventory — 📦, teal
- Accounting — 💰, green (money)
- Facilities — 🏢, amber (building/lease)
- Customer Service — 💬, blue-violet (conversation)

**Active vs. idle** is the main piece of "life" in the desk: while a ticket is running,
whichever agent produced the most recent event gets its card lit at full opacity, a
colored glow in its own color, and a small pulsing dot — every other card dims to ~55%
opacity. This single-active-agent model is a deliberate simplification: the backend can
technically have a delegation chain in flight, but showing one agent "with the ball" at a
time reads much more clearly than trying to show concurrent activity that, in practice,
isn't actually concurrent (the whole agent loop is sequential).

**Delegations** show up as short arrow lines in the Activity feed - "Boss → Accounting" -
built directly from the backend's `delegation` event type (`agent` is the source,
`arguments.target_agent` is the destination). They're interleaved chronologically with
tool-call and result lines rather than kept in a separate panel, since seeing the order
things happened in is part of what makes the desk feel alive.

**Per-agent summaries** on a resolved ticket come from each agent's final `result` event
for that ticket (`SpecialistReply.summary`, the same plain-language field the backend
already produces) - no extra text is generated client-side.

## How resolved tickets show up

A ticket card is actually one of three states, not two - `"open"`, genuinely resolved, or
resolved-by-Boss-but-still-waiting-on-a-human (revised after the first version of this
dashboard showed the same green "RESOLVED" stamp on a ticket that was really just waiting
on a payment approval, which was misleading). The backend decides which: any status
starting with `"awaiting"` is not resolved, no matter how far Boss got.

**Genuinely resolved** (status doesn't start with `"awaiting"`) gets:
- A green ✓ next to its type label.
- A rotated "RESOLVED" stamp in the corner, styled like an ink stamp (border only, no
  fill, slightly transparent) rather than a solid badge, to read as "stamped" rather than
  "flagged."

**Awaiting a human** (status starts with `"awaiting"`, e.g. `"awaiting payment approval"`)
gets its own amber badge - "⏳ Needs a human decision" - instead of the green stamp, so it
reads as "Boss finished triaging, but this isn't done" rather than "nothing left to do."

Both non-`"open"` states share the rest: the "Start agent team" button disappears (gated on
`status === "open"`, not on `resolved`, so it also stays hidden while awaiting approval -
re-running isn't appropriate until a human decides the payment), and the collapsed
`<details>` "What each agent did" section is available either way, since Boss and the
specialists already did real work worth showing.

An "awaiting" ticket becomes genuinely resolved automatically once its payment is approved
(`POST /payments/{id}/approve` marks the ticket resolved on success) - no separate action
needed. A ticket like #103, whose outcome is a pricing/policy call rather than a payment,
has no such automatic path yet, since there's no route for a human to record a non-payment
decision - see `output/harness.md`'s ticket-status section and the Problem 9 investigation
notes in `AI_prompts.md` for why, and what I think its eventual resolved state should be.

## How cash shows up

The balance is the single largest piece of text on the page (40px, gold, tabular
numerals so the digits don't jitter as they change) - it's the thing the whole approval
flow exists to protect, so it should look like the most important number in the room.

When a payment is approved, the balance doesn't jump - it tweens from the old value to
the new one over ~800ms (ease-out cubic, via `requestAnimationFrame`) and turns red for
the duration of the drop before settling back to gold. This is the one explicit "cash
moved" moment in the UI.

## Payment approval cards

Each pending approval is read directly out of the event stream: when Accounting's
`propose_payment` tool call appears, its JSON result (id, kind, ref_id, amount, account,
reason, proposed_by) is parsed out of that event's summary and turned into a card. This
keeps the frontend honest about "only through MCP tools" - there's no separate backend
route for listing proposals, so the dashboard reconstructs the pending list itself from
the same events everything else is built from.

**Design tradeoff on "payee":** the proposal only carries `kind` + `ref_id` (an invoice
or lease id), not a resolved vendor/landlord name - there's no `/invoices` or `/vendors`
route exposed, and adding one would mean changing the backend, which was out of scope.
So the card shows the reference plainly ("Invoice #501" / "Lease #1") and surfaces
Accounting's own `reason` text underneath, which is where a human-readable description
(generally including the vendor's name) actually lives. "Balance after paying" is
computed client-side as `current balance − amount`, since both numbers are already on
screen.

**Design tradeoff on "Reject":** there's no reject tool in the backend - once proposed, a
proposal is either approved or stays pending forever. So Reject is a local-only dismiss
(hides the card from this dashboard) and says so directly on the card, rather than
pretending it cancels anything server-side.

## Live updates without over-polling

- A 5-second heartbeat always refreshes tickets and the balance - this is also how the
  "backend offline" banner gets triggered/cleared, since a network-level fetch failure
  flips it on and the next successful heartbeat flips it back off automatically.
- A 1.5-second poll of `/events` (plus tickets/balance) runs only while at least one
  ticket is in the client's "running" set, and that set is pruned the moment `/tickets`
  reports a ticket resolved - so polling actually stops, as asked, instead of just
  slowing down.
- Events are accumulated client-side (not replaced) using each event's timestamp to
  only append what's new, so a ticket's summaries and activity history survive even
  after the backend's own recent-events buffer scrolls past them.

## Small touches

- A pulsing green dot next to "Live" in the header while something is running, so the
  header itself hints that the desk is busy before you even look at the columns.
- The Activity feed's new lines fade/slide in instead of popping in instantly.
- Pending approval cards get a slow gold pulse border - the one thing on the board that's
  deliberately trying to catch your eye, since it's the one thing that needs a human.
- Hovering a ticket card lifts it slightly - a small nod to it being a physical card on a
  desk.
- The offline banner uses the shop metaphor ("The desk is quiet...") instead of a generic
  network-error string, to stay in character with the rest of the UI's voice.
- The header's shop icon (🧥) and "Back Office Desk" subtitle exist purely to make the
  tab feel like a real internal tool rather than a generic admin panel.

## What wasn't tested live

Per your instructions, I didn't run the agent team on a ticket or approve/reject a
payment against the real backend - so the "while it runs" activity view, the resolved
stamp/summary, and the approval card are built and reviewed against the exact event
shapes the backend produces, but not yet exercised end-to-end with a real run. Everything
else (ticket list, balance, offline detection/recovery, the reset confirmation flow
without actually resetting, and the TypeScript build) was verified live.
