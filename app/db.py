import sqlite3
import json
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path(__file__).parent.parent / "data" / "crm.db"


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_conn():
    conn = _connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                email TEXT,
                company TEXT,
                need TEXT,
                stage TEXT DEFAULT 'new',
                assigned_to TEXT,
                summary TEXT,
                next_action TEXT,
                source TEXT,
                created_at TEXT,
                updated_at TEXT,
                last_contacted_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                event_type TEXT,
                customer_id INTEGER,
                detail TEXT,
                status TEXT
            )
        """)


def log_event(event_type: str, customer_id: int | None, detail: dict, status: str = "success"):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO audit_log (timestamp, event_type, customer_id, detail, status) "
            "VALUES (?, ?, ?, ?, ?)",
            (datetime.utcnow().isoformat(), event_type, customer_id, json.dumps(detail), status),
        )


def find_duplicate(email: str | None, name: str | None):
    """Very simple dedupe: exact email match first, then exact name match."""
    if not email and not name:
        return None
    with get_conn() as conn:
        if email:
            row = conn.execute(
                "SELECT * FROM customers WHERE email = ? COLLATE NOCASE", (email,)
            ).fetchone()
            if row:
                return dict(row)
        if name:
            row = conn.execute(
                "SELECT * FROM customers WHERE name = ? COLLATE NOCASE", (name,)
            ).fetchone()
            if row:
                return dict(row)
    return None


def create_customer(fields: dict) -> int:
    now = datetime.utcnow().isoformat()
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO customers
               (name, email, company, need, stage, assigned_to, summary, next_action,
                source, created_at, updated_at, last_contacted_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                fields.get("name"), fields.get("email"), fields.get("company"),
                fields.get("need"), fields.get("stage", "new"), fields.get("assigned_to"),
                fields.get("summary"), fields.get("next_action"), fields.get("source"),
                now, now, now,
            ),
        )
        return cur.lastrowid


def update_customer(customer_id: int, fields: dict):
    fields = dict(fields)
    fields["updated_at"] = datetime.utcnow().isoformat()
    columns = ", ".join(f"{k} = ?" for k in fields)
    with get_conn() as conn:
        conn.execute(
            f"UPDATE customers SET {columns} WHERE id = ?",
            (*fields.values(), customer_id),
        )


def get_customer(customer_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
        return dict(row) if row else None


def list_customers():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM customers ORDER BY updated_at DESC").fetchall()
        return [dict(r) for r in rows]


def list_audit_log(limit: int = 200):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def overdue_customers(threshold_days: int):
    """Customers with no contact/update in >= threshold_days, not yet closed."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT * FROM customers
               WHERE stage NOT IN ('closed_won', 'closed_lost')
               AND julianday('now') - julianday(last_contacted_at) >= ?""",
            (threshold_days,),
        ).fetchall()
        return [dict(r) for r in rows]
