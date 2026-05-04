"""
Agent State DB — Core implementation.

SQLite with WAL mode for concurrent read/write across multiple agents.
Single-file database at ~/.hermes/state/agent_state.db
"""

import json
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Optional


SCHEMA = """
CREATE TABLE IF NOT EXISTS agents (
    agent_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'interactive',  -- cron, interactive, delegated
    cron_job_id TEXT,
    metadata_json TEXT DEFAULT '{}',
    created_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL REFERENCES agents(agent_id),
    started_at TEXT NOT NULL,
    ended_at TEXT,
    status TEXT NOT NULL DEFAULT 'running',  -- running, completed, failed, interrupted
    exit_code INTEGER,
    summary TEXT,
    token_usage INTEGER DEFAULT 0,
    output_path TEXT
);

CREATE INDEX IF NOT EXISTS idx_runs_agent ON runs(agent_id);
CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
CREATE INDEX IF NOT EXISTS idx_runs_started ON runs(started_at);

CREATE TABLE IF NOT EXISTS state_kv (
    agent_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value_json TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (agent_id, key)
);

CREATE TABLE IF NOT EXISTS locks (
    resource TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    acquired_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_locks_expires ON locks(expires_at);

CREATE TABLE IF NOT EXISTS coordination (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    action TEXT NOT NULL,  -- working_on, completed, blocked_by, note
    resource TEXT NOT NULL,
    detail TEXT DEFAULT '',
    timestamp TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_coord_agent ON coordination(agent_id);
CREATE INDEX IF NOT EXISTS idx_coord_resource ON coordination(resource, timestamp DESC);

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);
"""


class AgentStateDB:
    """SQLite-backed shared state for autonomous agents."""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = os.path.expanduser("~/.hermes/state/agent_state.db")
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        with self._conn() as conn:
            conn.executescript(SCHEMA)
            conn.execute(
                "INSERT OR IGNORE INTO schema_version (version, applied_at) VALUES (1, ?)",
                (self._now(),),
            )
            conn.commit()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _uid() -> str:
        return uuid.uuid4().hex[:12]

    # ---- Agents ----

    def register_agent(
        self,
        name: str,
        type: str = "interactive",
        cron_job_id: str = None,
        metadata: dict = None,
    ) -> dict:
        """Register or update an agent. If name exists, updates last_seen."""
        agent_id = self._uid()
        now = self._now()
        meta_json = json.dumps(metadata or {})

        with self._conn() as conn:
            # Check if agent with this name already exists
            existing = conn.execute(
                "SELECT agent_id FROM agents WHERE name = ?", (name,)
            ).fetchone()
            if existing:
                conn.execute(
                    """UPDATE agents SET last_seen_at = ?, metadata_json = ?, cron_job_id = ?,
                       type = ? WHERE agent_id = ?""",
                    (now, meta_json, cron_job_id, type, existing["agent_id"]),
                )
                conn.commit()
                return self.get_agent(existing["agent_id"])

            conn.execute(
                """INSERT INTO agents (agent_id, name, type, cron_job_id, metadata_json, created_at, last_seen_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (agent_id, name, type, cron_job_id, meta_json, now, now),
            )
            conn.commit()
        return self.get_agent(agent_id)

    def get_agent(self, agent_id: str) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM agents WHERE agent_id = ?", (agent_id,)
            ).fetchone()
        return dict(row) if row else None

    def get_agent_by_name(self, name: str) -> Optional[dict]:
        """Look up an agent by name (used by Cron Guard for cron_job_id lookup)."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM agents WHERE name = ?", (name,)
            ).fetchone()
        return dict(row) if row else None

    def get_agent_by_cron_job_id(self, cron_job_id: str) -> Optional[dict]:
        """Look up an agent by cron_job_id."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM agents WHERE cron_job_id = ?", (cron_job_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_agents(self, type: str = None) -> list[dict]:
        with self._conn() as conn:
            if type:
                rows = conn.execute(
                    "SELECT * FROM agents WHERE type = ? ORDER BY last_seen_at DESC",
                    (type,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM agents ORDER BY last_seen_at DESC"
                ).fetchall()
        return [dict(r) for r in rows]

    def heartbeat(self, agent_id: str):
        with self._conn() as conn:
            conn.execute(
                "UPDATE agents SET last_seen_at = ? WHERE agent_id = ?",
                (self._now(), agent_id),
            )
            conn.commit()

    # ---- Runs ----

    def start_run(self, agent_id: str, output_path: str = None) -> str:
        run_id = self._uid()
        now = self._now()
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO runs (run_id, agent_id, started_at, status, output_path)
                   VALUES (?, ?, ?, 'running', ?)""",
                (run_id, agent_id, now, output_path),
            )
            conn.commit()
            # Update agent last_seen
            self.heartbeat(agent_id)
        return run_id

    def finish_run(
        self,
        run_id: str,
        status: str = "completed",
        exit_code: int = 0,
        summary: str = None,
        token_usage: int = 0,
    ):
        now = self._now()
        with self._conn() as conn:
            conn.execute(
                """UPDATE runs SET ended_at = ?, status = ?, exit_code = ?,
                   summary = ?, token_usage = ? WHERE run_id = ?""",
                (now, status, exit_code, summary, token_usage, run_id),
            )
            conn.commit()

    def cleanup_stale_runs(self, timeout_hours: int = 24) -> int:
        """Mark runs still 'running' after timeout_hours as 'interrupted'.
        Returns count of cleaned runs."""
        now = self._now()
        with self._conn() as conn:
            cursor = conn.execute(
                """UPDATE runs SET status = 'interrupted', ended_at = ?
                   WHERE status = 'running'
                   AND datetime(started_at) < datetime(?, ?)""",
                (now, now, f'-{timeout_hours} hours'),
            )
            conn.commit()
            return cursor.rowcount

    def get_run(self, run_id: str) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_runs(
        self, agent_id: str = None, status: str = None, limit: int = 50
    ) -> list[dict]:
        with self._conn() as conn:
            conditions = []
            params = []
            if agent_id:
                conditions.append("agent_id = ?")
                params.append(agent_id)
            if status:
                conditions.append("status = ?")
                params.append(status)
            where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            rows = conn.execute(
                f"SELECT * FROM runs {where} ORDER BY started_at DESC LIMIT ?",
                params + [limit],
            ).fetchall()
        return [dict(r) for r in rows]

    def get_recent_failures(self, agent_id: str, count: int = 3) -> int:
        """Count recent consecutive failures for an agent."""
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT status FROM runs WHERE agent_id = ?
                   ORDER BY started_at DESC LIMIT ?""",
                (agent_id, count),
            ).fetchall()
        failures = 0
        for r in rows:
            if r["status"] == "failed":
                failures += 1
            else:
                break  # Stop at first non-failure (non-consecutive)
        return failures

    # ---- State KV (versioned key-value store) ----

    def get_state(self, agent_id: str, key: str) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM state_kv WHERE agent_id = ? AND key = ?",
                (agent_id, key),
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["value"] = json.loads(d["value_json"])
        del d["value_json"]
        return d

    def set_state(self, agent_id: str, key: str, value: Any) -> int:
        """Set state. Returns new version number. Uses atomic upsert (no race condition)."""
        now = self._now()
        value_json = json.dumps(value)
        with self._conn() as conn:
            cursor = conn.execute(
                """INSERT INTO state_kv (agent_id, key, value_json, version, updated_at)
                   VALUES (?, ?, ?, 1, ?)
                   ON CONFLICT(agent_id, key) DO UPDATE SET
                       value_json = excluded.value_json,
                       version = version + 1,
                       updated_at = excluded.updated_at
                   RETURNING version""",
                (agent_id, key, value_json, now),
            )
            version = cursor.fetchone()["version"]
            conn.commit()
            return version

    def list_state(self, agent_id: str, prefix: str = None) -> list[dict]:
        with self._conn() as conn:
            if prefix:
                rows = conn.execute(
                    "SELECT agent_id, key, version, updated_at FROM state_kv WHERE agent_id = ? AND key LIKE ? ORDER BY key",
                    (agent_id, f"{prefix}%"),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT agent_id, key, version, updated_at FROM state_kv WHERE agent_id = ? ORDER BY key",
                    (agent_id,),
                ).fetchall()
        return [dict(r) for r in rows]

    # ---- Locks (advisory, resource-level) ----

    def acquire_lock(
        self, resource: str, agent_id: str, ttl_seconds: int = 300
    ) -> bool:
        """Try to acquire an advisory lock. Returns True if acquired."""
        now = self._now()
        expires = datetime.now(timezone.utc).isoformat()
        # Calculate expires_at properly
        from datetime import timedelta
        expires_dt = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        expires = expires_dt.isoformat()

        with self._conn() as conn:
            # Clean expired locks first
            conn.execute("DELETE FROM locks WHERE expires_at < ?", (now,))
            # Try insert — will fail if resource is still locked
            try:
                conn.execute(
                    """INSERT INTO locks (resource, agent_id, acquired_at, expires_at)
                       VALUES (?, ?, ?, ?)""",
                    (resource, agent_id, now, expires),
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def release_lock(self, resource: str, agent_id: str) -> bool:
        with self._conn() as conn:
            cursor = conn.execute(
                "DELETE FROM locks WHERE resource = ? AND agent_id = ?",
                (resource, agent_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def check_lock(self, resource: str) -> Optional[dict]:
        """Check if a resource is locked (and by whom). Expired locks auto-cleaned."""
        now = self._now()
        with self._conn() as conn:
            conn.execute("DELETE FROM locks WHERE expires_at < ?", (now,))
            conn.commit()
            row = conn.execute(
                "SELECT * FROM locks WHERE resource = ?", (resource,)
            ).fetchone()
        return dict(row) if row else None

    # ---- Coordination ----

    def coordinate(
        self,
        agent_id: str,
        action: str,
        resource: str,
        detail: str = "",
    ) -> int:
        """Post a coordination message (working_on, completed, blocked_by, note)."""
        now = self._now()
        with self._conn() as conn:
            cursor = conn.execute(
                """INSERT INTO coordination (agent_id, action, resource, detail, timestamp)
                   VALUES (?, ?, ?, ?, ?)""",
                (agent_id, action, resource, detail, now),
            )
            conn.commit()
            return cursor.lastrowid

    def check_coordination(
        self, resource: str, limit: int = 10
    ) -> list[dict]:
        """See who's working on a resource. Most recent first."""
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT c.*, a.name as agent_name FROM coordination c
                   JOIN agents a ON c.agent_id = a.agent_id
                   WHERE c.resource = ?
                   ORDER BY c.timestamp DESC LIMIT ?""",
                (resource, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def recent_activity(self, limit: int = 20) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT c.*, a.name as agent_name FROM coordination c
                   JOIN agents a ON c.agent_id = a.agent_id
                   ORDER BY c.timestamp DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ---- Stats ----

    def stats(self) -> dict:
        with self._conn() as conn:
            agent_count = conn.execute("SELECT COUNT(*) FROM agents").fetchone()[0]
            run_count = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
            active_runs = conn.execute(
                "SELECT COUNT(*) FROM runs WHERE status = 'running'"
            ).fetchone()[0]
            failed_runs = conn.execute(
                "SELECT COUNT(*) FROM runs WHERE status = 'failed'"
            ).fetchone()[0]
            lock_count = conn.execute(
                "SELECT COUNT(*) FROM locks WHERE expires_at > ?", (self._now(),)
            ).fetchone()[0]
        return {
            "agents": agent_count,
            "runs_total": run_count,
            "runs_active": active_runs,
            "runs_failed": failed_runs,
            "active_locks": lock_count,
            "db_path": self.db_path,
        }
