"""
Database module for the Online Leave Management System.

Provides connection management, schema initialization, and a standalone
initializer that works without a Flask application context.
"""

import os
import sqlite3

from flask import current_app, g

# ── Default database path (project directory) ────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DATABASE = os.path.join(BASE_DIR, 'leave_management.db')

# ── Schema definition ────────────────────────────────────────
SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name       TEXT    NOT NULL,
    email           TEXT    NOT NULL UNIQUE,
    password_hash   TEXT    NOT NULL,
    role            TEXT    NOT NULL CHECK(role IN ('faculty', 'hod')),
    leave_allowance INTEGER NOT NULL DEFAULT 12,
    created_at      TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS leave_requests (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    faculty_id      INTEGER NOT NULL,
    start_date      TEXT    NOT NULL,
    end_date        TEXT    NOT NULL,
    days            INTEGER NOT NULL CHECK(days > 0),
    leave_type      TEXT    NOT NULL CHECK(leave_type IN ('Casual Leave', 'Sick Leave', 'Earned Leave')),
    reason          TEXT    NOT NULL,
    status          TEXT    NOT NULL DEFAULT 'Pending' CHECK(status IN ('Pending', 'Approved', 'Rejected')),
    hod_remarks     TEXT    DEFAULT '',
    created_at      TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reviewed_at     TEXT,
    FOREIGN KEY (faculty_id) REFERENCES users(id),
    CHECK(end_date >= start_date)
);

CREATE INDEX IF NOT EXISTS idx_leave_requests_faculty_id ON leave_requests(faculty_id);
CREATE INDEX IF NOT EXISTS idx_leave_requests_status     ON leave_requests(status);
"""


def _get_db_path():
    """Return the database path from Flask config or the default."""
    try:
        return current_app.config['DATABASE']
    except (RuntimeError, KeyError):
        return DEFAULT_DATABASE


def get_db():
    """
    Return a database connection for the current Flask request.

    Uses autocommit mode (isolation_level=None) so that:
      - Single statements commit immediately.
      - Multi-statement transactions are managed explicitly with
        BEGIN IMMEDIATE / COMMIT / ROLLBACK.
    """
    if 'db' not in g:
        g.db = sqlite3.connect(_get_db_path(), isolation_level=None)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON')
    return g.db


def close_db(e=None):
    """Close the database connection at the end of a request."""
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    """Create tables if they do not exist (requires Flask app context)."""
    db = get_db()
    db.executescript(SCHEMA)


def init_db_standalone(db_path=None):
    """Create tables without requiring a Flask application context."""
    path = db_path or DEFAULT_DATABASE
    conn = sqlite3.connect(path)
    conn.execute('PRAGMA foreign_keys = ON')
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    return path
