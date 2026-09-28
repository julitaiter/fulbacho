from app.modules.stats.service import minimum_matches_for_win_rate


def test_win_rate_minimum_rule():
    assert minimum_matches_for_win_rate(1) == 1
    assert minimum_matches_for_win_rate(5) == 1
    assert minimum_matches_for_win_rate(6) == 2
    assert minimum_matches_for_win_rate(10) == 2
    assert minimum_matches_for_win_rate(12) == 3
    assert minimum_matches_for_win_rate(15) == 3
    assert minimum_matches_for_win_rate(16) == 5
