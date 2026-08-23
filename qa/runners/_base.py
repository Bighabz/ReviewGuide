"""Shared runner protocol: context, finding/emit helpers, exit codes.

Everything a runner touches that could hit the network or the clock is an
injectable attribute on RunnerContext, so unit tests build a context with
fakes and never go online. A dry_run context replaces the network seams
with guards that RAISE if called - proving in tests that dry runs make
zero prod calls.
"""

import argparse
import json
import os

from lib import envfile, flake, store

# Exit-code contract (see runners/__init__.py).
EXIT_OK = 0
EXIT_CRASH = 2
EXIT_BREACH = 3

# Env keys whose VALUES must never appear in an artifact.
_SECRET_ENV_KEYS = (
    "SUPABASE_QA_KEY",
    "TELEGRAM_BOT_TOKEN",
    "RC_SCRIPT_PATH",
    "QA_BYPASS_TOKEN",
)

SEVERITIES = ("low", "medium", "high", "info")


def _config_path():
    return os.path.join(os.path.dirname(__file__), "..", "config.json")


def load_config():
    with open(_config_path(), "r", encoding="utf-8") as handle:
        return json.load(handle)


def _network_guard(*_args, **_kwargs):
    raise RuntimeError("network disabled in dry_run context")


def _real_subprocess(cmd, cwd=None, env=None, timeout=None):
    """Run a child process, capture output. Returns
    {returncode, stdout, stderr}. Used by browser_qa (non-dry only)."""
    import subprocess

    proc = subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        timeout=timeout,
        capture_output=True,
        text=True,
    )
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout or "",
        "stderr": proc.stderr or "",
    }


class RunnerContext(object):
    """Everything a runner needs, all injectable.

    Network seams (store_exec, post_fn, query_fn, http_get, http_options,
    run_subprocess) are guards in a dry_run context. Clock/entropy seams
    (now_fn, rand_fn, sleep_fn) let tests be deterministic.
    """

    def __init__(
        self,
        config,
        run_id,
        artifacts_dir,
        dry_run=True,
        store_exec=None,
        post_fn=None,
        query_fn=None,
        http_get=None,
        http_post=None,
        http_options=None,
        run_subprocess=None,
        now_fn=None,
        rand_fn=None,
        sleep_fn=None,
    ):
        self.config = config
        self.run_id = run_id
        self.artifacts_dir = artifacts_dir
        self.dry_run = dry_run
        guard = _network_guard
        self.store_exec = store_exec or guard
        self.post_fn = post_fn or guard
        self.query_fn = query_fn or guard
        self.http_get = http_get or guard
        self.http_post = http_post or guard
        self.http_options = http_options or guard
        self.run_subprocess = run_subprocess or guard
        self.now_fn = now_fn or (lambda: "1970-01-01T00:00:00Z")
        self.rand_fn = rand_fn or (lambda: "00000000")
        self.sleep_fn = sleep_fn or (lambda _s: None)

    @property
    def runner_version(self):
        return str(self.config.get("runner_version", "1"))


def finding(dimension, check, locus, severity, summary, status="OPEN"):
    """Build a finding dict with a stable fingerprint.

    fingerprint = sha1(dimension + check + locus) so the same defect keeps
    one identity across runs (P2 history keys on it)."""
    if severity not in SEVERITIES:
        raise ValueError("bad severity %r" % severity)
    return {
        "fingerprint": flake.fingerprint(dimension, check, locus),
        "dimension": dimension,
        "check": check,
        "locus": locus,
        "severity": severity,
        "summary": summary,
        "status": status,
    }


def _collect_secrets(environ=None):
    environ = environ if environ is not None else os.environ
    secrets = []
    for key in _SECRET_ENV_KEYS:
        value = environ.get(key)
        if value:
            secrets.append(value)
    return secrets


def redact(text, secrets):
    """Replace every secret value in `text` with [redacted]."""
    for secret in secrets:
        if secret:
            text = text.replace(secret, "[redacted]")
    return text


def redact_secrets(text, environ=None):
    """Redact all known env secret values from `text`."""
    return redact(text, _collect_secrets(environ))


def emit(ctx, runner_name, findings, extra=None, environ=None):
    """Write <artifacts_dir>/<runner>.json and, when not dry_run, persist
    each finding as an immutable observation.

    The artifact is scrubbed of any secret value before it hits disk.
    Returns the artifact path.
    """
    payload = {
        "runner": runner_name,
        "run_id": ctx.run_id,
        "runner_version": ctx.runner_version,
        "dry_run": ctx.dry_run,
        "findings": findings,
    }
    if extra:
        payload["extra"] = extra
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    text = redact(text, _collect_secrets(environ))
    if ctx.artifacts_dir:
        try:
            os.makedirs(ctx.artifacts_dir, exist_ok=True)
        except OSError:
            pass
        path = os.path.join(ctx.artifacts_dir, "%s.json" % runner_name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
    else:
        path = None
    if not ctx.dry_run:
        for f in findings:
            store.record_observation(
                ctx.store_exec,
                run_id=ctx.run_id,
                fingerprint=f["fingerprint"],
                dimension=f["dimension"],
                severity=f["severity"],
                summary=f["summary"],
                locus=f["locus"],
                status=f["status"],
                runner_version=ctx.runner_version,
            )
    return path


def build_real_context(run_id, artifacts_dir, config=None):
    """Wire a context to the real httpio seams (or guards if dry_run)."""
    import time

    from lib import httpio

    config = config or load_config()
    dry = bool(config.get("dry_run", True))
    ctx_kwargs = dict(
        config=config,
        run_id=run_id,
        artifacts_dir=artifacts_dir,
        dry_run=dry,
        now_fn=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        rand_fn=lambda: os.urandom(4).hex(),
        sleep_fn=time.sleep,
    )
    if not dry:
        chat_url = config["prod_backend"].rstrip("/") + "/v1/chat/stream"
        ctx_kwargs.update(
            store_exec=httpio.execute,
            post_fn=lambda payload: httpio.sse_post(chat_url, payload),
            query_fn=httpio.pg_rest_query,
            http_get=httpio.status_get,
            http_post=httpio.post_status,
            http_options=httpio.options_cors,
            run_subprocess=_real_subprocess,
        )
    return RunnerContext(**ctx_kwargs)


def standard_argv(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--artifacts-dir", default="")
    parser.add_argument("--prove-marker", action="store_true")
    return parser.parse_args(argv)


def load_dotenv_if_present():
    """Load qa/.env (gitignored) into the environment if it exists."""
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    return envfile.load_env(env_path)


def main(runner_name, run_fn, argv=None):
    """Entry harness for `python -m runners.<name>`.

    Loads qa/.env, builds a real context, calls run_fn(ctx, args) which
    returns an exit code. An unhandled exception becomes EXIT_CRASH (the
    breach path returns EXIT_BREACH explicitly)."""
    args = standard_argv(argv)
    load_dotenv_if_present()
    try:
        ctx = build_real_context(args.run_id, args.artifacts_dir)
        return run_fn(ctx, args)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 - top-level guard
        import sys

        sys.stderr.write("%s crashed: %s\n" % (runner_name, exc))
        return EXIT_CRASH
