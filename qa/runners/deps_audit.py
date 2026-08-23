"""deps_audit - `npm audit --omit=dev --json` in frontend/. Report-only.

Findings: a high finding when high+critical exceed the Habib-accepted
baseline (config `deps_accepted_high`, default 8 - the known deferred set);
otherwise an info finding listing the counts. Subprocess injectable.
"""

import json
import os
import sys

from runners._base import EXIT_OK, emit, finding, main

RUNNER = "deps_audit"


def run(ctx, args):
    if ctx.dry_run and ctx.config.get("dry_run_skip_local"):
        emit(ctx, RUNNER, [finding("deps", "dry-run", RUNNER, "info", "npm audit skipped")])
        return EXIT_OK

    repo = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    npm = ctx.config.get("npm_path", "npm")
    timeout = int(ctx.config.get("deps_timeout_s", 300))
    accepted_high = int(ctx.config.get("deps_accepted_high", 8))

    try:
        result = ctx.run_subprocess(
            [npm, "audit", "--omit=dev", "--json"],
            cwd=os.path.join(repo, "frontend"),
            env=dict(os.environ),
            timeout=timeout,
        )
    except Exception as exc:  # noqa: BLE001
        emit(ctx, RUNNER, [finding("deps", "audit-error", RUNNER, "low", "npm audit could not run: %s" % exc)])
        return EXIT_OK

    # npm audit exits non-zero when advisories exist; the JSON is still on stdout.
    try:
        data = json.loads(result.get("stdout", "") or "{}")
    except ValueError:
        emit(ctx, RUNNER, [finding("deps", "audit-unparseable", RUNNER, "low", "npm audit produced no JSON")])
        return EXIT_OK

    vulns = (data.get("metadata") or {}).get("vulnerabilities") or {}
    high = int(vulns.get("high", 0)) + int(vulns.get("critical", 0))
    summary = "vulns: %s" % json.dumps(vulns)
    findings = []
    if high > accepted_high:
        findings.append(
            finding(
                "deps",
                "high-vulns-over-baseline",
                "frontend",
                "high",
                "%d high/critical (baseline %d). %s" % (high, accepted_high, summary),
            )
        )
    else:
        findings.append(finding("deps", "audit-counts", "frontend", "info", summary))

    emit(ctx, RUNNER, findings, extra={"vulnerabilities": vulns})
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(RUNNER, run))
