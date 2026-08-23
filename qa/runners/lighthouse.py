"""lighthouse - headless Lighthouse on / and /chat (desktop + mobile).

Report-only. Findings: any category < 90 (medium); CLS > 0.1 or LCP > 4s
(medium). A lighthouse crash is a low finding, never a runner crash.
Subprocess injectable; tests feed canned lighthouse JSON.
"""

import json
import os
import sys

from runners._base import EXIT_OK, emit, finding, main

RUNNER = "lighthouse"
_CATEGORIES = ("performance", "accessibility", "best-practices", "seo")


def _score(report, cat):
    c = ((report or {}).get("categories") or {}).get(cat) or {}
    s = c.get("score")
    return None if s is None else float(s) * 100.0


def _audit_numeric(report, audit_id):
    a = ((report or {}).get("audits") or {}).get(audit_id) or {}
    return a.get("numericValue")


def _evaluate(label, report):
    findings = []
    for cat in _CATEGORIES:
        score = _score(report, cat)
        if score is not None and score < 90:
            findings.append(
                finding("lighthouse", "low-score:%s" % cat, label, "medium", "%s %s = %.0f (<90)" % (label, cat, score))
            )
    cls = _audit_numeric(report, "cumulative-layout-shift")
    if cls is not None and float(cls) > 0.1:
        findings.append(finding("lighthouse", "cls", label, "medium", "%s CLS %.3f (>0.1)" % (label, float(cls))))
    lcp = _audit_numeric(report, "largest-contentful-paint")
    if lcp is not None and float(lcp) > 4000:
        findings.append(finding("lighthouse", "lcp", label, "medium", "%s LCP %.0fms (>4s)" % (label, float(lcp))))
    return findings


def run(ctx, args):
    if ctx.dry_run:
        emit(ctx, RUNNER, [finding("lighthouse", "dry-run", RUNNER, "info", "lighthouse skipped")])
        return EXIT_OK

    lh = ctx.config.get("lighthouse_path", "lighthouse")
    base = ctx.config["prod_frontend"].rstrip("/")
    timeout = int(ctx.config.get("lighthouse_timeout_s", 180))
    targets = [("home", base + "/"), ("chat", base + "/chat")]
    findings = []
    for label, url in targets:
        cmd = [
            lh,
            url,
            "--quiet",
            "--output=json",
            "--chrome-flags=--headless=new --no-sandbox",
            "--only-categories=%s" % ",".join(_CATEGORIES),
        ]
        try:
            result = ctx.run_subprocess(cmd, cwd=None, env=dict(os.environ), timeout=timeout)
            report = json.loads(result.get("stdout", "") or "{}")
        except Exception as exc:  # noqa: BLE001
            findings.append(finding("lighthouse", "unavailable", label, "low", "lighthouse failed on %s: %s" % (label, exc)))
            continue
        findings.extend(_evaluate(label, report))

    emit(ctx, RUNNER, findings)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(RUNNER, run))
