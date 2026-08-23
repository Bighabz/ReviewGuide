"""Notify for the QA loop (Habib-only).

Two channels, both driven by an injectable sender so unit tests stay
offline and no creds are ever logged here:

- Telegram (the P1 channel Habib chose 2026-08-22): `send_telegram(sender,
  ...)` where `sender` is a callable(message) -> result, built by
  httpio.make_telegram_sender from TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID.
- RingCentral SMS (dormant fallback): `send_sms(runner, ...)` where
  `runner` is a callable(script_path, text) -> result that shells to
  RC_SCRIPT_PATH Send-RcSms.

`dispatch(...)` routes to whichever channel the caller passes.
"""

import os

KINDS = ("run_complete", "run_failed", "breach")

_RC_SCRIPT_ENV = "RC_SCRIPT_PATH"


def _stamp(kind, text):
    if kind not in KINDS:
        raise ValueError(
            "unknown notify kind: %r (expected one of %s)" % (kind, KINDS)
        )
    return "[qa:%s] %s" % (kind, text)


def send_sms(runner, text, kind):
    """Send one SMS of the given kind via the injectable runner.

    Returns the runner result. Raises ValueError on an unknown kind and
    RuntimeError if RC_SCRIPT_PATH is not configured.
    """
    message = _stamp(kind, text)
    script_path = os.environ.get(_RC_SCRIPT_ENV)
    if not script_path:
        raise RuntimeError("%s is not set (see qa/.env.example)" % _RC_SCRIPT_ENV)
    return runner(script_path, message)


def send_telegram(sender, text, kind):
    """Send one Telegram message of the given kind via the injectable
    sender callable(message) -> result. Raises ValueError on unknown kind.
    The sender owns the token/chat_id (see httpio.make_telegram_sender);
    nothing is logged here."""
    message = _stamp(kind, text)
    return sender(message)


def dispatch(text, kind, channel, tg_sender=None, rc_runner=None):
    """Route one notification to `channel` ('telegram' or 'rc').

    Requires the matching sender to be supplied; raises RuntimeError if the
    chosen channel has no sender wired."""
    if channel == "telegram":
        if tg_sender is None:
            raise RuntimeError("telegram channel selected but no tg_sender supplied")
        return send_telegram(tg_sender, text, kind)
    if channel == "rc":
        if rc_runner is None:
            raise RuntimeError("rc channel selected but no rc_runner supplied")
        return send_sms(rc_runner, text, kind)
    raise ValueError("unknown notify channel: %r" % channel)
