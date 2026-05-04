"""
Agent State DB — SQLite+WAL shared state for autonomous agents.

Solvier: concurrency (SQLite WAL), agent identity, cross-agent coordination,
run journals, and advisory locking. Built for Hermes cron fleet.

Usage:
    from agent_state_db import AgentStateDB
    db = AgentStateDB()
    agent = db.register_agent("hourly-review", type="cron", cron_job_id="eafaef2d893b")
    db.start_run(agent["agent_id"])
    db.set_state(agent["agent_id"], "last_reviewed", "webpart-42")
"""

from .core import AgentStateDB

__all__ = ["AgentStateDB"]
