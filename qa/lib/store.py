"""Supabase store for qa.* tables (mgmt API over PostgREST).

Every function BUILDS the request and hands it to an injectable
executor(request) -> response; no network happens here unless the
executor performs it (unit tests pass a fake).

Findings are IMMUTABLE per-run observations keyed (run_id, fingerprint),
tagged with runner_version so a runner bump resets the P2 baseline
instead of poisoning it. Lifecycle classification is deferred to P2.
"""

import os

SCHEMA = "qa"
BASE_URL = "https://qvowmjjcotdonezdtvur.supabase.co"

# Cloudflare-UA workaround (memory supabase-mgmt-api-cloudflare-ua): the
# management API path rejects non-browser user agents.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)

_SERVICE_KEY_ENV = "SUPABASE_QA_KEY"


def _service_key():
    """Read the service key from the environment. Never logged."""
    key = os.environ.get(_SERVICE_KEY_ENV)
    if not key:
        raise RuntimeError("%s is not set (see qa/.env.example)" % _SERVICE_KEY_ENV)
    return key


def _headers(prefer=None):
    headers = {
        "apikey": _service_key(),
        "Authorization": "Bearer %s" % _service_key(),
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
        "Accept-Profile": SCHEMA,
        "Content-Profile": SCHEMA,
    }
    if prefer:
        headers["Prefer"] = prefer
    return headers


def _request(executor, method, path, payload, prefer=None, query=None):
    return executor(
        {
            "method": method,
            "url": BASE_URL + path,
            "headers": _headers(prefer),
            "query": dict(query or {}),
            "json": payload,
        }
    )


def start_run(executor, run_id, host):
    """Insert a new qa.runs row (started, counts zeroed)."""
    payload = {
        "run_id": run_id,
        "host": host,
        "status": "running",
        "counts": {},
    }
    return _request(
        executor, "POST", "/rest/v1/runs", payload, prefer="return=minimal"
    )


def beat(executor, run_id):
    """Insert a qa.heartbeats row for run_id (dead-man switch input)."""
    payload = {"run_id": run_id}
    return _request(
        executor, "POST", "/rest/v1/heartbeats", payload, prefer="return=minimal"
    )


def record_observation(
    executor,
    run_id,
    fingerprint,
    dimension,
    severity,
    summary,
    locus,
    status,
    runner_version,
):
    """Write an IMMUTABLE observation keyed (run_id, fingerprint).

    Prior-run rows are never overwritten; P2 derives NEW/OPEN/FIXED/
    REGRESSED lifecycle from history. runner_version lets a runner bump
    reset the baseline.
    """
    payload = {
        "run_id": run_id,
        "fingerprint": fingerprint,
        "dimension": dimension,
        "severity": severity,
        "summary": summary,
        "locus": locus,
        "status": status,
        "runner_version": runner_version,
    }
    return _request(
        executor,
        "POST",
        "/rest/v1/observations",
        payload,
        prefer="resolution=ignore-duplicates,return=minimal",
        query={"on_conflict": "run_id,fingerprint"},
    )


def finish_run(executor, run_id, counts):
    """Mark a qa.runs row finished with its final counts."""
    payload = {"status": "finished", "counts": counts}
    return _request(
        executor,
        "PATCH",
        "/rest/v1/runs",
        payload,
        prefer="return=minimal",
        query={"run_id": "eq.%s" % run_id},
    )
