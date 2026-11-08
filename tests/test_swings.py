from market_dash.swings import (
    Pivot,
    drawdown_episodes,
    find_swings,
    recovery_date,
    swing_label,
    weekly,
    zigzag,
)


def S(*values):
    """값만 주면 2026-01-01 부터 하루씩 날짜를 붙인다."""
    from datetime import date, timedelta

    return [((date(2026, 1, 1) + timedelta(days=i)).isoformat(), float(v)) for i, v in enumerate(values)]


def test_zigzag_ignores_small_moves():
    pivots, ongoing = zigzag(S(100, 105, 98, 104, 101), 10)
    assert pivots == [] and ongoing is None


def test_zigzag_finds_peak_and_trough():
    # 100 → 130(고점) → 100(저점, -23%) → 125(+25%, 진행 중)
    series = S(100, 115, 130, 120, 100, 110, 125)
    pivots, ongoing = zigzag(series, 10)
    assert [(p.value, p.kind) for p in pivots] == [(100, "trough"), (130, "peak"), (100, "trough")]
    assert ongoing == Pivot(series[6][0], 125, "peak")


def test_zigzag_small_pullback_does_not_end_trend():
    pivots, ongoing = zigzag(S(100, 120, 112, 140), 10)  # 120→112 는 -6.7% 라 무시
    assert [p.value for p in pivots] == [100]
    assert ongoing.value == 140


def test_find_swings_newest_first_with_recovery_and_ongoing():
    series = S(100, 115, 130, 120, 100, 110, 125, 131, 128)
    swings = find_swings(series, 10, since="2000-01-01")
    assert [s["kind"] for s in swings] == ["up", "down", "up"]

    up_now = swings[0]
    assert up_now["ongoing"] is True
    assert up_now["end"]["value"] == 131
    assert up_now["current"]["value"] == 128

    down = swings[1]
    assert down["change_pct"] == round((100 / 130 - 1) * 100, 2)
    assert down["label"] == "약세장급 급락"
    assert down["recovered"] == {"date": series[7][0], "days_from_bottom": 3}  # 131 ≥ 130


def test_find_swings_unrecovered_drop():
    series = S(100, 130, 100, 112)  # 130→100 후 아직 130 회복 못함, 112 는 +12% 진행 중
    down = [s for s in find_swings(series, 10, "2000-01-01") if s["kind"] == "down"][0]
    assert down["recovered"] is None


def test_find_swings_since_filter():
    series = S(100, 130, 100, 125)
    swings = find_swings(series, 10, since=series[3][0])
    assert len(swings) == 1 and swings[0]["kind"] == "up"


def test_swing_label():
    assert swing_label(-25) == "약세장급 급락"
    assert swing_label(-12) == "조정"
    assert swing_label(15) == "반등"
    assert swing_label(30) == "급등"


def test_recovery_date():
    s = S(100, 80, 90, 100, 95)
    assert recovery_date(s, s[1][0], 100) == s[3][0]
    assert recovery_date(s, s[1][0], 101) is None


def test_drawdown_episode_spans_whole_bear_market_despite_bounces():
    # 고점 100 → 80 → 반등 90 → 바닥 65 → 회복 101. 중간 반등이 있어도 하나의 에피소드
    s = S(100, 80, 90, 65, 85, 101)
    eps = drawdown_episodes(s, 10, "2000-01-01")
    assert len(eps) == 1
    e = eps[0]
    assert e["peak"]["value"] == 100 and e["bottom"]["value"] == 65
    assert e["depth_pct"] == -35.0
    assert e["recovered"]["date"] == s[5][0]
    assert e["recovered"]["days_from_bottom"] == 2
    assert e["recovered"]["days_total"] == 5


def test_drawdown_episode_ongoing_and_small_dips_ignored():
    s = S(100, 95, 101, 120, 100, 104)  # 100→95(-5%) 무시, 120→100(-16.7%) 미회복
    eps = drawdown_episodes(s, 10, "2000-01-01")
    assert len(eps) == 1
    assert eps[0]["peak"]["value"] == 120
    assert eps[0]["recovered"] is None
    assert eps[0]["label"] == "조정"


def test_drawdown_episode_since_filter_uses_end_date():
    s = S(100, 70, 100, 130, 110, 131)
    eps = drawdown_episodes(s, 10, since=s[4][0])  # 첫 에피소드는 s[2] 에 회복 → 제외
    assert [e["peak"]["value"] for e in eps] == [130]


def test_weekly_keeps_last_close_of_each_week():
    # 2026-01-01(목) ~ 01-11(일): 1주차(1/1~1/4), 2주차(1/5~1/11)
    s = S(*range(11))
    assert weekly(s) == [("2026-01-04", 3.0), ("2026-01-11", 10.0)]
