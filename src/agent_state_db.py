#!/usr/bin/env python3.11
"""
Agent State DB — SQLite shared state service for Hermes autonomous agents.

WAL-mode SQLite with busy timeout. Zero dependencies beyond Python stdlib.
Concurrent reads + single writer. Application-level resource locking.

Location: ~/.hermes/state/agent_state.db (auto-created on first use)
Module:  ~/.hermes/scripts/agent_state_db.py

Usage:
    from agent_state_db import AgentStateDB
    db = AgentStateDB()
    db.register_agent("cron_123", "Nightly Review", "cron")
    session_id = db.start_session("cron_123")
    # ... do work ...
    db.end_session(session_id, "ok", summary="Reviewed 45 web parts")
"""

import json
import os
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from threading import Lock as ThreadLock


DB_PATH = Path.home() / ".hermes" / "state" / "agent_state.db"


class AgentStateDB:
    """Singleton-ish SQLite state store for agent coordination."""

    def __init__(self, db_path: Optional[Path] = None):
        self._path = Path(db_path) if db_path else DB_PATH
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._init_lock = ThreadLock()
        self._init_db()

    # ── internal ──────────────────────────────────────────────

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._path), timeout=5)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._init_lock:
            conn = self._conn()
            try:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS agents (
                        agent_id    TEXT PRIMARY KEY,
                        name        TEXT NOT NULL,
                        type        TEXT NOT NULL DEFAULT 'cron',
                        created_at  TEXT NOT NULL,
                        last_active_at TEXT,
                        metadata    TEXT DEFAULT '{}'
                    );
                    CREATE TABLE IF NOT EXISTS sessions (
                        session_id  TEXT PRIMARY KEY,
                        agent_id    TEXT NOT NULL REFERENCES agents(agent_id),
                        started_at  TEXT NOT NULL,
                        ended_at    TEXT,
                        status      TEXT NOT NULL DEFAULT 'running',
                        summary     TEXT,
                        error_detail TEXT
                    );
                    CREATE TABLE IF NOT EXISTS locks (
                        resource_path TEXT PRIMARY KEY,
                        agent_id      TEXT NOT NULL,
                        acquired_at   TEXT NOT NULL,
                        intent        TEXT NOT NULL DEFAULT 'write',
                        expires_at    TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS journal (
                        id          INTEGER PRIMARY KEY AUTOINCREMENT,
                        agent_id    TEXT NOT NULL,
                        session_id  TEXT,
                        timestamp   TEXT NOT NULL,
                        category    TEXT NOT NULL,
                        content     TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS state (
                        agent_id    TEXT NOT NULL,
                        key         TEXT NOT NULL,
                        value       TEXT NOT NULL DEFAULT 'null',
                        updated_at  TEXT NOT NULL,
                        PRIMARY KEY (agent_id, key)
                    );
                """)
                # Indexes
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_sessions_agent
                    ON sessions(agent_id, started_at DESC)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_journal_agent
                    ON journal(agent_id, category, timestamp DESC)
                """)
                conn.commit()
            finally:
                conn.close()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    # ── Agent Registration ───────────────────────────────────

    def register_agent(self, agent_id: str, name: str,
                       agent_type: str = "cron",
                       metadata: Optional[dict] = None) -> bool:
        """Register or update an agent. Returns True if newly created."""
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT agent_id FROM agents WHERE agent_id = ?", (agent_id,)
            ).fetchone()
            if existing:
                conn.execute(
                    """UPDATE agents SET name=?, type=?, last_active_at=?, metadata=?
                       WHERE agent_id=?""",
                    (name, agent_type, self._now(),
                     json.dumps(metadata or {}), agent_id))
                conn.commit()
                return False
            else:
                conn.execute(
                    """INSERT INTO agents (agent_id, name, type, created_at,
                       last_active_at, metadata)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (agent_id, name, agent_type, self._now(),
                     self._now(), json.dumps(metadata or {})))
                conn.commit()
                return True
        finally:
            conn.close()

    def heartbeat(self, agent_id: str):
        """Update last_active_at timestamp."""
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE agents SET last_active_at=? WHERE agent_id=?",
                (self._now(), agent_id))
            conn.commit()
        finally:
            conn.close()

    def get_agent(self, agent_id: str) -> Optional[dict]:
        """Get agent info."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM agents WHERE agent_id=?", (agent_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_agents(self, agent_type: Optional[str] = None) -> list[dict]:
        """List all agents, optionally filtered by type."""
        conn = self._conn()
        try:
            if agent_type:
                rows = conn.execute(
                    "SELECT * FROM agents WHERE type=? ORDER BY name",
                    (agent_type,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM agents ORDER BY type, name"
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ── Sessions ─────────────────────────────────────────────

    def start_session(self, agent_id: str) -> str:
        """Start a new session for agent_id. Returns session_id."""
        sid = f"session_{uuid.uuid4().hex[:12]}"
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO sessions (session_id, agent_id, started_at, status)
                   VALUES (?, ?, ?, 'running')""",
                (sid, agent_id, self._now()))
            conn.execute(
                "UPDATE agents SET last_active_at=? WHERE agent_id=?",
                (self._now(), agent_id))
            conn.commit()
        finally:
            conn.close()
        return sid

    def end_session(self, session_id: str, status: str = "ok",
                    summary: Optional[str] = None,
                    error_detail: Optional[str] = None):
        """End a session with status and optional summary."""
        conn = self._conn()
        try:
            conn.execute(
                """UPDATE sessions SET ended_at=?, status=?, summary=?, error_detail=?
                   WHERE session_id=?""",
                (self._now(), status, summary, error_detail, session_id))
            conn.commit()
        finally:
            conn.close()

    def get_session(self, session_id: str) -> Optional[dict]:
        """Get session details."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_id=?", (session_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_sessions(self, agent_id: str, limit: int = 10) -> list[dict]:
        """List recent sessions for an agent."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT * FROM sessions WHERE agent_id=?
                   ORDER BY started_at DESC LIMIT ?""",
                (agent_id, limit)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def list_active_sessions(self) -> list[dict]:
        """List all currently running sessions across all agents."""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM sessions WHERE status='running' ORDER BY started_at"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ── Resource Locking ─────────────────────────────────────

    def acquire_lock(self, resource_path: str, agent_id: str,
                     intent: str = "write",
                     ttl_seconds: int = 300) -> bool:
        """Try to acquire a lock. Returns True on success.

        Locks auto-expire after ttl_seconds to prevent deadlocks.
        """
        conn = self._conn()
        try:
            now = self._now()
            # Clean expired locks first
            conn.execute("DELETE FROM locks WHERE expires_at < ?", (now,))

            # Check if lock exists
            existing = conn.execute(
                "SELECT agent_id, expires_at FROM locks WHERE resource_path=?",
                (resource_path,)
            ).fetchone()

            if existing:
                # Lock already held — check if it's us
                if existing["agent_id"] == agent_id:
                    # Refresh our lock
                    expires = datetime.fromisoformat(now).timestamp() + ttl_seconds
                    expires_at = datetime.fromtimestamp(expires, tz=timezone.utc).isoformat()
                    conn.execute(
                        """UPDATE locks SET acquired_at=?, expires_at=?
                           WHERE resource_path=?""",
                        (now, expires_at, resource_path))
                    conn.commit()
                    return True
                conn.commit()
                return False

            # Acquire new lock
            expires = datetime.fromisoformat(now).timestamp() + ttl_seconds
            expires_at = datetime.fromtimestamp(expires, tz=timezone.utc).isoformat()
            conn.execute(
                """INSERT INTO locks (resource_path, agent_id, acquired_at,
                   intent, expires_at) VALUES (?, ?, ?, ?, ?)""",
                (resource_path, agent_id, now, intent, expires_at))
            conn.commit()
            return True
        finally:
            conn.close()

    def release_lock(self, resource_path: str, agent_id: str) -> bool:
        """Release a lock held by agent_id. Returns True if lock existed."""
        conn = self._conn()
        try:
            cursor = conn.execute(
                "DELETE FROM locks WHERE resource_path=? AND agent_id=?",
                (resource_path, agent_id))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def list_locks(self) -> list[dict]:
        """List all active locks."""
        conn = self._conn()
        try:
            # Clean expired
            conn.execute("DELETE FROM locks WHERE expires_at < ?", (self._now(),))
            conn.commit()
            rows = conn.execute(
                "SELECT * FROM locks ORDER BY acquired_at"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ── Journal ──────────────────────────────────────────────

    def journal(self, agent_id: str, category: str, content: dict,
                session_id: Optional[str] = None) -> int:
        """Log a structured journal entry. Returns row id."""
        conn = self._conn()
        try:
            cursor = conn.execute(
                """INSERT INTO journal (agent_id, session_id, timestamp, category, content)
                   VALUES (?, ?, ?, ?, ?)""",
                (agent_id, session_id, self._now(), category,
                 json.dumps(content)))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def query_journal(self, agent_id: Optional[str] = None,
                      category: Optional[str] = None,
                      limit: int = 50) -> list[dict]:
        """Query journal entries with optional filters."""
        conn = self._conn()
        try:
            query = "SELECT * FROM journal WHERE 1=1"
            params = []
            if agent_id:
                query += " AND agent_id=?"
                params.append(agent_id)
            if category:
                query += " AND category=?"
                params.append(category)
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
            return [{**dict(r), "content": json.loads(r["content"])} for r in rows]
        finally:
            conn.close()

    # ── Key-Value State ──────────────────────────────────────

    def set_state(self, agent_id: str, key: str, value: Any):
        """Set a key-value pair for an agent."""
        conn = self._conn()
        try:
            conn.execute(
                """INSERT OR REPLACE INTO state (agent_id, key, value, updated_at)
                   VALUES (?, ?, ?, ?)""",
                (agent_id, key, json.dumps(value), self._now()))
            conn.commit()
        finally:
            conn.close()

    def get_state(self, agent_id: str, key: str) -> Optional[Any]:
        """Get a key-value pair for an agent."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT value FROM state WHERE agent_id=? AND key=?",
                (agent_id, key)
            ).fetchone()
            return json.loads(row["value"]) if row else None
        finally:
            conn.close()

    def delete_state(self, agent_id: str, key: str):
        """Delete a key-value pair."""
        conn = self._conn()
        try:
            conn.execute(
                "DELETE FROM state WHERE agent_id=? AND key=?",
                (agent_id, key))
            conn.commit()
        finally:
            conn.close()

    def list_state_keys(self, agent_id: str) -> list[str]:
        """List all state keys for an agent."""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT key FROM state WHERE agent_id=? ORDER BY key",
                (agent_id,)
            ).fetchall()
            return [r["key"] for r in rows]
        finally:
            conn.close()

    # ── Health & Maintenance ─────────────────────────────────

    def health_check(self) -> dict:
        """Return health metrics."""
        conn = self._conn()
        try:
            agents_count = conn.execute(
                "SELECT COUNT(*) as n FROM agents"
            ).fetchone()["n"]
            active_sessions = conn.execute(
                "SELECT COUNT(*) as n FROM sessions WHERE status='running'"
            ).fetchone()["n"]
            active_locks = conn.execute(
                "SELECT COUNT(*) as n FROM locks WHERE expires_at > ?",
                (self._now(),)
            ).fetchone()["n"]
            journal_count = conn.execute(
                "SELECT COUNT(*) as n FROM journal"
            ).fetchone()["n"]
            db_size = self._path.stat().st_size if self._path.exists() else 0
            wal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]

            return {
                "db_path": str(self._path),
                "db_size_bytes": db_size,
                "wal_mode": wal_mode,
                "agents": agents_count,
                "active_sessions": active_sessions,
                "active_locks": active_locks,
                "journal_entries": journal_count,
            }
        finally:
            conn.close()

    def vacuum(self):
        """Reclaim disk space."""
        conn = self._conn()
        try:
            conn.execute("VACUUM")
        finally:
            conn.close()

    def clear_expired_locks(self) -> int:
        """Remove expired locks. Returns count removed."""
        conn = self._conn()
        try:
            cursor = conn.execute(
                "DELETE FROM locks WHERE expires_at < ?", (self._now(),)
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()


# Module-level convenience that scripts can import
_default_db: Optional[AgentStateDB] = None


def get_db() -> AgentStateDB:
    """Get or create the default AgentStateDB instance."""
    global _default_db
    if _default_db is None:
        _default_db = AgentStateDB()
    return _default_db
