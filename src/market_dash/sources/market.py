"""yfinance 로 지수·종목·ETF 시세 수집. (yfinance 는 비공식 → 언제든 실패 가능)"""

from __future__ import annotations

import math

import pandas as pd
import yfinance as yf

from market_dash.calc import Series, pct_change


def _to_series(closes: pd.Series) -> Series:
    closes = closes.dropna()
    return [(ts.strftime("%Y-%m-%d"), float(v)) for ts, v in closes.items()]


def fetch_close_history(symbol: str, period: str = "max") -> Series:
    """일별 종가 시계열. 전고점 계산을 위해 기본은 전체 기간."""
    df = yf.Ticker(symbol).history(period=period, auto_adjust=False)
    if df.empty or "Close" not in df:
        raise RuntimeError(f"{symbol}: 시세 데이터가 비어 있음")
    series = _to_series(df["Close"])
    if len(series) < 2:
        raise RuntimeError(f"{symbol}: 데이터가 2일 미만")
    return series


def fetch_quotes(symbols: list[str], period: str = "10d") -> list[dict]:
    """여러 종목의 최근 종가·전일 대비·거래량을 한 번에 조회.

    종목마다 마지막 두 개의 유효 종가를 쓴다(신규 상장·거래정지 등 결측 대비).
    """
    df = yf.download(
        symbols,
        period=period,
        group_by="column",
        auto_adjust=False,
        progress=False,
        threads=True,
    )
    if df.empty:
        raise RuntimeError("일괄 시세 조회 결과가 비어 있음")

    closes, volumes = df["Close"], df["Volume"]
    quotes: list[dict] = []
    for sym in symbols:
        if sym not in closes:
            continue
        c = closes[sym].dropna()
        if len(c) < 2:
            continue
        last, prev = float(c.iloc[-1]), float(c.iloc[-2])
        vol = volumes[sym].get(c.index[-1]) if sym in volumes else None
        quotes.append(
            {
                "symbol": sym,
                "date": c.index[-1].strftime("%Y-%m-%d"),
                "close": last,
                "prev_close": prev,
                "change_pct": pct_change(last, prev),
                "volume": None if vol is None or math.isnan(vol) else int(vol),
            }
        )
    if not quotes:
        raise RuntimeError("유효한 종목 시세가 하나도 없음")
    return quotes
