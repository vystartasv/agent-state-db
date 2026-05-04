#!/usr/bin/env python3.11
"""
Cron pre-flight script for Agent State DB.

Called BEFORE a cron job runs. Registers the agent (upserts on name),
starts a new run, and prints the run_id for the cron job to capture.

Usage:
    eval $(python3.11 scripts/cron_pre_flight.py "My Job" "cron-job-id-abc123")

    # $RUN_ID is now set — pass it to the post-flight script when done
    # ... do the actual cron work ...
"""

import sys
import os
import json

# Ensure agent_state_db package is importable
sys.path.insert(0, os.path.expanduser("~/.hermes/state"))

from agent_state_db.core import AgentStateDB  # noqa: E402


def main():
    if len(sys.argv) < 2:
        print("Usage: cron_pre_flight.py <agent_name> [cron_job_id]", file=sys.stderr)
        sys.exit(1)

    agent_name = sys.argv[1]
    cron_job_id = sys.argv[2] if len(sys.argv) > 2 else None

    db = AgentStateDB()
    agent = db.register_agent(agent_name, type="cron", cron_job_id=cron_job_id)
    run_id = db.start_run(agent["agent_id"])

    # Output as shell-parseable env vars
    print(f'export AGENT_STATE_RUN_ID="{run_id}"')
    print(f'export AGENT_STATE_AGENT_ID="{agent["agent_id"]}"')

    # Also output as JSON on stderr for logging
    print(json.dumps({
        "event": "run_started",
        "agent_name": agent_name,
        "agent_id": agent["agent_id"],
        "run_id": run_id,
        "cron_job_id": cron_job_id,
    }), file=sys.stderr)


if __name__ == "__main__":
    main()
