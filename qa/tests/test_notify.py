"""F4 tests: notify routes each kind through the injectable runner."""

import pytest

from lib import notify

SCRIPT = r"C:\me\morning-brief\bin\ringcentral.ps1"


class FakeRunner:
    def __init__(self):
        self.calls = []

    def __call__(self, script_path, message):
        self.calls.append((script_path, message))
        return "sent"


@pytest.fixture
def runner(monkeypatch):
    monkeypatch.setenv("RC_SCRIPT_PATH", SCRIPT)
    return FakeRunner()


@pytest.mark.parametrize("kind", ["run_complete", "run_failed", "breach"])
def test_routes_each_kind(runner, kind):
    result = notify.send_sms(runner, "run-1 finished", kind)
    assert result == "sent"
    script_path, message = runner.calls[0]
    assert script_path == SCRIPT
    assert message == "[qa:%s] run-1 finished" % kind


def test_kind_is_stamped_in_message(runner):
    notify.send_sms(runner, "marker lost on turn 2", "breach")
    assert runner.calls[0][1].startswith("[qa:breach]")


def test_unknown_kind_rejected(runner):
    with pytest.raises(ValueError):
        notify.send_sms(runner, "hi", "page_the_whole_team")


def test_missing_script_path_raises(monkeypatch):
    monkeypatch.delenv("RC_SCRIPT_PATH", raising=False)
    with pytest.raises(RuntimeError):
        notify.send_sms(FakeRunner(), "hi", "run_complete")
