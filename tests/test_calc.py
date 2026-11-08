import pytest

from market_dash.calc import (
    Peak,
    drawdown_pct,
    drawdown_series,
    find_peak,
    gold_krw,
    krw_change_pct,
    pct_change,
    rank_movers,
    threshold_gauge,
    value_on_or_before,
)

LINES = (-10.0, -20.0, -30.0, -40.0)


# ── pct_change ─────────────────────────────────────────


def test_pct_change_up_and_down():
    assert pct_change(110, 100) == pytest.approx(10.0)
    assert pct_change(90, 100) == pytest.approx(-10.0)


def test_pct_change_zero_base_raises():
    with pytest.raises(ValueError):
        pct_change(1, 0)


# ── 전고점 / 하락률 ────────────────────────────────────


def test_find_peak_returns_first_date_of_max():
    s = [("2026-01-01", 100.0), ("2026-01-02", 120.0), ("2026-01-03", 110.0), ("2026-01-04", 120.0)]
    assert find_peak(s) == Peak(value=120.0, date="2026-01-02")


def test_find_peak_empty_raises():
    with pytest.raises(ValueError):
        find_peak([])


def test_drawdown_pct():
    assert drawdown_pct(80, 100) == pytest.approx(-20.0)
    assert drawdown_pct(100, 100) == 0.0


def test_drawdown_never_positive():
    # 고점보다 높은 값이 들어와도(데이터 시차 등) 0 으로 캡
    assert drawdown_pct(105, 100) == 0.0


def test_drawdown_series_uses_running_peak():
    s = [("d1", 100.0), ("d2", 50.0), ("d3", 200.0), ("d4", 150.0)]
    rows = drawdown_series(s)
    assert [r["peak"] for r in rows] == [100.0, 100.0, 200.0, 200.0]
    assert [r["drawdown_pct"] for r in rows] == pytest.approx([0.0, -50.0, 0.0, -25.0])


# ── 기준선 게이지 ──────────────────────────────────────


def test_gauge_between_zero_and_first_line():
    g = threshold_gauge(-6.8, LINES)
    assert g.prev_line == 0.0
    assert g.next_line == -10.0
    assert g.remaining_pp == pytest.approx(3.2)
    assert g.progress == pytest.approx(0.68)


def test_gauge_at_peak_has_zero_progress():
    g = threshold_gauge(0.0, LINES)
    assert g.next_line == -10.0
    assert g.progress == 0.0
    assert g.remaining_pp == pytest.approx(10.0)


def test_gauge_exactly_on_line_points_to_next():
    g = threshold_gauge(-10.0, LINES)
    assert g.prev_line == -10.0
    assert g.next_line == -20.0
    assert g.remaining_pp == pytest.approx(10.0)
    assert g.progress == pytest.approx(0.0)


def test_gauge_between_later_lines():
    g = threshold_gauge(-27.5, LINES)
    assert (g.prev_line, g.next_line) == (-20.0, -30.0)
    assert g.remaining_pp == pytest.approx(2.5)
    assert g.progress == pytest.approx(0.75)


def test_gauge_beyond_last_line():
    g = threshold_gauge(-45.0, LINES)
    assert g.next_line is None
    assert g.remaining_pp is None
    assert g.prev_line == -40.0
    assert g.progress == 1.0


def test_gauge_line_order_does_not_matter():
    assert threshold_gauge(-15.0, (-40.0, -10.0, -30.0, -20.0)) == threshold_gauge(-15.0, LINES)


# ── 원화 환산 ──────────────────────────────────────────


def test_krw_change_compounds_index_and_fx():
    # 지수 +10%, 환율 +10% → 원화 기준 +21% (단순합 20% 아님)
    assert krw_change_pct(10.0, 10.0) == pytest.approx(21.0)


def test_krw_change_offsetting_moves():
    # 지수 -2%, 환율 +2% → -0.04%
    assert krw_change_pct(-2.0, 2.0) == pytest.approx(-0.04)


def test_krw_change_matches_converted_values():
    idx_prev, idx_now = 20000.0, 19500.0
    fx_prev, fx_now = 1350.0, 1380.0
    expected = pct_change(idx_now * fx_now, idx_prev * fx_prev)
    got = krw_change_pct(pct_change(idx_now, idx_prev), pct_change(fx_now, fx_prev))
    assert got == pytest.approx(expected)


def test_value_on_or_before():
    s = [("2026-11-03", 1.0), ("2026-11-05", 2.0), ("2026-11-06", 3.0)]
    assert value_on_or_before(s, "2026-11-05") == 2.0  # 당일
    assert value_on_or_before(s, "2026-11-04") == 1.0  # 휴일 → 직전
    assert value_on_or_before(s, "2026-12-01") == 3.0  # 이후 → 마지막
    assert value_on_or_before(s, "2026-11-01") is None  # 이전 데이터 없음


def test_gold_krw_per_ounce_and_don():
    # 1온스(31.1034768g) = 4000달러, 환율 1350 → 1온스 540만원
    assert gold_krw(4000, 1350, 31.1034768) == pytest.approx(5_400_000)
    # 1돈 3.75g
    assert gold_krw(4000, 1350, 3.75) == pytest.approx(5_400_000 / 31.1034768 * 3.75)


# ── 상위 종목 ──────────────────────────────────────────


def test_rank_movers():
    quotes = [
        {"symbol": "A", "change_pct": 5.0, "volume": 100},
        {"symbol": "B", "change_pct": -3.0, "volume": 900},
        {"symbol": "C", "change_pct": 1.0, "volume": None},
        {"symbol": "D", "change_pct": None, "volume": 5000},  # 변동률 없음 → 제외
        {"symbol": "E", "change_pct": -7.0, "volume": 300},
    ]
    r = rank_movers(quotes, 2)
    assert [q["symbol"] for q in r["gainers"]] == ["A", "C"]
    assert [q["symbol"] for q in r["losers"]] == ["E", "B"]
    assert [q["symbol"] for q in r["most_active"]] == ["B", "E"]
