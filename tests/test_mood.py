import pytest

from market_dash.explain import fear_greed_zone, mood_summary, vix_zone
from market_dash.sources.sentiment import parse_fear_greed


@pytest.mark.parametrize("score,label", [
    (0, "극단적 공포"), (24.4, "극단적 공포"), (24.6, "공포"),  # 화면엔 25로 보이므로 '공포'
    (44, "공포"), (45, "중립"), (55, "중립"), (56, "탐욕"), (75, "탐욕"), (76, "극단적 탐욕"), (100, "극단적 탐욕"),
])
def test_fear_greed_zone_boundaries(score, label):
    assert fear_greed_zone(score)["label"] == label


def test_fear_greed_levels_increase_with_greed():
    assert [fear_greed_zone(s)["level"] for s in (10, 30, 50, 60, 90)] == [0, 1, 2, 3, 4]


@pytest.mark.parametrize("vix,label", [
    (11.2, "평온"), (14.99, "평온"), (15, "보통"), (19.9, "보통"), (20, "불안"), (29.99, "불안"),
    (30, "공포"), (39.9, "공포"), (40, "패닉"), (82.7, "패닉"),
])
def test_vix_zone_boundaries(vix, label):
    assert vix_zone(vix)["label"] == label


def test_mood_summary():
    assert mood_summary(22.08, 25.64) == [
        "투자자 심리는 100점 만점에 22점, '극단적 공포' 상태예요.",
        "공포지수(VIX)는 25.6, '불안' 수준이에요.",
    ]
    assert mood_summary(None, None) == []


def _cnn(score=22.08, points=()):
    return {
        "fear_and_greed": {"score": score, "timestamp": "2026-11-06T23:59:54+00:00", "previous_close": 19.9,
                           "previous_1_week": 26.3, "previous_1_month": 47.0, "previous_1_year": 24.3},
        "fear_and_greed_historical": {"data": [{"x": x, "y": y} for x, y in points]},
    }


def test_parse_fear_greed_dedupes_same_day_keeping_last():
    day = 1793923200000.0  # 2026-11-06 00:00 UTC
    out = parse_fear_greed(_cnn(points=[(day - 86400000, 30.0), (day, 21.0), (day + 86394000, 22.08)]))
    assert out["history"] == [("2026-11-05", 30.0), ("2026-11-06", 22.08)]
    assert out["score"] == 22.08 and out["week_ago"] == 26.3


def test_parse_fear_greed_keeps_recent_days_only():
    pts = [(1793923200000.0 - i * 86400000, 50.0) for i in range(200)]
    assert len(parse_fear_greed(_cnn(points=pts), keep_days=95)["history"]) == 95


def test_parse_fear_greed_rejects_out_of_range():
    with pytest.raises(ValueError):
        parse_fear_greed(_cnn(score=130))
