"""RingCentral SMS notify for the QA loop (Habib-only, to 5542).

`runner` is an injectable callable(script_path, text) -> result; the real
implementation shells to RC_SCRIPT_PATH Send-RcSms (verified + pinned at
install). Unit tests pass a fake - no creds are ever logged here.
"""

import os

KINDS = ("run_complete", "run_failed", "breach")

_RC_SCRIPT_ENV = "RC_SCRIPT_PATH"


def send_sms(runner, text, kind):
    """Send one SMS of the given kind via the injectable runner.

    Returns the runner result. Raises ValueError on an unknown kind and
    RuntimeError if RC_SCRIPT_PATH is not configured.
    """
    if kind not in KINDS:
        raise ValueError(
            "unknown notify kind: %r (expected one of %s)" % (kind, KINDS)
        )
    script_path = os.environ.get(_RC_SCRIPT_ENV)
    if not script_path:
        raise RuntimeError("%s is not set (see qa/.env.example)" % _RC_SCRIPT_ENV)
    message = "[qa:%s] %s" % (kind, text)
    return runner(script_path, message)
