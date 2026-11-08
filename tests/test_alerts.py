from datetime import datetime, timezone

import pytest

from market_dash.alerts import detect_alerts
from market_dash.market_calendar import is_market_open


def snap(chg=-0.5, dd=-5.0, as_of="2026-11-09", vix=None, key="nasdaq"):
    return {
        "assets": {key: {"name": "나스닥", "as_of": as_of, "close": 24000.0,
                         "change_pct": chg, "drawdown_pct": dd, "when": "장중 23:30"}},
        "vix": None if vix is None else {"close": vix, "when": "장중 23:30"},
    }


def test_no_alert_on_quiet_day():
    msgs, state = detect_alerts(snap(), {})
    assert msgs == []
    assert state == {"day": {}, "dd": {}, "vix": None}


def test_day_drop_alerts_once_per_step_and_escalates():
    msgs, st = detect_alerts(snap(chg=-2.3), {})
    assert len(msgs) == 1 and "-2.30%" in msgs[0]
    # 30분 뒤에도 -2.5% → 같은 단계라 조용
    msgs, st = detect_alerts(snap(chg=-2.5), st)
    assert msgs == []
    # -3.4% → 더 깊은 단계라 다시 알림
    msgs, st = detect_alerts(snap(chg=-3.4), st)
    assert len(msgs) == 1 and st["day"]["nasdaq"]["step"] == -3.0
    # 다음 거래일에 -2.1% → 날짜가 바뀌었으니 다시 알림
    msgs, _ = detect_alerts(snap(chg=-2.1, as_of="2026-11-10"), st)
    assert len(msgs) == 1


def test_big_jump_down_reports_only_deepest_step():
    msgs, st = detect_alerts(snap(chg=-5.6), {})
    assert len(msgs) == 1 and st["day"]["nasdaq"]["step"] == -5.0


def test_rise_never_alerts():
    assert detect_alerts(snap(chg=4.0), {})[0] == []


def test_drawdown_line_cross_and_reset_after_recovery():
    msgs, st = detect_alerts(snap(dd=-10.2), {})
    assert len(msgs) == 1 and "'조정'(-10%)" in msgs[0]
    # -10% 근처에서 오르내려도 반복 알림 없음 (2%p 이상 회복해야 초기화)
    msgs, st = detect_alerts(snap(dd=-9.1), st)
    assert msgs == [] and st["dd"]["nasdaq"] == -10.0
    msgs, st = detect_alerts(snap(dd=-10.5), st)
    assert msgs == []
    # -7.5% 까지 회복 → 초기화, 다시 -10% 아래면 알림
    _, st = detect_alerts(snap(dd=-7.5), st)
    assert st["dd"]["nasdaq"] is None
    msgs, _ = detect_alerts(snap(dd=-10.1), st)
    assert len(msgs) == 1


def test_drawdown_deeper_line_alerts():
    _, st = detect_alerts(snap(dd=-12.0), {})
    msgs, st = detect_alerts(snap(dd=-20.4), st)
    assert len(msgs) == 1 and "'약세장'(-20%)" in msgs[0]


def test_vix_cross_and_reset():
    msgs, st = detect_alerts(snap(vix=31.0), {})
    assert len(msgs) == 1 and "30 돌파" in msgs[0]
    assert detect_alerts(snap(vix=29.0), st)[0] == []  # 3 이상 내려와야 초기화
    msgs, st = detect_alerts(snap(vix=42.0), st)
    assert len(msgs) == 1 and "40 돌파" in msgs[0]
    _, st = detect_alerts(snap(vix=25.0), st)
    assert st["vix"] is None


def test_detect_does_not_mutate_input_state():
    state = {"day": {}, "dd": {}, "vix": None}
    detect_alerts(snap(chg=-3, dd=-15, vix=35), state)
    assert state == {"day": {}, "dd": {}, "vix": None}


@pytest.mark.parametrize("utc,expected", [
    ("2026-11-09T14:29:00", False),  # 월 09:29 ET (개장 전, EST)
    ("2026-11-09T14:30:00", True),   # 09:30 ET 개장
    ("2026-11-09T20:59:00", True),
    ("2026-11-09T21:00:00", False),  # 16:00 ET 마감
    ("2026-11-07T15:00:00", False),  # 토요일
    ("2026-11-26T15:00:00", False),  # 추수감사절 휴장
    ("2026-11-27T18:30:00", False),  # 다음 날 13:00 ET 조기폐장 이후
    ("2026-07-06T13:30:00", True),   # 서머타임(EDT) 09:30
])
def test_is_market_open(utc, expected):
    assert is_market_open(datetime.fromisoformat(utc).replace(tzinfo=timezone.utc)) is expected
