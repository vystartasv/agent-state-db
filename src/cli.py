#!/usr/bin/env python3.11
"""
agent-state CLI — manage the Agent State DB.

Usage:
    agent-state health              Show health metrics
    agent-state agents              List all agents
    agent-state agent <id>          Show agent details
    agent-state sessions [agent]    List sessions
    agent-state locks               List active locks
    agent-state journal [agent]     Show recent journal entries
    agent-state vacuum              Reclaim disk space
"""

import sys
import os
import json

# Ensure we can import from ~/.hermes/scripts
sys.path.insert(0, os.path.expanduser("~/.hermes/scripts"))
from agent_state_db import AgentStateDB


def cmd_health():
    db = AgentStateDB()
    health = db.health_check()
    print(f"DB: {health['db_path']}")
    print(f"Size: {health['db_size_bytes']:,} bytes")
    print(f"WAL mode: {health['wal_mode']}")
    print(f"Agents: {health['agents']}")
    print(f"Active sessions: {health['active_sessions']}")
    print(f"Active locks: {health['active_locks']}")
    print(f"Journal entries: {health['journal_entries']}")


def cmd_agents():
    db = AgentStateDB()
    agents = db.list_agents()
    if not agents:
        print("No agents registered.")
        return
    for a in agents:
        status = "●" if a.get("last_active_at") else "○"
        print(f"{status} {a['agent_id']:<24} {a['name']:<30} [{a['type']}]")


def cmd_agent(agent_id: str):
    db = AgentStateDB()
    agent = db.get_agent(agent_id)
    if not agent:
        print(f"Agent '{agent_id}' not found.")
        return
    for k, v in agent.items():
        if k == "metadata":
            try:
                v = json.dumps(json.loads(v), indent=2)
            except (json.JSONDecodeError, TypeError):
                pass
        print(f"  {k}: {v}")


def cmd_sessions(agent_id: str = None):
    db = AgentStateDB()
    if agent_id:
        sessions = db.list_sessions(agent_id, limit=20)
    else:
        sessions = db.list_active_sessions()
        if not sessions:
            # Show all recent
            agents = db.list_agents()
            sessions = []
            for a in agents[:5]:
                sessions.extend(db.list_sessions(a["agent_id"], limit=3))

    for s in sessions:
        icon = {"ok": "✓", "running": "→", "error": "✗"}.get(s["status"], "?")
        ended = s.get("ended_at", "")[:19] if s.get("ended_at") else "running..."
        print(f"{icon} {s['session_id']:<20} {s['agent_id']:<24} {s['status']:<8} {ended}")


def cmd_locks():
    db = AgentStateDB()
    locks = db.list_locks()
    if not locks:
        print("No active locks.")
        return
    for l in locks:
        print(f"🔒 {l['resource_path']:<40} held by {l['agent_id']:<24} [{l['intent']}]")


def cmd_journal(agent_id: str = None, limit: int = 20):
    db = AgentStateDB()
    entries = db.query_journal(agent_id=agent_id, limit=limit)
    if not entries:
        print("No journal entries.")
        return
    for e in entries:
        ts = e["timestamp"][:19]
        content_preview = json.dumps(e["content"])[:80]
        print(f"[{ts}] {e['agent_id']:<24} {e['category']:<12} {content_preview}")


def cmd_vacuum():
    db = AgentStateDB()
    before = db.health_check()["db_size_bytes"]
    db.vacuum()
    after = db.health_check()["db_size_bytes"]
    print(f"Vacuumed: {before:,} → {after:,} bytes (saved {before - after:,})")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    cmd = sys.argv[1]
    if cmd == "health":
        cmd_health()
    elif cmd == "agents":
        cmd_agents()
    elif cmd == "agent" and len(sys.argv) > 2:
        cmd_agent(sys.argv[2])
    elif cmd == "sessions":
        cmd_sessions(sys.argv[2] if len(sys.argv) > 2 else None)
    elif cmd == "locks":
        cmd_locks()
    elif cmd == "journal":
        cmd_journal(sys.argv[2] if len(sys.argv) > 2 else None)
    elif cmd == "vacuum":
        cmd_vacuum()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
