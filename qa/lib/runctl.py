"""Tiny CLI so run.ps1 can touch the qa.* store without handling secrets.

    python -m lib.runctl start  --run-id R --host H
    python -m lib.runctl beat   --run-id R
    python -m lib.runctl finish --run-id R --counts '{"high":1}'
    python -m lib.runctl last-beat            # prints YYYY-MM-DD of newest beat, or NONE

Reads SUPABASE_QA_KEY from qa/.env (loaded here) and uses the real httpio
executor. Never prints the key.
"""

import argparse
import json
import os
import sys

from lib import envfile, httpio, store


def _load_env():
    envfile.load_env(os.path.join(os.path.dirname(__file__), "..", ".env"))


def _last_beat_date():
    """Return the date (YYYY-MM-DD) of the most recent heartbeat, or None."""
    resp = httpio.execute(
        {
            "method": "GET",
            "url": store.BASE_URL + "/rest/v1/heartbeats",
            "headers": store._headers(),
            "query": {"select": "beat_at", "order": "beat_at.desc", "limit": "1"},
            "json": None,
        }
    )
    rows = resp.get("json") or []
    if rows and isinstance(rows, list):
        ts = str(rows[0].get("beat_at", ""))
        return ts[:10] or None
    return None


def main(argv=None):
    _load_env()
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("start", "beat", "finish"):
        sp = sub.add_parser(name)
        sp.add_argument("--run-id", required=True)
        sp.add_argument("--host", default="beeep")
        sp.add_argument("--counts", default="{}")
    sub.add_parser("last-beat")
    args = parser.parse_args(argv)

    if args.cmd == "start":
        store.start_run(httpio.execute, args.run_id, args.host)
    elif args.cmd == "beat":
        store.beat(httpio.execute, args.run_id)
    elif args.cmd == "finish":
        try:
            counts = json.loads(args.counts)
        except ValueError:
            counts = {}
        store.finish_run(httpio.execute, args.run_id, counts)
    elif args.cmd == "last-beat":
        sys.stdout.write((_last_beat_date() or "NONE") + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
