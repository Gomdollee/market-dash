import pytest

from market_dash.explain import (
    _duration,
    drawdown_zone,
    five_year_summary,
    fx_summary,
    index_summary,
    krw_summary,
)


@pytest.mark.parametrize("days, text", [(23, "23일"), (60, "약 2개월"), (365, "약 1년"), (790, "약 2년 2개월")])
def test_duration(days, text):
    assert _duration(days) == text


def test_five_year_summary_picks_worst_episode():
    eps = [
        {"peak": {"date": "2024-12-16"}, "bottom": {"date": "2025-04-08"}, "depth_pct": -24.3,
         "recovered": {"days_from_bottom": 80}},
        {"peak": {"date": "2021-11-19"}, "bottom": {"date": "2022-12-28"}, "depth_pct": -35.4,
         "recovered": {"days_from_bottom": 428}},
    ]
    assert five_year_summary("나스닥 지수는", eps) == [
        "지난 5년 동안 나스닥 지수는 최고점보다 10% 넘게 떨어진 적이 2번 있었어요.",
        "가장 크게 떨어진 건 2021.11~2022.12의 -35.4%예요.",
        "그때는 바닥에서 다시 최고점을 회복하기까지 약 1년 2개월 걸렸어요.",
    ]


def test_five_year_summary_empty():
    assert "없어요" in five_year_summary("S&P 500 지수는", [])[0]


@pytest.mark.parametrize(
    "dd, label",
    [(0.0, "고점 근처"), (-4.9, "고점 근처"), (-5.0, "약한 하락"), (-9.99, "약한 하락"),
     (-10.0, "조정"), (-19.9, "조정"), (-20.0, "약세장"), (-35.0, "깊은 약세장"), (-40.0, "역사적 폭락")],
)
def test_drawdown_zone_boundaries(dd, label):
    assert drawdown_zone(dd)["label"] == label


def test_index_summary_in_correction():
    assert index_summary("나스닥 지수는", 1.09, -10.94, -20.0, 9.06) == [
        "나스닥 지수는 지난 거래일에 1.09% 올랐어요.",
        "최고점보다 10.9% 낮은 '조정' 상태예요.",
        "'약세장' 단계(-20%)까지 9.1%p 더 떨어지면 도달해요.",
    ]


def test_index_summary_at_peak_and_down_day():
    lines = index_summary("S&P 500 지수는", -0.5, 0.0, -10.0, 10.0)
    assert lines[0] == "S&P 500 지수는 지난 거래일에 0.50% 내렸어요."
    assert lines[1] == "지금이 사상 최고점이에요!"


def test_index_summary_beyond_last_line_has_no_next_sentence():
    assert len(index_summary("나스닥 지수는", 0.0, -45.0, None, None)) == 2


def test_fx_summary_up_down_flat():
    assert fx_summary(1356.34, 1340.07)[0] == "환율이 16원 올랐어요 (1달러 = 1,356원)."
    assert "줄어들어요" in fx_summary(1340.0, 1356.0)[1]
    assert fx_summary(1350.0, 1350.0) == ["환율은 그대로예요 (1달러 = 1,350원)."]


def test_fx_summary_small_change_shows_decimal():
    assert fx_summary(1350.4, 1350.0)[0].startswith("환율이 0.4원 올랐어요")


def test_krw_summary():
    assert krw_summary("나스닥 지수는", 2.31, 1.09, 1.21) == "원화로 투자했다면 나스닥 지수는 +2.31%예요 (달러 기준 +1.09% + 환율 +1.21% 효과)."


def test_gold_subject():
    assert index_summary("금 값은", -1.0, -26.7, -30.0, 3.3)[0] == "금 값은 지난 거래일에 1.00% 내렸어요."
