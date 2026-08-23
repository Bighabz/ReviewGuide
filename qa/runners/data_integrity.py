"""data_integrity - read-only Supabase reconciliation. NEVER writes.

Checks:
  (a) qa-auto conversation_messages: counted + listed into a prune manifest;
      a finding if the accumulated count exceeds config prune_warn_rows.
  (b) qa-auto affiliate_clicks: counted into the manifest.
  (c) kv_cache expired-but-present rows (sweeper health) - best-effort;
      skipped cleanly if the table/column shape differs.
Requires SUPABASE_QA_KEY (loaded from qa/.env by the runner harness); skips
with an info finding if the public_get seam is unavailable.
"""

import json
import os
import sys

from runners._base import EXIT_OK, emit, finding, main

RUNNER = "data_integrity"


def run(ctx, args):
    if ctx.dry_run:
        emit(ctx, RUNNER, [finding("data", "dry-run", RUNNER, "info", "reconciliation skipped")])
        return EXIT_OK

    findings = []
    manifest = {}

    # (a) qa-auto conversation_messages (prunable rows).
    try:
        rows = ctx.public_get(
            "/rest/v1/conversation_messages",
            {"select": "id,session_id", "session_id": "like.qa-auto-*", "limit": "10000"},
        )
        manifest["conversation_messages"] = [r.get("id") for r in rows]
        warn = int(ctx.config.get("prune_warn_rows", 2000))
        if len(rows) > warn:
            findings.append(
                finding(
                    "data",
                    "qa-rows-accumulating",
                    "conversation_messages",
                    "medium",
                    "%d qa-auto conversation_messages rows (>%d) - prune backlog" % (len(rows), warn),
                )
            )
        else:
            findings.append(
                finding("data", "qa-rows", "conversation_messages", "info", "%d qa-auto rows" % len(rows))
            )
    except Exception as exc:  # noqa: BLE001
        findings.append(finding("data", "reconcile-error", "conversation_messages", "low", "read failed: %s" % exc))

    # (b) qa-auto affiliate_clicks.
    try:
        clicks = ctx.public_get(
            "/rest/v1/affiliate_clicks",
            {"select": "id,session_id", "session_id": "like.qa-auto-*", "limit": "10000"},
        )
        manifest["affiliate_clicks"] = [r.get("id") for r in clicks]
    except Exception as exc:  # noqa: BLE001
        findings.append(finding("data", "reconcile-error", "affiliate_clicks", "low", "read failed: %s" % exc))

    # (c) kv_cache sweeper health (best-effort).
    try:
        stale = ctx.public_get(
            "/rest/v1/kv_cache",
            {"select": "key", "expires_at": "lt.%s" % ctx.now_fn(), "limit": "100"},
        )
        if stale:
            findings.append(
                finding(
                    "data",
                    "sweeper-lag",
                    "kv_cache",
                    "medium",
                    "%d expired kv_cache rows still present (sweeper lag)" % len(stale),
                )
            )
    except Exception:  # noqa: BLE001
        pass  # table/column shape differs - skip quietly

    if ctx.artifacts_dir:
        try:
            os.makedirs(ctx.artifacts_dir, exist_ok=True)
            with open(os.path.join(ctx.artifacts_dir, "qa-writes-manifest.json"), "w", encoding="utf-8") as fh:
                json.dump(manifest, fh, indent=2)
        except OSError:
            pass

    emit(ctx, RUNNER, findings)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(RUNNER, run))
