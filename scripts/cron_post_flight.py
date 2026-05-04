#!/usr/bin/env python3.11
"""
Cron post-flight script for Agent State DB.

Called AFTER a cron job finishes. Records the run outcome in the shared database.

Usage:
    python3.11 scripts/cron_post_flight.py $RUN_ID completed "Task summary"

    python3.11 scripts/cron_post_flight.py $RUN_ID failed "Error message" --exit-code 1
"""

import sys
import os
import json

sys.path.insert(0, os.path.expanduser("~/.hermes/state"))
from agent_state_db.core import AgentStateDB  # noqa: E402


def main():
    if len(sys.argv) < 3:
        print("Usage: cron_post_flight.py <run_id> <status> [summary] [--exit-code N]",
              file=sys.stderr)
        print("  status: completed, failed, interrupted", file=sys.stderr)
        sys.exit(1)

    run_id = sys.argv[1]
    status = sys.argv[2]

    # Parse optional arguments
    summary = None
    exit_code = 0
    args = sys.argv[3:]
    i = 0
    while i < len(args):
        if args[i] == "--exit-code" and i + 1 < len(args):
            exit_code = int(args[i + 1])
            i += 2
        elif not args[i].startswith("--"):
            summary = args[i]
            i += 1
        else:
            i += 1

    db = AgentStateDB()
    db.finish_run(run_id, status=status, exit_code=exit_code, summary=summary)

    print(json.dumps({
        "event": "run_finished",
        "run_id": run_id,
        "status": status,
        "exit_code": exit_code,
    }))

    if status == "failed":
        sys.exit(1 if exit_code == 0 else exit_code)


if __name__ == "__main__":
    main()
