"""미국 증시 일정 - 규칙 기반 계산 (순수 함수, 네트워크 없음).

- NYSE 휴장일 / 조기폐장(13:00 ET)
- 월간 옵션 만기(셋째 금요일), 분기 만기 = 네 마녀의 날(3·6·9·12월)
- 미국 서머타임 전환 → 한국시간 개장 시각 변화

주의: 대통령 국장 등 임시 휴장은 규칙으로 알 수 없다.
날짜는 전부 미국 동부(현지) 날짜 기준.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo  # ≈ java.time.ZoneId

ET = ZoneInfo("America/New_York")
KST = ZoneInfo("Asia/Seoul")

MON, TUE, WED, THU, FRI, SAT, SUN = range(7)
REGULAR_OPEN = time(9, 30)
REGULAR_CLOSE = time(16, 0)
EARLY_CLOSE = time(13, 0)


# ── 날짜 규칙 도우미 ────────────────────────────────────


def nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """그 달의 n번째 weekday (n=1 부터). 예: 11월 넷째 목요일."""
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + 7 * (n - 1))


def last_weekday(year: int, month: int, weekday: int) -> date:
    nxt = date(year + (month == 12), month % 12 + 1, 1)
    last = nxt - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def easter(year: int) -> date:
    """그레고리력 부활절 (Anonymous Gregorian algorithm)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7  # noqa: E741
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


def observed(d: date) -> date:
    """토요일 → 금요일, 일요일 → 월요일 대체."""
    if d.weekday() == SAT:
        return d - timedelta(days=1)
    if d.weekday() == SUN:
        return d + timedelta(days=1)
    return d


# ── 휴장 / 조기폐장 ─────────────────────────────────────


def nyse_holidays(year: int) -> dict[date, str]:
    h: dict[date, str] = {}

    # 신정: 일요일이면 월요일 대체, 토요일이면 대체 없음 (전년 12/31 은 개장)
    ny = date(year, 1, 1)
    if ny.weekday() == SUN:
        h[ny + timedelta(days=1)] = "신정(대체)"
    elif ny.weekday() != SAT:
        h[ny] = "신정"

    h[nth_weekday(year, 1, MON, 3)] = "마틴 루서 킹 데이"
    h[nth_weekday(year, 2, MON, 3)] = "대통령의 날"
    h[easter(year) - timedelta(days=2)] = "성금요일(Good Friday)"
    h[last_weekday(year, 5, MON)] = "메모리얼 데이"
    if year >= 2022:
        h[observed(date(year, 6, 19))] = "준틴스(노예해방기념일)"
    h[observed(date(year, 7, 4))] = "독립기념일"
    h[nth_weekday(year, 9, MON, 1)] = "노동절"
    h[nth_weekday(year, 11, THU, 4)] = "추수감사절"
    h[observed(date(year, 12, 25))] = "크리스마스"
    return h


def is_trading_day(d: date, holidays: dict[date, str] | None = None) -> bool:
    if d.weekday() >= SAT:
        return False
    holidays = holidays if holidays is not None else nyse_holidays(d.year)
    return d not in holidays


def early_closes(year: int) -> dict[date, str]:
    """13:00 ET 조기폐장일. 해당 날짜가 평일이고 휴장이 아닐 때만."""
    hol = nyse_holidays(year)
    candidates = {
        date(year, 7, 3): "독립기념일 전날",
        nth_weekday(year, 11, THU, 4) + timedelta(days=1): "추수감사절 다음 날",
        date(year, 12, 24): "크리스마스이브",
    }
    return {d: name for d, name in candidates.items() if is_trading_day(d, hol)}


def previous_trading_day(d: date) -> date:
    d -= timedelta(days=1)
    while not is_trading_day(d):
        d -= timedelta(days=1)
    return d


# ── 옵션 만기 ───────────────────────────────────────────


def monthly_opex(year: int, month: int) -> date:
    """셋째 금요일. 휴장이면 직전 거래일 (예: 성금요일과 겹치면 목요일)."""
    d = nth_weekday(year, month, FRI, 3)
    return d if is_trading_day(d) else previous_trading_day(d)


def is_quad_witching_month(month: int) -> bool:
    return month in (3, 6, 9, 12)


# ── 서머타임 / 한국시간 ─────────────────────────────────


def dst_transitions(year: int) -> tuple[date, date]:
    """(시작: 3월 둘째 일요일, 종료: 11월 첫째 일요일)."""
    return nth_weekday(year, 3, SUN, 2), nth_weekday(year, 11, SUN, 1)


def session_kst(d: date, early: bool = False) -> tuple[datetime, datetime]:
    """미국 날짜 d 의 정규장 개장·마감을 한국시간으로."""
    open_et = datetime.combine(d, REGULAR_OPEN, tzinfo=ET)
    close_et = datetime.combine(d, EARLY_CLOSE if early else REGULAR_CLOSE, tzinfo=ET)
    return open_et.astimezone(KST), close_et.astimezone(KST)


def fmt_kst(dt: datetime) -> str:
    return dt.strftime("%H:%M")


def upcoming_sessions(from_date: date, count: int) -> list[dict]:
    """from_date 부터 거래일 count 개의 정규장 시각(한국시간 ISO).

    화면에서 '지금 장 열림/닫힘, 다음 개장' 을 보는 시점 기준으로 판단하는 데 쓴다.
    """
    early = {}
    out: list[dict] = []
    d = from_date
    while len(out) < count:
        if d.year not in early:
            early[d.year] = early_closes(d.year)
        if is_trading_day(d):
            is_early = d in early[d.year]
            o, c = session_kst(d, early=is_early)
            out.append({"date": d.isoformat(), "open": o.isoformat(), "close": c.isoformat(), "early": is_early})
        d += timedelta(days=1)
    return out


# ── 이벤트 목록 ─────────────────────────────────────────


def rule_events(start: date, end: date) -> list[dict]:
    """[start, end] 구간의 규칙 기반 이벤트. 날짜순."""
    events: list[dict] = []
    for year in range(start.year, end.year + 1):
        for d, name in nyse_holidays(year).items():
            events.append({"date": d, "type": "holiday", "title": f"휴장 · {name}"})

        for d, name in early_closes(year).items():
            _, close = session_kst(d, early=True)
            events.append(
                {
                    "date": d,
                    "type": "early_close",
                    "title": f"조기폐장 · {name}",
                    "detail": f"13:00 ET 마감 (한국 {close.strftime('%m/%d')} {fmt_kst(close)})",
                }
            )

        for month in range(1, 13):
            d = monthly_opex(year, month)
            if is_quad_witching_month(month):
                events.append(
                    {
                        "date": d,
                        "type": "witching",
                        "title": "네 마녀의 날 (분기 옵션·선물 동시 만기)",
                        "detail": "변동성·거래량 확대 주의",
                    }
                )
            else:
                events.append({"date": d, "type": "opex", "title": "월간 옵션 만기"})

        for d, starts in zip(dst_transitions(year), (True, False)):
            first_session = d + timedelta(days=1)
            while not is_trading_day(first_session):
                first_session += timedelta(days=1)
            o, c = session_kst(first_session)
            events.append(
                {
                    "date": d,
                    "type": "dst",
                    "title": f"미국 서머타임 {'시작' if starts else '종료'}",
                    "detail": f"정규장 한국시간 {fmt_kst(o)}~{fmt_kst(c)}",
                }
            )

    picked = [e for e in events if start <= e["date"] <= end]
    return sorted(picked, key=lambda e: (e["date"], e["type"]))


def is_market_open(now: datetime) -> bool:
    """now(시간대 포함) 가 미국 정규장 시간 안인지. 휴장·조기폐장 반영 (임시 휴장은 모름)."""
    d = now.astimezone(ET).date()
    if not is_trading_day(d):
        return False
    o, c = session_kst(d, early=d in early_closes(d.year))
    return o <= now < c
