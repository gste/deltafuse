from ratelimit.stats import UsageStats


def test_stats_unknown_key_is_zero():
    stats = UsageStats()
    s = stats.snapshot('nobody')
    assert s['total'] == 0
    assert s['success'] == 0
    assert s['rejected'] == 0
    assert s['peak_per_sec'] == 0


def test_stats_total_equals_success_plus_rejected():
    stats = UsageStats()
    stats.record('u', success=True)
    stats.record('u', success=False)
    stats.record('u', success=False)
    s = stats.snapshot('u')
    assert s['total'] == 3
    assert s['success'] == 1
    assert s['rejected'] == 2
    assert s['total'] == s['success'] + s['rejected']


def test_stats_peak_per_sec():
    stats = UsageStats()
    for _ in range(5):
        stats.record('u', success=True)
    assert stats.snapshot('u')['peak_per_sec'] >= 1
