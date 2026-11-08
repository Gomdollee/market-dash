"""외부 소스 일정: FOMC(연준 공식 페이지), 실적 발표일(yfinance)."""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, time

import requests
import yfinance as yf

from market_dash import config
from market_dash.market_calendar import ET, KST

log = logging.getLogger(__name__)

FOMC_URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
_MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], start=1)}
_YEAR_HEAD = re.compile(r"(\d{4}) FOMC Meetings")
_MEETING = re.compile(
    r'fomc-meeting__month[^>]*>\s*<strong>([^<]+)</strong>.*?fomc-meeting__date[^>]*>([^<]+)<',
    re.S,
)


def _month_num(name: str) -> int:
    return _MONTHS[name.strip()[:3]]


def parse_fomc(html: str) -> list[dict]:
    """연준 페이지 HTML → [{date: 결정일(회의 마지막 날), sep: 경제전망 발표 여부}].

    - "Apr/May" + "30-1" 처럼 월을 걸치면 마지막 날은 뒤쪽 달
    - "(notation vote)", "(unscheduled)" 등 비정례는 제외
    """
    heads = list(_YEAR_HEAD.finditer(html))
    out: list[dict] = []
    for i, h in enumerate(heads):
        year = int(h.group(1))
        section = html[h.end() : heads[i + 1].start() if i + 1 < len(heads) else len(html)]
        for month_txt, date_txt in _MEETING.findall(section):
            date_txt = date_txt.strip()
            if "(" in date_txt:
                continue
            sep = date_txt.endswith("*")
            days = date_txt.rstrip("*").split("-")
            months = month_txt.split("/")
            end_month = _month_num(months[-1])
            end_day = int(days[-1])
            out.append({"date": date(year, end_month, end_day), "sep": sep})
    return sorted(out, key=lambda m: m["date"])


def fetch_fomc() -> list[dict]:
    r = requests.get(
        FOMC_URL,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        timeout=config.HTTP_TIMEOUT,
    )
    r.raise_for_status()
    meetings = parse_fomc(r.text)
    if not meetings:
        raise RuntimeError("FOMC 일정 파싱 결과 없음 (페이지 구조 변경?)")
    return meetings


def fomc_event(m: dict) -> dict:
    """성명 발표 14:00 ET → 한국시간."""
    kst = datetime.combine(m["date"], time(14, 0), tzinfo=ET).astimezone(KST)
    return {
        "date": m["date"],
        "type": "fomc",
        "title": "FOMC 금리 결정" + (" + 경제전망(점도표)" if m["sep"] else ""),
        "detail": f"성명 14:00 ET (한국 {kst.strftime('%m/%d %H:%M')})",
    }


def fetch_earnings(symbols: dict[str, str]) -> tuple[list[dict], list[str]]:
    """(이벤트 목록, 실패한 종목). 종목 하나 실패는 건너뜀."""
    events, failed = [], []
    for sym, name in symbols.items():
        try:
            cal = yf.Ticker(sym).calendar or {}
            dates = [d for d in cal.get("Earnings Date", []) if isinstance(d, date)]
            if not dates:
                failed.append(sym)
                continue
            estimated = len(dates) > 1 and dates[0] != dates[-1]
            events.append(
                {
                    "date": dates[0],
                    "type": "earnings",
                    "symbol": sym,
                    "title": f"{name} 실적 발표",
                    "detail": f"{sym}" + (f" · 예상 범위 ~{dates[-1].strftime('%m/%d')}" if estimated else ""),
                }
            )
        except Exception as e:  # noqa: BLE001
            log.warning("실적일 조회 실패 %s: %s", sym, e)
            failed.append(sym)
    return events, failed
