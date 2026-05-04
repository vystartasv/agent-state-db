# Changelog

All notable changes to Agent State DB are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] — 2026-05-04

### Added
- SQLite+WAL core schema with agent, run, state, and lock tables
- Agent registration with upsert and heartbeat tracking
- Run lifecycle: start, finish (completed/failed), auto-cleanup of stale runs
- Versioned key-value state store with conflict resolution via RETURNING
- Advisory resource locks with TTL-based stale lock detection
- Cross-agent coordination API (working_on announcements)
- CLI: `agent-state agent register|list`, `agent-state run start|finish`, `agent-state state set|get`, `agent-state lock acquire|release`, `agent-state coord working-on`, `agent-state stats`
- Cron Guard pre-cron script integration (`cron_pre_script.sh`)
- Context Packer integration for pre-run context injection
- 8 tests with 100% pass rate
