# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability, please **do not** open a public issue.

Email the maintainer directly at vilius.vystartas@gmail.com.

You should receive a response within 48 hours. If the issue is confirmed,
we'll release a fix as soon as possible — typically within 72 hours.

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Security Model

This is a **local-only** tool. It runs on your machine, not a server. The
primary security boundary is your operating system's user permissions.

- No network exposure — SQLite file, local access only
- Database file at `~/.hermes/state/agents.db` with filesystem permissions
- No telemetry, no phoning home
- No authentication layer — assumes trusted local user
