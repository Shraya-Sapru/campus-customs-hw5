"""In-memory live event feed for the dashboard (Problem 7).

Separate from the on-disk, append-only output/audit_trail.json (backend/audit.py).
Agents publish the same event dicts here as they work (same call sites that call
audit.record), by putting them onto an asyncio.Queue. A background drainer task
(started in backend/main.py's lifespan) moves each one into a capped recent-events
buffer, so GET /events can read a snapshot without consuming the queue - repeated
polls all see the latest activity.
"""

import asyncio
import json
from collections import deque
from pathlib import Path

MAX_RECENT = 200

queue: asyncio.Queue = asyncio.Queue()
_recent: deque = deque(maxlen=MAX_RECENT)


def publish(event: dict) -> None:
    """Call from agent code as it works. Never blocks (the queue is unbounded)."""
    queue.put_nowait(event)


def hydrate_from_audit_trail(audit_path: Path) -> None:
    """Seed the live feed from the persistent audit trail on startup.

    This feed is pure in-process memory - restarting the backend (a code change, a
    crash, `--reload` firing) empties it, even though output/audit_trail.json and the
    database are untouched. Without this, a still-pending payment proposal from
    before the restart would silently vanish from the dashboard on the next page
    load, even though it's still genuinely pending - exactly the kind of thing this
    feed exists to surface. Call once, before the drainer starts.
    """
    if not audit_path.exists():
        return
    try:
        entries = json.loads(audit_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    _recent.extend(entries[-MAX_RECENT:])


async def drain_forever() -> None:
    """Run once as a background task for the app's lifetime (see main.py)."""
    while True:
        event = await queue.get()
        _recent.append(event)


def recent(limit: int = 50) -> list[dict]:
    """Most recent events first."""
    items = list(_recent)
    items.reverse()
    return items[:limit]


def clear() -> None:
    """Used by POST /reset - clears the live feed only, never output/audit_trail.json."""
    _recent.clear()
    while not queue.empty():
        try:
            queue.get_nowait()
        except asyncio.QueueEmpty:
            break
