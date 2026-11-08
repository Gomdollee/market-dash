from datetime import date

import pytest

from market_dash.main import _month_range


@pytest.mark.parametrize(
    "today, ahead, expected",
    [
        (date(2026, 11, 8), 2, (date(2026, 11, 1), date(2027, 1, 31))),
        (date(2026, 1, 31), 1, (date(2026, 1, 1), date(2026, 2, 28))),
        (date(2026, 12, 15), 0, (date(2026, 12, 1), date(2026, 12, 31))),
    ],
)
def test_month_range(today, ahead, expected):
    assert _month_range(today, ahead) == expected


# ── 급락 알림 흐름 ──────────────────────────────────────
from datetime import datetime as _dt, timezone as _tz

import pytest as _pytest

from market_dash import config as _config
from market_dash import main as _main
from market_dash.storage import FetchResult as _FR


def _results(chg):
    idx = {"as_of": "2026-11-09", "close": 24000.0, "change_pct": chg, "drawdown_pct": -5.0, "live": True}
    res = {k: _FR(ok=False, error="x") for k in _config.INDICES}
    res["nasdaq"] = _FR(ok=True, data=idx)
    res["vix"] = _FR(ok=False, error="x")
    return res


@_pytest.fixture
def tg(monkeypatch, tmp_path):
    sent = []
    monkeypatch.setattr(_config, "ALERT_STATE_PATH", tmp_path / "alerts.json")
    monkeypatch.setattr(_main.telegram, "credentials", lambda: ("t", "c"))
    monkeypatch.setattr(_main.telegram, "send", lambda text, creds: sent.append(text))
    return sent


NOW = _dt(2026, 11, 9, 15, 0, tzinfo=_tz.utc)


def test_notify_first_run_sends_connection_message_then_alerts(tg):
    assert _main.notify(_results(-0.4), NOW) == "연결 확인 메시지 전송"
    assert "연결됐어요" in tg[0] and "나스닥" in tg[0]
    assert _main.notify(_results(-0.6), NOW) == "알릴 것 없음"
    assert _main.notify(_results(-2.4), NOW) == "알림 1건 전송"
    assert "장중 00:00" in tg[-1] and _config.PAGE_URL in tg[-1]


def test_notify_does_not_save_state_when_send_fails(tg, monkeypatch):
    _main.notify(_results(-0.4), NOW)

    def boom(text, creds):
        raise RuntimeError("down")
    monkeypatch.setattr(_main.telegram, "send", boom)
    with _pytest.raises(RuntimeError):
        _main.notify(_results(-2.4), NOW)
    monkeypatch.setattr(_main.telegram, "send", lambda text, creds: tg.append(text))
    assert _main.notify(_results(-2.4), NOW) == "알림 1건 전송"  # 다음 실행에 재시도


def test_notify_skips_without_credentials(monkeypatch):
    monkeypatch.setattr(_main.telegram, "credentials", lambda: None)
    assert "건너뜀" in _main.notify(_results(-5), NOW)
