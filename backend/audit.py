"""Append-only audit trail at output/audit_trail.json.

Every agent-loop step - a model call, a tool call, a delegation, or a final result - goes
through record() below. The file is read, the new event appended, and the whole list written
back; existing events are never dropped or cleared, and a missing file is treated as an empty
list. Events only ever contain shop data (ticket ids, tool names/arguments, reply summaries) -
never the Portkey API key or any other secret, since nothing in backend/ ever reads the key
outside of backend/model.py.
"""

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

AUDIT_PATH = Path(__file__).resolve().parents[1] / "output" / "audit_trail.json"

_lock = threading.Lock()


def _read_existing() -> list[dict]:
    if not AUDIT_PATH.exists():
        return []
    text = AUDIT_PATH.read_text(encoding="utf-8").strip()
    if not text:
        return []
    return json.loads(text)


def summarize(value: Any, limit: int = 2000) -> str:
    """A short, plain string for the audit log - never the raw secret-bearing objects.

    Dict/list values are JSON-dumped first. The limit is generous (not a tight "short
    summary" length) because the dashboard's live feed (backend/events.py) parses this
    same string back out as JSON for things like a propose_payment result - a limit
    that's too tight truncates mid-object and produces invalid JSON. 300 was too tight
    in practice (a normal propose_payment result with a real `reason` string exceeded
    it); the frontend no longer depends solely on this parsing cleanly, but there's no
    reason to truncate aggressively either.
    """
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def record(event: dict) -> dict:
    """Append one audit event: {agent, ticket_id, step, tool, arguments, summary, ...}.

    Returns the finalized entry (with its timestamp attached) so callers can also hand
    it to backend.events.publish() for the live dashboard feed - this module has no
    dependency on that feed itself, callers wire the two together.
    """
    entry = {"timestamp": datetime.now(timezone.utc).isoformat(), **event}
    with _lock:
        existing = _read_existing()
        existing.append(entry)
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        AUDIT_PATH.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    return entry
