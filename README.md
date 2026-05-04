# Agent State DB

SQLite+WAL shared state for autonomous AI agents. Solves concurrency across multiple
cron jobs by providing agent identity, run journals, versioned key-value state,
advisory locks, and cross-agent coordination.

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
