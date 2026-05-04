# My 19 AI Agents Kept Breaking Each Other — The 4 Tools That Fixed It

*By Vilius Vystartas | May 2026 | [Published on dev.to](https://dev.to/vystartasv/my-19-ai-agents-kept-breaking-each-other-the-4-tools-that-fixed-it-3559)*

I run 19 AI agents on my machine. They wake up throughout the day to review code, publish content, check server health, research medical literature, and self-improve. Some run hourly. Some fire at 2am.

For months they were reliable. Then I noticed the cracks.

--- 

## The Moment I Realised It Was Broken

Three things happened in the same week:

One agent updated a skill file and another overwrote it 30 seconds later with stale data. The skill file was now wrong — silently corrupted — and both agents continued as if nothing happened.

A cron job tried to publish a blog post to dev.to. It needed an API key from 1Password. The agent sat there waiting for a fingerprint that would never come. The job failed. Then it tried again next tick. And the next. 17 consecutive failures before I noticed.

Another agent was trying to read a project repository. Its local model has a 40K token context window. Someone had dumped `node_modules`, `.git`, and every log file into the prompt. The model couldn't see the actual code. It guessed. The output was nonsense.

None of these were model problems. None were prompt problems. Every single one was an *infrastructure problem* — the layer between the agent and its environment was missing.

---

## What I Built: Four Infrastructure Tools

I spent a weekend building four single-purpose tools that handle the four categories of failures I kept seeing. Each tool is a Python package. Each does exactly one thing. Each has tests.

### 1. Agent State DB — So They Stop Overwriting Each Other

The problem: 19 agents, one filesystem. No coordination. When two agents modify the same file, last-write-wins, and the loser's changes evaporate silently.

The fix: a SQLite database with WAL-mode concurrency that gives every agent a persistent identity, a run journal, versioned key-value state, advisory locks, and a coordination channel.

```
$ agent-state stats
  Registered agents:  20
  Active runs:         2
  Completed runs:     47
  Failed runs:         8
  Active locks:        1
```

Agents now write to the DB before touching shared files. If they see a lock on `catalog.json`, they wait. If they want to announce what they're working on, they call `agent-state coord working-on`. Other agents can check before starting conflicting work.

**Stack:** Python 3.11, SQLite WAL, Click CLI. 8 tests. MIT.

### 2. Credential Proxy — So They Can Get Passwords Without Fingers

The problem: password managers need a fingerprint, a master password, or a hardware key tap. Cron jobs have none of those. Any agent that needs an API key is dead on arrival.

The fix: a local daemon that decrypts your credentials once at boot and serves them over a Unix socket. Agents call `get_credential("github.com")`. No Touch ID. No popups.

```
$ credential-proxy status
  Daemon:    running (pid 85985)
  Socket:    ~/.hermes/credential_proxy/proxy.sock
  Credentials: 353 loaded
  Chrome import: auto-deleted after import
```

Everything is Fernet-encrypted at rest. The socket is `chmod 600`. The database and master key are `chmod 600`. Nothing touches the network. It's a locked box in your house, not a cloud service.

**Stack:** Python 3.11, Fernet (AES-128-CBC + HMAC-SHA256), Unix domain sockets, launchd. 24 tests. MIT.

### 3. Context Packer — So Local Models Can See What Matters

The problem: local models have small context windows (40K tokens max for Q4 quants). Dumping a whole repo — `node_modules`, build artifacts, 42MB of logs — wastes 90% of the window on noise.

The fix: a deterministic pre-cron script that takes a repo path and outputs a compact markdown blob of only the high-signal files.

```
$ python3.11 context_packer.py ~/Agent-Projects/agent-foundry
  2,521 files scanned
  8 high-signal files packed
  12,847 characters (safe within budget)
  Priority: README.md, pyproject.toml, src/main.py, tests/
```

It reads `AGENTS.md`, `ARCHITECTURE.md`, `README.md`, prioritizes recently modified files, excludes `.git`, `node_modules`, `__pycache__`, and `venv`, and outputs a token-budgeted markdown document. Drop it as a pre-cron script and your local model suddenly sees the code it's supposed to work on.

**Stack:** Python 3.11, stat-based file scoring. MIT.

### 4. Cron Guard — So Failures Don't Cascade

The problem: a broken cron job fails every tick. If it runs hourly, that's 24 failures before you wake up and notice. Multiply by 19 jobs and one bad configuration means hundreds of silent failures.

The fix: a pre-cron script that checks the last 3 runs of every job via the Agent State DB. Three consecutive failures → auto-pause + alert.

```
$ python3.11 cron_guard.py
  Checked: 20 jobs
  Healthy: 19
  Blocked: 1 (k6a-weekly — 3 consecutive failures)
  Pause instructions written to /tmp/cron_guard_blocked.json
```

The agent that was failing 17 times in a row now stops itself after 3. I get an alert. I fix the root cause. It resumes. No more failure cascades.

**Stack:** Python 3.11, Agent State DB integration. MIT.

---

## How They Work Together

The four tools are independent but designed to chain:

1. **Cron Guard** runs first — checks if the job should even proceed
2. **Agent State DB** registers the run — the agent gets an identity and a run ID
3. **Context Packer** builds the prompt context — the model sees what matters
4. **Credential Proxy** serves API keys on demand — the agent authenticates

All four are pre-cron scripts. They run before the model prompt is even sent. They're deterministic Python, not LLM calls. That's intentional — infrastructure should be boring and reliable.

---

## What I Learned

**1. Agent failures are rarely model failures.** Every failure I debugged traced back to the environment: missing credentials, corrupted files, context overflow, no coordination. The models were fine. The scaffolding was missing.

**2. Shared state is the difference between a collection of scripts and a fleet.** Before the Agent State DB, my 19 agents were 19 independent processes that happened to run on the same machine. After, they're a system. They know about each other. They coordinate. They journal their own history.

**3. Infrastructure should be boring.** None of these tools use AI. They're deterministic Python scripts. They run in milliseconds. They have tests. The more AI you put in your AI infrastructure, the more ways it can fail. Let the models be models. Let the plumbing be plumbing.

---

## Get It

- **Agent State DB:** [github.com/vystartasv/agent-state-db](https://github.com/vystartasv/agent-state-db)
- **Credential Proxy:** [github.com/vystartasv/credential-proxy](https://github.com/vystartasv/credential-proxy)
- **Context Packer:** [github.com/vystartasv/agent-state-db](https://github.com/vystartasv/agent-state-db) (bundled in `scripts/`)
- **Cron Guard:** [github.com/vystartasv/agent-state-db](https://github.com/vystartasv/agent-state-db) (bundled in `scripts/`)

All MIT licensed. Python 3.11. Install with `pip install -e .`.

If you're running multiple agents and hitting the same walls, I'd love to hear what you're building. Feedback welcome.
