import os
from pathlib import Path

_DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "campus_customs_new.db"

# Override only used by the throwaway-copy test harness; production always uses the default.
DB_PATH = Path(os.environ["CAMPUS_CUSTOMS_DB_PATH"]) if os.environ.get("CAMPUS_CUSTOMS_DB_PATH") else _DEFAULT_DB_PATH


def ensure_schema(con) -> None:
    """Additive, idempotent schema setup for tables/columns this project needs that
    the original database doesn't have. Never touches existing rows or columns."""
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS drafts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS payment_proposals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL,
            ref_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            account TEXT NOT NULL,
            reason TEXT,
            proposed_by TEXT NOT NULL,
            proposed_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            approved_by TEXT,
            approved_at TEXT
        )
        """
    )
    existing_lease_cols = {row[1] for row in con.execute("PRAGMA table_info(leases)")}
    if "last_paid" not in existing_lease_cols:
        con.execute("ALTER TABLE leases ADD COLUMN last_paid TEXT")
    con.commit()
