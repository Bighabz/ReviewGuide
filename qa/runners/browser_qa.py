"""browser_qa - runs the committed Playwright checks and maps the JSON
report to findings.

Tier A only: the committed specs mock the chat stream and route-abort all
external hosts, so this runner makes ZERO real chat calls and ZERO real
outbound affiliate traffic. Tier B (real-chat browser E2E) is deliberately
deferred until after the live marker gate opens.

The subprocess runner is injectable (ctx.run_subprocess); unit tests pass a
fake and never invoke npx.
"""

import json
import os
import sys

from runners._base import EXIT_OK, emit, finding, main, redact_secrets

RUNNER = "browser_qa"

# Minimal env for the npx subprocess - NEVER pass the whole parent env (it
# carries SUPABASE_QA_KEY / TELEGRAM_BOT_TOKEN). Only what node/playwright need.
_ENV_WHITELIST = (
    "PATH",
    "PATHEXT",
    "SystemRoot",
    "SYSTEMROOT",
    "windir",
    "ComSpec",
    "TEMP",
    "TMP",
    "TMPDIR",
    "HOME",
    "USERPROFILE",
    "APPDATA",
    "LOCALAPPDATA",
    "ProgramFiles",
    "ProgramFiles(x86)",
    "ProgramData",
    "NUMBER_OF_PROCESSORS",
    "PLAYWRIGHT_BROWSERS_PATH",
    "NODE_PATH",
)


def _parse_report(report):
    """Walk a Playwright JSON report; return a list of failed spec titles.

    Defensive: an unrecognized shape yields [] (the caller then trusts the
    process return code / stats instead)."""
    failed = []

    def walk(suite):
        for spec in suite.get("specs", []) or []:
            title = spec.get("title", "<unknown>")
            if spec.get("ok") is False:
                failed.append(title)
        for child in suite.get("suites", []) or []:
            walk(child)

    if not isinstance(report, dict):
        return failed
    for suite in report.get("suites", []) or []:
        walk(suite)
    return failed


def run(ctx, args):
    if ctx.dry_run:
        emit(
            ctx,
            RUNNER,
            [finding("browser", "dry-run", RUNNER, "info", "dry_run: playwright not run")],
            extra={"skipped": True},
        )
        return EXIT_OK

    pw_dir = os.path.join(os.path.dirname(__file__), "..", "playwright")
    run_dir = os.path.join(ctx.artifacts_dir or ".", "playwright")
    npx = ctx.config.get("npx_path", "npx")
    timeout = int(ctx.config.get("browser_timeout_s", 900))

    env = {k: os.environ[k] for k in _ENV_WHITELIST if k in os.environ}
    env["BASE_URL"] = ctx.config["prod_frontend"]
    env["QA_RUN_DIR"] = run_dir
    env["QA_RUN_ID"] = ctx.run_id

    cmd = [npx, "playwright", "test", "--reporter=json"]

    try:
        result = ctx.run_subprocess(cmd, cwd=pw_dir, env=env, timeout=timeout)
    except Exception as exc:  # noqa: BLE001
        emit(
            ctx,
            RUNNER,
            [finding("browser", "playwright-unavailable", RUNNER, "medium", "playwright did not run: %s" % exc)],
            extra={"error": str(exc)},
        )
        return EXIT_OK

    stdout = result.get("stdout", "") or ""
    returncode = result.get("returncode", 1)
    report = None
    try:
        report = json.loads(stdout)
    except ValueError:
        report = None

    # Redact any secret value before the report touches disk (a spec could
    # log env; emit() redacts elsewhere but this artifact is written here).
    if ctx.artifacts_dir and stdout:
        try:
            os.makedirs(ctx.artifacts_dir, exist_ok=True)
            with open(
                os.path.join(ctx.artifacts_dir, "playwright-report.json"),
                "w",
                encoding="utf-8",
            ) as handle:
                handle.write(redact_secrets(stdout))
        except OSError:
            pass

    findings = []
    failed_titles = _parse_report(report) if report is not None else []
    for title in failed_titles:
        findings.append(
            finding("browser", "spec-failed", title, "medium", "playwright spec failed: %s" % title)
        )
    report_errors = (report or {}).get("errors") if isinstance(report, dict) else None
    # A non-zero exit with no per-spec failures (config error, zero tests run,
    # top-level errors[]) must NOT pass as green just because the JSON parsed.
    if returncode != 0 and not failed_titles:
        findings.append(
            finding(
                "browser",
                "playwright-nonzero-exit",
                RUNNER,
                "medium",
                "playwright exited %s with no failed specs parsed (errors=%s)"
                % (returncode, bool(report_errors)),
            )
        )

    emit(ctx, RUNNER, findings, extra={"returncode": returncode})
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(RUNNER, run))
