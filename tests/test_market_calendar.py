"""NYSE 공표 일정과 대조. (기대값 출처: NYSE Holidays & Trading Hours)"""

from datetime import date

import pytest

from market_dash.market_calendar import (
    dst_transitions,
    early_closes,
    easter,
    is_trading_day,
    monthly_opex,
    nyse_holidays,
    rule_events,
    session_kst,
)

D = date


@pytest.mark.parametrize(  # ≈ JUnit @ParameterizedTest
    "year, expected",
    [
        (2025, [D(2025, 1, 1), D(2025, 1, 20), D(2025, 2, 17), D(2025, 4, 18), D(2025, 5, 26),
                D(2025, 6, 19), D(2025, 7, 4), D(2025, 9, 1), D(2025, 11, 27), D(2025, 12, 25)]),
        (2026, [D(2026, 1, 1), D(2026, 1, 19), D(2026, 2, 16), D(2026, 4, 3), D(2026, 5, 25),
                D(2026, 6, 19), D(2026, 7, 3), D(2026, 9, 7), D(2026, 11, 26), D(2026, 12, 25)]),
        (2027, [D(2027, 1, 1), D(2027, 1, 18), D(2027, 2, 15), D(2027, 3, 26), D(2027, 5, 31),
                D(2027, 6, 18), D(2027, 7, 5), D(2027, 9, 6), D(2027, 11, 25), D(2027, 12, 24)]),
    ],
)
def test_nyse_holidays(year, expected):
    assert sorted(nyse_holidays(year)) == expected


def test_new_year_on_saturday_has_no_observed_holiday():
    # 2022-01-01 토요일 → 대체 휴일 없음, 2021-12-31(금)은 개장
    assert D(2022, 1, 1) not in nyse_holidays(2022)
    assert D(2021, 12, 31) not in nyse_holidays(2021)
    assert is_trading_day(D(2021, 12, 31))


def test_christmas_on_sunday_moves_to_monday():
    assert D(2022, 12, 26) in nyse_holidays(2022)


def test_juneteenth_only_from_2022():
    assert D(2021, 6, 18) not in nyse_holidays(2021)


@pytest.mark.parametrize("year, expected", [(2024, D(2024, 3, 31)), (2025, D(2025, 4, 20)),
                                            (2026, D(2026, 4, 5)), (2027, D(2027, 3, 28))])
def test_easter(year, expected):
    assert easter(year) == expected


@pytest.mark.parametrize(
    "year, expected",
    [
        (2025, [D(2025, 7, 3), D(2025, 11, 28), D(2025, 12, 24)]),
        (2026, [D(2026, 11, 27), D(2026, 12, 24)]),  # 7/3 이 휴장(대체) → 7/2 조기폐장 없음
        (2027, [D(2027, 11, 26)]),  # 7/3 토요일, 12/24 휴장
    ],
)
def test_early_closes(year, expected):
    assert sorted(early_closes(year)) == expected


def test_opex_third_friday():
    assert monthly_opex(2026, 11) == D(2026, 11, 20)
    assert monthly_opex(2026, 3) == D(2026, 3, 20)


def test_opex_moves_to_thursday_when_friday_is_holiday():
    assert monthly_opex(2025, 4) == D(2025, 4, 17)  # 성금요일
    assert monthly_opex(2026, 6) == D(2026, 6, 18)  # 준틴스


def test_dst_transitions_2026():
    assert dst_transitions(2026) == (D(2026, 3, 8), D(2026, 11, 1))


def test_session_kst_summer_and_winter():
    o, c = session_kst(D(2026, 7, 15))
    assert (o.strftime("%m/%d %H:%M"), c.strftime("%m/%d %H:%M")) == ("07/15 22:30", "07/16 05:00")
    o, c = session_kst(D(2026, 11, 9))
    assert (o.strftime("%H:%M"), c.strftime("%H:%M")) == ("23:30", "06:00")
    _, c = session_kst(D(2026, 11, 27), early=True)
    assert c.strftime("%m/%d %H:%M") == "11/28 03:00"


def test_rule_events_november_2026():
    ev = rule_events(D(2026, 11, 1), D(2026, 11, 30))
    got = [(e["date"], e["type"]) for e in ev]
    assert got == [
        (D(2026, 11, 1), "dst"),
        (D(2026, 11, 20), "opex"),
        (D(2026, 11, 26), "holiday"),
        (D(2026, 11, 27), "early_close"),
    ]
    assert ev[0]["detail"] == "정규장 한국시간 23:30~06:00"


def test_upcoming_sessions_skip_weekend_and_holiday():
    from market_dash.market_calendar import upcoming_sessions

    s = upcoming_sessions(D(2026, 11, 25), 3)  # 수, (목 휴장), 금 조기폐장, (주말), 월
    assert [x["date"] for x in s] == ["2026-11-25", "2026-11-27", "2026-11-30"]
    assert s[1]["early"] is True
    assert s[1]["close"] == "2026-11-28T03:00:00+09:00"
    assert s[2]["open"] == "2026-11-30T23:30:00+09:00"


def test_rule_events_marks_quad_witching():
    ev = rule_events(D(2026, 6, 1), D(2026, 6, 30))
    witching = [e for e in ev if e["type"] == "witching"]
    assert [e["date"] for e in witching] == [D(2026, 6, 18)]
