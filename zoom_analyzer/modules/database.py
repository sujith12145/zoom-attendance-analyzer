"""
Module: database.py
====================
SQLite-based persistence layer:
  • Store / retrieve master-list
  • Append / fetch attendance records
  • Manage class metadata
  • CSV backup utilities
"""

import sqlite3
import pandas as pd
import os
from datetime import datetime

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH, CSV_BACKUP


# ─────────────────────────────────────────────────────────────────────────────
# Schema
# ─────────────────────────────────────────────────────────────────────────────

DDL = """
CREATE TABLE IF NOT EXISTS master_students (
    roll_number  TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    name_clean   TEXT
);

CREATE TABLE IF NOT EXISTS classes (
    class_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    class_name  TEXT    NOT NULL,
    class_date  TEXT    NOT NULL,
    subject     TEXT,
    notes       TEXT,
    created_at  TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS attendance (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    class_id         INTEGER NOT NULL REFERENCES classes(class_id),
    roll_number      TEXT    NOT NULL,
    name             TEXT,
    total_minutes    REAL    DEFAULT 0,
    sessions         INTEGER DEFAULT 0,
    status           TEXT    NOT NULL,  -- Present | Absent | Unmatched
    match_method     TEXT,
    match_score      REAL,
    min_duration_used REAL,
    UNIQUE (class_id, roll_number)
);

CREATE INDEX IF NOT EXISTS idx_att_roll  ON attendance(roll_number);
CREATE INDEX IF NOT EXISTS idx_att_class ON attendance(class_id);
"""


# ─────────────────────────────────────────────────────────────────────────────
# Connection helper
# ─────────────────────────────────────────────────────────────────────────────

def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.executescript(DDL)
    conn.commit()
    return conn


# ─────────────────────────────────────────────────────────────────────────────
# Master list CRUD
# ─────────────────────────────────────────────────────────────────────────────

def save_master_list(df: pd.DataFrame) -> int:
    """Replace the master_students table with the provided DataFrame."""
    with _get_conn() as conn:
        conn.execute("DELETE FROM master_students")
        df[['roll_number', 'name', 'name_clean']].to_sql(
            'master_students', conn, if_exists='append', index=False
        )
    return len(df)


def load_master_list_db() -> pd.DataFrame:
    """Return master student list from DB, or empty DataFrame."""
    with _get_conn() as conn:
        return pd.read_sql("SELECT roll_number, name, name_clean FROM master_students", conn)


def master_list_exists() -> bool:
    with _get_conn() as conn:
        n = conn.execute("SELECT COUNT(*) FROM master_students").fetchone()[0]
    return n > 0


# ─────────────────────────────────────────────────────────────────────────────
# Class metadata CRUD
# ─────────────────────────────────────────────────────────────────────────────

def insert_class(class_name: str, class_date: str, subject: str = '', notes: str = '') -> int:
    """Insert a new class record; return its class_id."""
    with _get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO classes (class_name, class_date, subject, notes) VALUES (?,?,?,?)",
            (class_name, class_date, subject, notes)
        )
        return cur.lastrowid


def get_all_classes() -> pd.DataFrame:
    with _get_conn() as conn:
        return pd.read_sql(
            "SELECT class_id, class_name, class_date, subject, notes, created_at "
            "FROM classes ORDER BY class_date DESC",
            conn
        )


def delete_class(class_id: int) -> None:
    """Delete a class and its attendance records."""
    with _get_conn() as conn:
        conn.execute("DELETE FROM attendance WHERE class_id=?", (class_id,))
        conn.execute("DELETE FROM classes WHERE class_id=?", (class_id,))


def class_exists(class_name: str, class_date: str) -> bool:
    with _get_conn() as conn:
        n = conn.execute(
            "SELECT COUNT(*) FROM classes WHERE class_name=? AND class_date=?",
            (class_name, class_date)
        ).fetchone()[0]
    return n > 0


def get_class_id(class_name: str, class_date: str) -> int | None:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT class_id FROM classes WHERE class_name=? AND class_date=?",
            (class_name, class_date)
        ).fetchone()
    return row['class_id'] if row else None


# ─────────────────────────────────────────────────────────────────────────────
# Attendance CRUD
# ─────────────────────────────────────────────────────────────────────────────

def save_attendance(attendance_df: pd.DataFrame, class_id: int) -> int:
    """
    Upsert attendance rows for a given class_id.
    Returns number of rows saved.
    """
    rows = []
    for _, r in attendance_df.iterrows():
        rows.append((
            class_id,
            str(r.get('roll_number', '')),
            str(r.get('name', '')),
            float(r.get('total_minutes', 0)),
            int(r.get('sessions', 0)),
            str(r.get('status', 'Absent')),
            str(r.get('match_method', '')),
            float(r.get('match_score', 0)),
            float(r.get('min_duration_used', 0)),
        ))

    with _get_conn() as conn:
        conn.executemany(
            """INSERT OR REPLACE INTO attendance
               (class_id, roll_number, name, total_minutes, sessions, status,
                match_method, match_score, min_duration_used)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            rows
        )
    return len(rows)


def load_attendance(class_id: int | None = None) -> pd.DataFrame:
    """
    Load attendance joined with class metadata.
    If class_id is given, filter to that class only.
    """
    query = """
        SELECT
            a.id, a.class_id, c.class_name, c.class_date, c.subject,
            a.roll_number, a.name,
            a.total_minutes, a.sessions, a.status,
            a.match_method, a.match_score, a.min_duration_used
        FROM attendance a
        JOIN classes c ON a.class_id = c.class_id
    """
    params: list = []
    if class_id is not None:
        query += " WHERE a.class_id = ?"
        params.append(class_id)
    query += " ORDER BY c.class_date DESC, a.roll_number"

    with _get_conn() as conn:
        return pd.read_sql(query, conn, params=params)


def load_full_history() -> pd.DataFrame:
    """Return all attendance records joined with class info."""
    return load_attendance(class_id=None)


def get_attendance_summary() -> dict:
    """Return high-level counts for the dashboard."""
    with _get_conn() as conn:
        total_students = conn.execute("SELECT COUNT(*) FROM master_students").fetchone()[0]
        total_classes  = conn.execute("SELECT COUNT(*) FROM classes").fetchone()[0]
        total_records  = conn.execute(
            "SELECT COUNT(*) FROM attendance WHERE status IN ('Present','Absent')"
        ).fetchone()[0]
        present_records = conn.execute(
            "SELECT COUNT(*) FROM attendance WHERE status='Present'"
        ).fetchone()[0]
    avg_pct = round(present_records / total_records * 100, 1) if total_records else 0
    return {
        'total_students': total_students,
        'total_classes':  total_classes,
        'total_records':  total_records,
        'present_records': present_records,
        'avg_attendance_pct': avg_pct,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Backup helpers
# ─────────────────────────────────────────────────────────────────────────────

def export_csv_backup() -> str:
    """Export full history to CSV; return path."""
    df = load_full_history()
    df.to_csv(CSV_BACKUP, index=False)
    return CSV_BACKUP


def reset_database() -> None:
    """Drop and recreate all tables (destructive!)."""
    with _get_conn() as conn:
        conn.executescript("""
            DROP TABLE IF EXISTS attendance;
            DROP TABLE IF EXISTS classes;
            DROP TABLE IF EXISTS master_students;
        """)
        conn.executescript(DDL)
