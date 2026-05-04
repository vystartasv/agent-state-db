#!/usr/bin/env python3.11
"""
agent-state — CLI for Agent State DB.

Usage:
    agent-state agent register <name> [--type cron|interactive] [--cron-job-id ID]
    agent-state agent list [--type cron|interactive]
    agent-state agent show <agent-id>
    agent-state agent heartbeat <agent-id>

    agent-state run start <agent-id> [--output-path PATH]
    agent-state run finish <run-id> [--status completed|failed] [--exit-code N] [--summary TEXT]
    agent-state run list [--agent-id ID] [--status STATUS] [--limit N]
    agent-state run show <run-id>

    agent-state state get <agent-id> <key>
    agent-state state set <agent-id> <key> <value>
    agent-state state list <agent-id> [--prefix PREFIX]

    agent-state lock acquire <resource> <agent-id> [--ttl SECONDS]
    agent-state lock release <resource> <agent-id>
    agent-state lock check <resource>

    agent-state coord working-on <agent-id> <resource> [--detail TEXT]
    agent-state coord check <resource>
    agent-state coord recent [--limit N]

    agent-state stats
    agent-state init
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.expanduser("~/.hermes/state"))
from agent_state_db import AgentStateDB


def _print_json(obj):
    print(json.dumps(obj, indent=2, default=str))


def main():
    parser = argparse.ArgumentParser(
        prog="agent-state",
        description="Agent State DB — shared state for autonomous agents",
    )
    subparsers = parser.add_subparsers(dest="command")

    # ---- init ----
    subparsers.add_parser("init", help="Initialize database")

    # ---- agent ----
    agent_p = subparsers.add_parser("agent", help="Agent management")
    agent_subs = agent_p.add_subparsers(dest="subcommand")

    register_p = agent_subs.add_parser("register", help="Register or update an agent")
    register_p.add_argument("name")
    register_p.add_argument("--type", default="interactive")
    register_p.add_argument("--cron-job-id")
    register_p.add_argument("--metadata", default="{}")

    list_p = agent_subs.add_parser("list", help="List agents")
    list_p.add_argument("--type")

    show_p = agent_subs.add_parser("show", help="Show agent details")
    show_p.add_argument("agent_id")

    hb_p = agent_subs.add_parser("heartbeat", help="Update agent last_seen")
    hb_p.add_argument("agent_id")

    # ---- run ----
    run_p = subparsers.add_parser("run", help="Run management")
    run_subs = run_p.add_subparsers(dest="subcommand")

    start_p = run_subs.add_parser("start", help="Start a new run")
    start_p.add_argument("agent_id")
    start_p.add_argument("--output-path")

    finish_p = run_subs.add_parser("finish", help="Finish a run")
    finish_p.add_argument("run_id")
    finish_p.add_argument("--status", default="completed")
    finish_p.add_argument("--exit-code", type=int, default=0)
    finish_p.add_argument("--summary")
    finish_p.add_argument("--token-usage", type=int, default=0)

    rlist_p = run_subs.add_parser("list", help="List runs")
    rlist_p.add_argument("--agent-id")
    rlist_p.add_argument("--status")
    rlist_p.add_argument("--limit", type=int, default=50)

    rshow_p = run_subs.add_parser("show", help="Show run details")
    rshow_p.add_argument("run_id")

    # ---- state ----
    state_p = subparsers.add_parser("state", help="Key-value state management")
    state_subs = state_p.add_subparsers(dest="subcommand")

    get_p = state_subs.add_parser("get", help="Get state value")
    get_p.add_argument("agent_id")
    get_p.add_argument("key")

    set_p = state_subs.add_parser("set", help="Set state value")
    set_p.add_argument("agent_id")
    set_p.add_argument("key")
    set_p.add_argument("value")

    slist_p = state_subs.add_parser("list", help="List state keys")
    slist_p.add_argument("agent_id")
    slist_p.add_argument("--prefix")

    # ---- lock ----
    lock_p = subparsers.add_parser("lock", help="Advisory locking")
    lock_subs = lock_p.add_subparsers(dest="subcommand")

    acquire_p = lock_subs.add_parser("acquire", help="Acquire a lock")
    acquire_p.add_argument("resource")
    acquire_p.add_argument("agent_id")
    acquire_p.add_argument("--ttl", type=int, default=300)

    release_p = lock_subs.add_parser("release", help="Release a lock")
    release_p.add_argument("resource")
    release_p.add_argument("agent_id")

    check_p = lock_subs.add_parser("check", help="Check a lock")
    check_p.add_argument("resource")

    # ---- coord ----
    coord_p = subparsers.add_parser("coord", help="Coordination messages")
    coord_subs = coord_p.add_subparsers(dest="subcommand")

    working_p = coord_subs.add_parser("working-on", help="Declare working on a resource")
    working_p.add_argument("agent_id")
    working_p.add_argument("resource")
    working_p.add_argument("--detail", default="")

    ccheck_p = coord_subs.add_parser("check", help="Check coordination for resource")
    ccheck_p.add_argument("resource")

    recent_p = coord_subs.add_parser("recent", help="Recent coordination activity")
    recent_p.add_argument("--limit", type=int, default=20)

    # ---- stats ----
    subparsers.add_parser("stats", help="Database statistics")

    args = parser.parse_args()

    if args.command == "init":
        db = AgentStateDB()
        _print_json({"status": "initialized", "path": db.db_path})
        return

    db = AgentStateDB()

    if args.command == "agent":
        if args.subcommand == "register":
            metadata = {}
            try:
                metadata = json.loads(args.metadata)
            except json.JSONDecodeError:
                pass
            result = db.register_agent(
                args.name, type=args.type, cron_job_id=getattr(args, 'cron_job_id', None), metadata=metadata
            )
            _print_json(result)
        elif args.subcommand == "list":
            _print_json(db.list_agents(type=args.type))
        elif args.subcommand == "show":
            _print_json(db.get_agent(args.agent_id))
        elif args.subcommand == "heartbeat":
            db.heartbeat(args.agent_id)
            print("✓ Heartbeat updated")

    elif args.command == "run":
        if args.subcommand == "start":
            run_id = db.start_run(args.agent_id, output_path=args.output_path)
            _print_json({"run_id": run_id})
        elif args.subcommand == "finish":
            db.finish_run(
                args.run_id,
                status=args.status,
                exit_code=args.exit_code,
                summary=args.summary,
                token_usage=args.token_usage,
            )
            print("✓ Run finished")
        elif args.subcommand == "list":
            _print_json(db.list_runs(
                agent_id=args.agent_id, status=args.status, limit=args.limit
            ))
        elif args.subcommand == "show":
            _print_json(db.get_run(args.run_id))

    elif args.command == "state":
        if args.subcommand == "get":
            result = db.get_state(args.agent_id, args.key)
            _print_json(result if result else {"error": "not found"})
        elif args.subcommand == "set":
            # Try parsing as JSON first
            try:
                value = json.loads(args.value)
            except json.JSONDecodeError:
                value = args.value
            version = db.set_state(args.agent_id, args.key, value)
            _print_json({"key": args.key, "version": version, "status": "set"})
        elif args.subcommand == "list":
            _print_json(db.list_state(args.agent_id, prefix=args.prefix))

    elif args.command == "lock":
        if args.subcommand == "acquire":
            ok = db.acquire_lock(args.resource, args.agent_id, ttl_seconds=args.ttl)
            if ok:
                _print_json({"status": "acquired", "resource": args.resource, "ttl": args.ttl})
            else:
                existing = db.check_lock(args.resource)
                _print_json({"status": "denied", "held_by": existing})
                sys.exit(1)
        elif args.subcommand == "release":
            ok = db.release_lock(args.resource, args.agent_id)
            _print_json({"status": "released" if ok else "not_found"})
        elif args.subcommand == "check":
            result = db.check_lock(args.resource)
            _print_json(result if result else {"status": "free"})

    elif args.command == "coord":
        if args.subcommand == "working-on":
            row_id = db.coordinate(
                args.agent_id, "working_on", args.resource, detail=args.detail
            )
            _print_json({"id": row_id, "status": "posted"})
        elif args.subcommand == "check":
            _print_json(db.check_coordination(args.resource))
        elif args.subcommand == "recent":
            _print_json(db.recent_activity(limit=args.limit))

    elif args.command == "stats":
        _print_json(db.stats())

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
