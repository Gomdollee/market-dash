"""순수 계산 함수. 네트워크·파일 I/O 없음 → 단위 테스트 대상.

(≈ Spring에서 외부 의존 없는 도메인 서비스. 입력만으로 결과가 정해지므로 Mock 이 필요 없다.)

단위 규칙: 변동률·하락률은 전부 "퍼센트" (예: -6.8 은 -6.8%).
시계열은 (날짜 문자열 'YYYY-MM-DD', 값) 튜플의 리스트이고 날짜 오름차순이다.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass

Series = list[tuple[str, float]]


def pct_change(new: float, old: float) -> float:
    """old → new 변동률(%)."""
    if old == 0:
        raise ValueError("기준값이 0 이면 변동률을 계산할 수 없음")
    return (new / old - 1.0) * 100.0


# ── 전고점 / 하락률 ─────────────────────────────────────


@dataclass(frozen=True)  # ≈ Java record (불변 값 객체)
class Peak:
    value: float
    date: str


def find_peak(series: Series) -> Peak:
    """최고값과 그 날짜. 같은 최고값이 여러 번이면 처음 도달한 날짜."""
    if not series:
        raise ValueError("빈 시계열")
    best_date, best_value = series[0]
    for d, v in series[1:]:
        if v > best_value:
            best_date, best_value = d, v
    return Peak(value=best_value, date=best_date)


def drawdown_pct(current: float, peak: float) -> float:
    """고점 대비 하락률(%). 항상 0 이하."""
    if peak <= 0:
        raise ValueError("고점은 양수여야 함")
    return min(0.0, pct_change(current, peak))


def drawdown_series(series: Series) -> list[dict]:
    """각 날짜의 '그날까지의 최고 종가' 대비 하락률.

    시계열 전체(가능하면 상장 이후 전부)를 넣어야 고점이 정확하다.
    """
    rows: list[dict] = []
    running_peak = float("-inf")
    for d, v in series:
        running_peak = max(running_peak, v)
        rows.append(
            {
                "date": d,
                "close": v,
                "peak": running_peak,
                "drawdown_pct": drawdown_pct(v, running_peak),
            }
        )
    return rows


# ── 하락 기준선 게이지 ──────────────────────────────────


@dataclass(frozen=True)
class Gauge:
    prev_line: float  # 이미 지난(또는 출발점) 기준선. 시작은 0
    next_line: float | None  # 다음 기준선. 모두 돌파했으면 None
    remaining_pp: float | None  # 다음 선까지 남은 %p (양수)
    progress: float  # prev_line → next_line 구간 진행률 0.0~1.0


def threshold_gauge(dd_pct: float, lines: tuple[float, ...]) -> Gauge:
    """현재 하락률이 기준선들 사이 어디쯤인지.

    예) dd=-6.8, lines=(-10,-20,...) → prev 0, next -10, 남은 3.2%p, 진행 68%
    정확히 선에 닿으면(dd == -10) 그 선은 '도달'로 보고 다음 선을 가리킨다.
    """
    ordered = sorted(lines, reverse=True)  # -10, -20, -30, -40
    prev = 0.0
    for line in ordered:
        if dd_pct > line:
            progress = (prev - dd_pct) / (prev - line)
            return Gauge(
                prev_line=prev,
                next_line=line,
                remaining_pp=dd_pct - line,
                progress=min(1.0, max(0.0, progress)),
            )
        prev = line
    return Gauge(prev_line=ordered[-1], next_line=None, remaining_pp=None, progress=1.0)


# ── 원화 환산 ───────────────────────────────────────────


def krw_change_pct(index_pct: float, fx_pct: float) -> float:
    """원화 기준 변동률(%) = (1+지수변동)×(1+환율변동) - 1.

    단순 합(index_pct + fx_pct)은 근사치이고 이 식이 정확한 값이다.
    """
    return ((1 + index_pct / 100.0) * (1 + fx_pct / 100.0) - 1.0) * 100.0


def gold_krw(usd_per_oz: float, usdkrw: float, grams: float, troy_oz_g: float = 31.1034768) -> float:
    """국제 금값(달러/트로이온스) → grams 그램당 원화. 세금·수수료·국내 프리미엄 제외."""
    return usd_per_oz * usdkrw / troy_oz_g * grams


def value_on_or_before(series: Series, date: str) -> float | None:
    """date 당일, 없으면 그 이전 가장 가까운 날의 값. 없으면 None.

    지수(미국 거래일)와 환율(다른 휴일)의 날짜를 맞출 때 쓴다.
    'YYYY-MM-DD' 문자열은 사전순 = 날짜순이라 문자열 비교로 충분하다.
    """
    dates = [d for d, _ in series]
    i = bisect_right(dates, date)
    return series[i - 1][1] if i else None


# ── 상위 종목 ───────────────────────────────────────────


def rank_movers(quotes: list[dict], n: int) -> dict[str, list[dict]]:
    """quotes: [{symbol, change_pct, volume, ...}] → 상승/하락/거래량 상위 n개."""
    valid = [q for q in quotes if q.get("change_pct") is not None]
    gainers = sorted(valid, key=lambda q: q["change_pct"], reverse=True)[:n]
    losers = sorted(valid, key=lambda q: q["change_pct"])[:n]
    active = sorted(
        (q for q in valid if q.get("volume") is not None),
        key=lambda q: q["volume"],
        reverse=True,
    )[:n]
    return {"gainers": gainers, "losers": losers, "most_active": active}
