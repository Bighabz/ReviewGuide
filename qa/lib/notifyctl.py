"""CLI so run.ps1 / heartbeat-check.ps1 can send a notification.

    python -m lib.notifyctl <kind> "<text>"

kind in run_complete|run_failed|breach. Channel from config.notify_channel
(default telegram). Reads TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID (or RC_SCRIPT_PATH)
from qa/.env; never prints them. Prints "SENT" / "SKIPPED: <reason>".
"""

import json
import os
import subprocess
import sys

from lib import envfile, notify


def _config():
    from lib import config

    return config.load()


def _rc_runner(script_path, message):
    return subprocess.run(
        [
            r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            script_path,
            "-To",
            "3109515542",
            "-Message",
            message,
        ],
        capture_output=True,
        text=True,
    ).returncode


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) < 2:
        sys.stdout.write("SKIPPED: usage: notifyctl <kind> <text>\n")
        return 0
    kind, text = argv[0], argv[1]
    envfile.load_env(os.path.join(os.path.dirname(__file__), "..", ".env"))
    channel = _config().get("notify_channel", "telegram")

    try:
        if channel == "telegram":
            from lib import httpio

            token = os.environ.get("TELEGRAM_BOT_TOKEN")
            chat_id = os.environ.get("TELEGRAM_CHAT_ID")
            if not token or not chat_id:
                sys.stdout.write("SKIPPED: telegram creds not set in qa/.env\n")
                return 0
            sender = httpio.make_telegram_sender(token, chat_id)
            notify.dispatch(text, kind, "telegram", tg_sender=sender)
        else:
            notify.dispatch(text, kind, "rc", rc_runner=_rc_runner)
        sys.stdout.write("SENT\n")
    except Exception as exc:  # noqa: BLE001
        sys.stdout.write("SKIPPED: %s\n" % exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
