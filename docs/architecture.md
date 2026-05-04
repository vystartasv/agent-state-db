# Agent State DB — Architecture

Shared SQLite state service for Hermes autonomous agents. Solves concurrency, identity, coordination, and journaling in one package.

## Problem

19 cron jobs running as isolated processes with no shared runtime state:
- **Write conflicts** on shared JSONL files (skill_gaps.jsonl)
- **No identity** — agents don't know their own history
- **No coordination** — can't check "is anyone working on file X?"
- **No journal** — learnings lost between runs

## Design

- **SQLite WAL mode** — concurrent reads + single writer
- **File at ~/.hermes/state/agent_state.db** — colocated with agent runtime
- **Python module** at ~/.hermes/scripts/agent_state_db.py — importable by all agents
- **WAL mode** enables 19 agents reading simultaneously, one writing at a time
- **Busy timeout 5000ms** — writers queue rather than fail

## Schema

```
agents          — one row per agent/cron job
  agent_id TEXT PK, name TEXT, type TEXT, created_at TEXT,
  last_active_at TEXT, metadata JSON

sessions        — one row per agent run
  session_id TEXT PK, agent_id TEXT FK, started_at TEXT,
  ended_at TEXT, status TEXT, summary TEXT, error_detail TEXT

locks           — resource coordination
  resource_path TEXT PK, agent_id TEXT, acquired_at TEXT,
  intent TEXT, expires_at TEXT

journal         — structured learnings
  id INTEGER PK AUTOINCREMENT, agent_id TEXT, session_id TEXT,
  timestamp TEXT, category TEXT, content JSON

state           — key-value persistence
  agent_id TEXT, key TEXT, value JSON, updated_at TEXT,
  PRIMARY KEY (agent_id, key)
```

## API Design

```python
from agent_state_db import AgentStateDB

db = AgentStateDB()  # singleton, auto-inits DB

# Identity
db.register_agent("job_123", "Nightly Analyzer", "cron", metadata={...})
db.heartbeat("job_123")

# Sessions
sid = db.start_session("job_123")
db.end_session(sid, "ok", summary="Reviewed 45 web parts")
db.list_sessions("job_123", limit=10)

# Coordination
if db.acquire_lock("MEMORY.md", "job_123", intent="write"):
    # do work
    db.release_lock("MEMORY.md", "job_123")

# Journal
db.journal("job_123", "discovery", {"finding": "...", "fix": "..."})

# State
db.set_state("job_123", "last_reviewed", {"slug": "chatbot", "at": "..."})
last = db.get_state("job_123", "last_reviewed")

# Operational
db.health_check()  # returns dict with counts, WAL status, size
```

## Concurrency guarantees

- WAL mode: readers never block writers, writers never block readers
- `BEGIN IMMEDIATE` on writes — first writer wins, others get busy-wait
- Busy timeout 5000ms — no "database is locked" failures
- Locks table for application-level coordination (not DB-level)

## Deployment

- Python package installable via `pip install -e .` (or `pip install agent-state-db` from PyPI)
- DB lives at `~/.hermes/state/agent_state.db`
- Zero dependencies beyond Python stdlib (sqlite3, json, uuid, datetime)
- Agents import and use directly: `from agent_state_db.core import AgentStateDB`
- Cron integration: `scripts/cron_pre_flight.py` + `scripts/cron_post_flight.py` for auto-registration and run tracking
