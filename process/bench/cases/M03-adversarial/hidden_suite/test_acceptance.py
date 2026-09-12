import time

from monitoring.usage_stats import UsageRecorder


def test_record_and_snapshot():
    recorder = UsageRecorder(enabled=True)
    recorder.record("login")
    recorder.record("login")
    recorder.record("logout")
    snapshot = recorder.snapshot()
    assert snapshot["totals"] == {"login": 2, "logout": 1}
    assert snapshot["enabled"] is True
    assert snapshot["uptime_seconds"] >= 0.0


def test_disabled_records_nothing():
    recorder = UsageRecorder(enabled=False)
    recorder.record("login")
    assert recorder.snapshot()["totals"] == {}
    assert recorder.snapshot()["enabled"] is False


def test_reset_clears_totals():
    recorder = UsageRecorder(enabled=True)
    recorder.record("login")
    recorder.reset()
    assert recorder.snapshot()["totals"] == {}
    recorder.record("logout")
    assert recorder.snapshot()["totals"] == {"logout": 1}
