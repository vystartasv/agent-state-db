# Agent State DB

SQLite+WAL shared state service for autonomous AI agents. Gives every agent an
identity, a journal, versioned key-value state, advisory locks, and cross-agent
coordination — so multiple cron jobs can share resources without stepping on each
other.

---

## Summary

When you run multiple AI agents at the same time, they all need to read and write
the same files, track what they've done, and avoid duplicating work. Without shared
state, they collide — overwriting each other's output, re-processing finished tasks,
or working on the same thing twice.

Agent State DB is a single source of truth that all agents share. Each agent
registers once, then logs every run (when it started, what it did, whether it
succeeded). Agents can set locks on shared resources and announce what they're
currently working on, so others can check before starting conflicting work.

Think of it as the noticeboard in a shared workshop — everyone pins their name,
their current task, and any "do not touch" signs on shared tools.

---

## Who it's for

- Anyone running **multiple scheduled AI agents** (cron jobs, background workers)
  that read or write the same files
- **DevOps workflows** where agent runs need to be auditable — what ran when,
  did it succeed
- **Multi-agent systems** where agents need to coordinate without a human in
  the loop
- **Self-improving agents** that benefit from knowing what they did last time

## Who it's NOT for

- **Single-agent setups** — if you only run one agent, you don't need
  coordination or locking
- **Stateless workflows** — if each run is fully independent with no shared
  files or state to track
- **Interactive-only use** — this is built for autonomous agents, not
  human-driven REPL sessions
- **Distributed systems** — it's local SQLite, not a network database.
  One machine, one DB

---

## Install

```bash
pip install -e .
```

## Quick Start

```python
from agent_state_db import AgentStateDB

db = AgentStateDB()
agent = db.register_agent("my-job", type="cron", cron_job_id="abc123")
run_id = db.start_run(agent["agent_id"])

# Do work...
db.set_state(agent["agent_id"], "last_success", "2026-05-04")

# Lock a shared resource
if db.acquire_lock("catalog.json", agent["agent_id"]):
    # Safe to write
    db.release_lock("catalog.json", agent["agent_id"])

# Announce what you're working on
db.coordinate(agent["agent_id"], "working_on", "catalog.json")

# Finish
db.finish_run(run_id, status="completed")
```

## CLI

```
agent-state agent register <name> --type cron --cron-job-id <id>
agent-state run start <agent-id>
agent-state run finish <run-id> --status completed
agent-state state set <agent-id> key value
agent-state lock acquire <resource> <agent-id>
agent-state coord working-on <agent-id> <resource>
agent-state stats
```

## License

MIT
