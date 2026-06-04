#!/usr/bin/env bash
# ask-codex.sh — pipe a prompt to OpenAI Codex in headless, read-only review mode.
#
# Usage:
#   ./scripts/ask-codex.sh "your question here"
#   ./scripts/ask-codex.sh -f prompt.txt          # read prompt from a file
#   echo "your question" | ./scripts/ask-codex.sh  # read prompt from stdin
#
# Notes:
#   - Codex is installed but NOT on PATH; the binary lives under a version-hash
#     folder that changes on update, so we locate it dynamically.
#   - The prompt MUST be piped via stdin with `exec -`; passing it as a
#     positional arg hangs this build ("Reading additional input from stdin...").
#   - Sandbox: this Windows build's `read-only` sandbox is broken — every spawned
#     command dies with "windows sandbox: spawn setup refresh" before it can read
#     a file. So we default to `danger-full-access` (skips Codex's sandbox). The
#     review prompt only reads, so this is safe on a trusted machine. Override with
#     CODEX_SANDBOX=read-only|workspace-write|danger-full-access if the build is fixed.
#   - Ignore any "rmcp ... AuthRequired" lines: those are other MCP servers
#     (Vercel/Supabase) failing to auth and do not affect the answer.
set -euo pipefail

CODEX_ROOT="${CODEX_ROOT:-/c/Users/$(whoami)/AppData/Local/OpenAI/Codex/bin}"
CODEX_SANDBOX="${CODEX_SANDBOX:-danger-full-access}"
CODEX=$(find "$CODEX_ROOT" -name codex.exe 2>/dev/null | head -1)

if [ -z "${CODEX:-}" ]; then
  echo "ask-codex: could not find codex.exe under $CODEX_ROOT" >&2
  echo "  Set CODEX_ROOT to the OpenAI Codex bin dir and retry." >&2
  exit 1
fi

# Gather the prompt: -f FILE, positional args, or stdin.
if [ "${1:-}" = "-f" ] && [ -n "${2:-}" ]; then
  PROMPT=$(cat "$2")
elif [ "$#" -gt 0 ]; then
  PROMPT="$*"
else
  PROMPT=$(cat)
fi

printf '%s' "$PROMPT" | "$CODEX" exec --sandbox "$CODEX_SANDBOX" --skip-git-repo-check -
