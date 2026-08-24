import os

import aiosqlite
import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    start_time TEXT NOT NULL,          -- ISO8601 UTC
    end_time TEXT NOT NULL,            -- ISO8601 UTC
    status TEXT NOT NULL DEFAULT 'applied',   -- applied | deleted

    reminder_hour_sent INTEGER NOT NULL DEFAULT 0,

    start_prompt_sent INTEGER NOT NULL DEFAULT 0,
    start_prompt_sent_at TEXT,
    last_start_reminder_at TEXT,
    escalation_sent INTEGER NOT NULL DEFAULT 0,
    reminders_stopped INTEGER NOT NULL DEFAULT 0,
    started_at TEXT,

    end_prompt_sent INTEGER NOT NULL DEFAULT 0,
    ended_at TEXT,

    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pending_edits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,              -- create | edit | delete
    schedule_id INTEGER,               -- NULL for 'create'
    user_id TEXT NOT NULL,
    start_time TEXT,
    end_time TEXT,
    created_by TEXT,
    created_at TEXT NOT NULL
);
"""

_db: aiosqlite.Connection | None = None


async def init_db() -> aiosqlite.Connection:
    global _db
    db_dir = os.path.dirname(config.DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    _db = await aiosqlite.connect(config.DB_PATH)
    _db.row_factory = aiosqlite.Row
    await _db.executescript(SCHEMA)
    await _db.commit()
    return _db


def get_db() -> aiosqlite.Connection:
    if _db is None:
        raise RuntimeError("Database has not been initialized yet.")
    return _db
