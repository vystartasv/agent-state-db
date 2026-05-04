# Comms Kit — Agent Infrastructure Tools Launch

> Channel-specific posts for the 4-tool agent infrastructure release.  
> Blog post: `docs/blog-four-agent-infrastructure-tools.md`  
> Repos: agent-state-db, credential-proxy  
> Python 3.11, SQLite, Fernet, Unix sockets. All MIT.

---

## 1. Twitter/X Thread

**Tweet 1:**  
I run 19 AI agents on my machine. They kept breaking each other in ways that had nothing to do with the models. Overwriting shared files. Needing passwords with no fingers. Drowning in context noise. Failing silently 17 times in a row. The fix wasn't better prompts. It was better infrastructure. 🧵

**Tweet 2:**  
Agent State DB — SQLite+WAL shared state. Every agent gets an identity, a run journal, advisory locks, and a coordination channel. When 19 agents share one filesystem, last-write-wins isn't good enough. github.com/vystartasv/agent-state-db

**Tweet 3:**  
Credential Proxy — Fernet-encrypted credential store over Unix socket. Your password manager wants a fingerprint. Cron jobs don't have fingers. This decrypts once at boot and serves 353 credentials over a local socket. No network. No popups. github.com/vystartasv/credential-proxy

**Tweet 4:**  
Context Packer — 2,521 files → 8 high-signal files. Local models have 40K token windows. Dumping node_modules and build artifacts into the prompt is like asking someone to read a book while shoving takeout menus in their face. This strips the noise. Drop it as a pre-cron script.

**Tweet 5:**  
Cron Guard — 3 consecutive failures → auto-pause + alert. Found a job that failed 17 times before I noticed. Now it stops itself after 3. All four tools are deterministic Python scripts. They run before the model even sees a prompt. Infrastructure should be boring.

**Tweet 6:**  
All MIT, all Python 3.11, all tested, all repo-documented (README, CONTRIBUTING, CHANGELOG, SECURITY, CODE_OF_CONDUCT). If you're running multiple agents and hitting the same walls: github.com/vystartasv/agent-state-db

---

## 2. LinkedIn Post

**My 19 AI agents kept breaking each other. Better prompts didn't fix it.**

Three failures in one week: an agent silently corrupted a shared skill file (last-write-wins), another failed 17 consecutive times waiting for a fingerprint it would never get, and a third drowned its local model in node_modules instead of actual code.

None of these were model problems. They were infrastructure problems — the layer between the agent and its environment was missing.

So I built four tools over a weekend:

→ **Agent State DB** — SQLite+WAL shared state so agents coordinate instead of colliding
→ **Credential Proxy** — encrypted credential store over Unix socket so cron jobs can authenticate
→ **Context Packer** — strips 2,521 files down to 8 high-signal ones for local models
→ **Cron Guard** — 3-strike auto-pause so failures don't cascade (caught a job with 17 consecutive fails)

All deterministic Python. All tested. All MIT.

Lesson: your agents aren't failing because of the model. They're failing because the scaffolding is missing. Let models be models. Let plumbing be plumbing.

Repos at github.com/vystartasv — agent-state-db and credential-proxy.

#aiagents #python #opensource #devops #sqlite

---

## 3. Short (Telegram / Discord)

**4 agent infrastructure tools are live** 🦞

Fixed the four failure modes that kept breaking my 19 autonomous agents:

- **Agent State DB** — agents stop overwriting each other's work (SQLite+WAL, advisory locks, run journal)
- **Credential Proxy** — agents get passwords without needing fingers (Fernet, Unix socket, 353 creds)
- **Context Packer** — local models see code, not node_modules (2,521 files → 8, token-budgeted)
- **Cron Guard** — 3 failures → auto-pause before you get 24 error emails

All MIT, all tested, all documented with README / CONTRIBUTING / CHANGELOG / SECURITY / CODE_OF_CONDUCT.

- [agent-state-db](https://github.com/vystartasv/agent-state-db)
- [credential-proxy](https://github.com/vystartasv/credential-proxy)
