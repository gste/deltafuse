from monitoring.usage_stats import UsageRecorder


def test_record_and_counts():
    recorder = UsageRecorder()
    recorder.record("login")
    recorder.record("login")
    recorder.record("logout")
    assert recorder.counts() == {"login": 2, "logout": 1}
