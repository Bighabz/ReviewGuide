"""unit_suite - runs the LOCAL test suites (no prod). Report-only.

Each configured command runs via an injectable subprocess runner with a
timeout; a non-zero exit is one finding (dimension "unit"). Defaults are
the beeep-absolute commands; override via config `unit_suite_cmds`.
"""

import os
import sys

from runners._base import EXIT_OK, emit, finding, main

RUNNER = "unit_suite"

# [label, argv, cwd] - absolute paths (interactive PATH is absent under the
# scheduled-task account).
_DEFAULT_CMDS = [
    [
        "backend-pytest",
        [
            r"C:\Windows\System32\wsl.exe",
            "-d",
            "kali-linux",
            "-u",
            "root",
            "--",
            "bash",
            "-c",
            "cd /mnt/c/Users/habib/projects/ReviewGuide/backend && /root/rgvenv/bin/python -m pytest -q",
        ],
        None,
    ],
    ["frontend-vitest", [r"C:\Program Files\nodejs\npm.cmd", "run", "test:run"], "frontend"],
    ["frontend-tsc", [r"C:\Program Files\nodejs\npx.cmd", "tsc", "--noEmit"], "frontend"],
]


def run(ctx, args):
    if ctx.dry_run and ctx.config.get("dry_run_skip_local"):
        emit(ctx, RUNNER, [finding("unit", "dry-run", RUNNER, "info", "local suites skipped")])
        return EXIT_OK

    repo = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    cmds = ctx.config.get("unit_suite_cmds") or _DEFAULT_CMDS
    timeout = int(ctx.config.get("unit_timeout_s", 1800))
    findings = []
    tails = {}
    for label, argv, cwd in cmds:
        workdir = os.path.join(repo, cwd) if cwd else repo
        try:
            result = ctx.run_subprocess(argv, cwd=workdir, env=dict(os.environ), timeout=timeout)
        except Exception as exc:  # noqa: BLE001
            findings.append(finding("unit", "suite-error", label, "high", "%s could not run: %s" % (label, exc)))
            continue
        rc = result.get("returncode", 1)
        tails[label] = (result.get("stdout", "")[-400:], result.get("stderr", "")[-400:])
        if rc != 0:
            findings.append(finding("unit", "suite-failed", label, "high", "%s exited %s" % (label, rc)))

    emit(ctx, RUNNER, findings, extra={"tails": tails})
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(RUNNER, run))
