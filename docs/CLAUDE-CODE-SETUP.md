# Claude Code Setup — New Machine Guide

Everything needed to bring up a fresh dev machine for working on this project with Claude Code. **Read this before doing anything else on a new computer.**

After completing the steps here, your kickoff move is to open Claude Code in the repo root and paste the prompt at the bottom of this doc.

---

## Quickstart (TL;DR)

```bash
git clone git@github.com:Bighabz/ReviewGuide-SourceCode.git
cd ReviewGuide-SourceCode
```

(If you don't have SSH set up with GitHub, use HTTPS instead: `git clone https://github.com/Bighabz/ReviewGuide-SourceCode.git`)

1. Walk through §1–§5 below to install Claude Code, plugins, MCPs, and CLI tools.
2. Open Claude Code in the repo root.
3. Paste the kickoff prompt from §7 into Claude Code as your first message.
4. From there, Claude reads `docs/audits/next-session-prompt-2026-05-19.md` and starts work.

---

## What travels via `git clone` (already in this repo)

You get these for free when you clone:

- **`CLAUDE.md`** — project conventions, repo map, important paths. Claude Code auto-reads this on startup.
- **`.claude/commands/`** — project-scoped slash commands: `/deploy`, `/feature-dev`, `/review`, `/test`. Available immediately after clone.
- **`docs/audits/`** — all audit reports, handoff prompts, and the QA report. The current handoff is `next-session-prompt-2026-05-19.md`.
- **`.planning/`** — codebase maps (STACK, ARCHITECTURE, CONVENTIONS, CONCERNS) and phase folders. Used by the GSD workflow.

## What does NOT travel (per-machine setup required)

| Item | Reason | How to recreate |
|---|---|---|
| `.mcp.json` | Gitignored (contains plaintext API tokens) — see §3 below | Recreate locally with your own credentials |
| `.claude/settings.local.json` | Per-machine permission allowlist | Auto-generated on first use; will fill in as you approve tool calls |
| `~/.claude.json` | User-level Claude Code config (theme, MCPs, login) | Set up via Claude Code on first run |
| `~/railway-env-backups/` | Local snapshots of Railway env vars (contain secrets) | Re-snapshot via `railway variables --json` whenever you need a checkpoint |
| Auto-memory store at `~/.claude/projects/.../memory/` | Per-machine, not portable | Load-bearing facts are captured in this doc + the handoff |
| Chrome extension state | Per-machine browser install | Install Chrome extension (see §4) |

---

## 1. Install Claude Code

Follow the official install guide for your platform (CLI, desktop app, or IDE extension). The CLI is what we use in this project.

```bash
# verify install
claude --version
```

Log in to Anthropic when prompted.

---

## 2. Install plugins (skills + agents)

This project uses two plugins from the `claude-plugins-official` marketplace:

```bash
# Inside Claude Code, run these slash commands:
/plugin marketplace add claude-plugins-official
/plugin install superpowers@claude-plugins-official
/plugin install frontend-design@claude-plugins-official
```

You'll then have access to:

- **`superpowers`** — skill library used throughout this project: `brainstorming`, `dispatching-parallel-agents`, `executing-plans`, `test-driven-development`, `verification-before-completion`, etc.
- **`frontend-design`** — for any visual / UI work on the Next.js frontend.

You'll also see `gsd:*` slash commands (GSD = Get Sh*t Done — phase-based workflow used in this repo). These are typically auto-installed alongside superpowers.

---

## 3. MCP servers

### 3a. User-level MCPs (configured once per Claude Code install)

| MCP | Purpose in this project |
|---|---|
| **`nanobanana`** | Gemini-powered image generation. Used for hero/category images during phase work (see `phases/18-*`, `phases/19-*`, `phases/24-03`). |

Configure via:

```bash
# Add via Claude Code CLI (will prompt for any required tokens):
claude mcp add nanobanana
```

### 3b. Project-level MCPs (live in gitignored `.mcp.json`)

This project ships with 5 project MCPs configured. They are **not** committed (file is in `.gitignore` for security — contains plaintext tokens). You must recreate `.mcp.json` at the repo root on each new machine.

| MCP | Purpose | Token needed |
|---|---|---|
| **`supabase`** | Database introspection, table schema, query exec | Supabase access token (from supabase.com → account → access tokens) |
| **`github`** | PR creation, issue ops, branch creation, list_commits | GitHub Personal Access Token (`repo`, `read:org`) |
| **`vercel`** | Frontend deploy status, project info | Vercel API key (vercel.com → account settings → tokens) |
| **`railway`** | Backend env vars, deploys, logs (Railway hosts the FastAPI backend) | None directly — uses `railway login` CLI session |
| **`docker`** | Local container ops | None |

Create `.mcp.json` at the repo root using the template below. **Replace `<...>` with your own credentials.** Do not commit this file.

```json
{
  "mcpServers": {
    "supabase": {
      "command": "cmd",
      "args": ["/c", "npx", "-y", "@supabase/mcp-server-supabase@latest", "--access-token", "<YOUR_SUPABASE_ACCESS_TOKEN>"]
    },
    "github": {
      "command": "cmd",
      "args": ["/c", "npx", "-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "<YOUR_GITHUB_PAT>"
      }
    },
    "vercel": {
      "command": "cmd",
      "args": ["/c", "npx", "-y", "vercel-mcp", "VERCEL_API_KEY=<YOUR_VERCEL_API_KEY>"]
    },
    "railway": {
      "command": "cmd",
      "args": ["/c", "npx", "-y", "@railway/mcp-server"]
    },
    "docker": {
      "command": "cmd",
      "args": ["/c", "npx", "-y", "@hypnosis/docker-mcp-server"]
    }
  }
}
```

> **Linux / macOS users:** replace each `"command": "cmd"` + `"args": ["/c", "npx", ...]` block with `"command": "npx"` + drop the `/c` arg. e.g.:
> ```json
> { "command": "npx", "args": ["-y", "@modelcontextprotocol/server-github"] }
> ```

Then in Claude Code, enable them for this project (one-time):

```bash
/mcp                          # interactive menu — toggle on each MCP listed
```

Or edit `.claude/settings.local.json` directly to include:

```json
{
  "enableAllProjectMcpServers": true,
  "enabledMcpjsonServers": ["supabase", "github", "vercel", "railway", "docker"]
}
```

### 3c. Chrome browser automation MCP

**`claude-in-chrome`** is used for live browser audits (visual regression checks, click-through verification, console inspection on prod URLs). It is not a typical MCP server — it's a Chrome extension + bridge.

To set up:

1. Install the **Claude in Chrome** extension from the Chrome Web Store (search "Claude in Chrome" by Anthropic).
2. Pin the extension to the toolbar.
3. Open Claude Code. The MCP tools (`mcp__claude-in-chrome__*`) auto-appear when the extension is active.

Used in 2026-04-21 audit to verify the wrong-link affiliate bug visually — see `docs/audits/qa-report-2026-04-21.md`.

### 3d. Other Anthropic-hosted MCPs (auth-on-demand)

These are surfaced in Claude Code as deferred tools and authenticate per-use:

- `claude_ai_Gmail` — Gmail read/send
- `claude_ai_Google_Calendar` — calendar read/write
- `claude_ai_Google_Drive` — Drive file read

No setup needed beyond logging in when first invoked.

---

## 4. CLI tools

Install on the new machine:

```bash
# Git + GitHub CLI (auth)
gh auth login

# Railway CLI (for backend env / deploys)
npm install -g @railway/cli
railway login
railway link --project reviewguide-backend
railway service        # confirm backend service selected

# Vercel CLI (optional — Vercel MCP covers most needs)
npm install -g vercel
vercel login

# Node + Python (project dependencies)
cd backend && pip install -r requirements.txt && cd ..
cd frontend && npm install && cd ..
```

---

## 5. Verify the backend is up

```bash
curl -sS -o /dev/null -w "%{http_code}\n" \
  https://backend-production-0ae7.up.railway.app/health
# expect: 200
```

If you get anything else, check Railway dashboard before assuming the codebase is broken — the prior session burned hours diagnosing what turned out to be an unrelated Railway env issue.

---

## 6. Read the handoff

The current handoff doc is **`docs/audits/next-session-prompt-2026-05-19.md`**. Read it in full before touching code. It contains:

- The 5 ranked fixes (Fix 1 = positional-zip affiliate mismapping, ship alone first)
- The misdiagnosis from the prior (2026-04-22) handoff, marked superseded
- The logo restoration open question
- Reality-check warnings: re-verify against `git log -5 origin/main` and `curl /health` before trusting any state claim

Supporting documents to read in order:

1. `docs/audits/next-session-prompt-2026-05-19.md` ← **current handoff, start here**
2. `docs/audits/qa-report-2026-04-21.md` ← QA findings that drove the plan
3. `docs/audits/opus-4.7-audit-report-2026-04-16.md` ← original P0-P3 inventory
4. `.planning/codebase/STACK.md`, `ARCHITECTURE.md`, `CONVENTIONS.md`, `CONCERNS.md` ← codebase maps
5. `CLAUDE.md` ← project conventions

---

## 7. Kickoff prompt (paste this into Claude Code as your first message on the new machine)

```
You are picking up the ReviewGuide.ai stabilization work from a prior session on another machine. Before doing anything else:

0. If the repo isn't cloned in the current working directory yet, clone it first. Repo URL: `git@github.com:Bighabz/ReviewGuide-SourceCode.git` (HTTPS fallback: `https://github.com/Bighabz/ReviewGuide-SourceCode.git`). After clone, `cd ReviewGuide-SourceCode` and continue from step 1.

1. Read `docs/CLAUDE-CODE-SETUP.md` to confirm the machine is set up (MCPs enabled, plugins installed, Railway/GitHub/Vercel CLIs authed, /health returns 200). If any CLI is missing, install + auth it; ask the user to run interactive logins via `! <cmd> login`.

2. Read `docs/audits/next-session-prompt-2026-05-19.md` end to end — that is the current handoff. Then read the documents it references in the order listed.

3. Re-verify reality before trusting the handoff:
   - `git log -5 origin/main` — confirm last commit is still `84d2999` (or note what changed)
   - `curl -sS -o /dev/null -w "%{http_code}\n" https://backend-production-0ae7.up.railway.app/health` — must be 200
   - Skim `git status` and any open PRs to see what's already in flight

4. The current backlog (as ranked in the handoff):
   - Fix 1 (P0, ship alone): positional-zip affiliate mismapping at `backend/mcp_server/tools/product_affiliate.py:174-175`. Read `_fuzzy_product_match` to confirm threshold convention and spot-check curated_amazon_links.py for premium-brand coverage BEFORE writing the patch.
   - Fix 2 (P1): create `frontend/app/discover/page.tsx` as a 2-line redirect to `/`.
   - Fix 3 (P1): correct miscategorized chip queries in `frontend/components/discover/CategoryChipRow.tsx:10-19`.
   - Fix 4 (P1): remove Saved + Compare nav links from `frontend/components/UnifiedTopbar.tsx` and delete the matching `app/saved/` and `app/compare/` page directories.
   - Fix 5 (P2): gate the `router.replace` in `frontend/app/chat/page.tsx:25-83` behind the `processedQueryRef` check (do NOT just set `deps=[]` — that breaks second-chip navigation).
   - Logo restoration (blocked on user input): pick option 1 / 2 / 3 from the handoff's "Logo restoration" section.

5. Use TaskCreate to track. Mark items completed as soon as each ships.

6. For Fix 1 specifically: do NOT execute the env-var mutation plan from the superseded 2026-04-22 handoff (`USE_MOCK_AFFILIATE=true`, etc.). It was based on a misdiagnosed symptom and would make the wrong-link bug harder to detect.

Start.
```

---

*Written 2026-05-19. Keep this doc in sync with reality — if you change the MCP set, the plugins, or the slash commands, update §2 and §3.*
