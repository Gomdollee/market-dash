"""USD/KRW 환율. 1순위 yfinance(장중 갱신), 실패 시 frankfurter(ECB 기준환율, 하루 1회)."""

from __future__ import annotations

import logging
from datetime import date, timedelta

import requests

from market_dash import config
from market_dash.calc import Series
from market_dash.sources.market import fetch_close_history

log = logging.getLogger(__name__)


def _from_frankfurter(days: int = 400) -> Series:
    start = (date.today() - timedelta(days=days)).isoformat()
    url = config.FX_FALLBACK_URL.format(start=start)
    r = requests.get(url, headers=config.HTTP_HEADERS, timeout=config.HTTP_TIMEOUT)
    r.raise_for_status()
    rates = r.json()["rates"]
    series = sorted((d, float(v["KRW"])) for d, v in rates.items())
    if len(series) < 2:
        raise RuntimeError("frankfurter: 데이터 부족")
    return series


def fetch_usdkrw_history() -> tuple[Series, str]:
    """(시계열, 출처 이름)."""
    try:
        return fetch_close_history(config.FX_YF_SYMBOL, period="2y"), "Yahoo Finance"
    except Exception as e:  # noqa: BLE001 - 어떤 실패든 대체 소스로 넘어감
        log.warning("yfinance 환율 실패, frankfurter 로 대체: %s", e)
        return _from_frankfurter(), "Frankfurter (ECB)"
