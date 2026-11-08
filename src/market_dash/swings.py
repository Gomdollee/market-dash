"""큰 상승·하락 구간 찾기 (지그재그) - 순수 함수.

지그재그: 직전 고점에서 threshold% 이상 떨어지면 그 고점을 '확정 고점'으로,
직전 저점에서 threshold% 이상 오르면 그 저점을 '확정 저점'으로 찍는다.
확정된 꼭짓점 사이가 하나의 구간(swing)이고, 마지막 꼭짓점 이후는 '진행 중' 구간이다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from market_dash.calc import Series, pct_change


@dataclass(frozen=True)
class Pivot:
    date: str
    value: float
    kind: str  # "peak" | "trough"


def zigzag(series: Series, threshold_pct: float) -> tuple[list[Pivot], Pivot | None]:
    """(확정 꼭짓점 목록, 진행 중 구간의 현재 극값). 추세가 아직 안 정해졌으면 ([], None)."""
    if len(series) < 2:
        return [], None
    t = threshold_pct / 100.0
    first = series[0]
    hi = lo = first
    trend: str | None = None
    ext = first
    pivots: list[Pivot] = []

    for d, v in series[1:]:
        if trend is None:
            if v > hi[1]:
                hi = (d, v)
            if v < lo[1]:
                lo = (d, v)
            if v >= lo[1] * (1 + t):
                pivots.append(Pivot(lo[0], lo[1], "trough"))
                trend, ext = "up", (d, v)
            elif v <= hi[1] * (1 - t):
                pivots.append(Pivot(hi[0], hi[1], "peak"))
                trend, ext = "down", (d, v)
        elif trend == "up":
            if v > ext[1]:
                ext = (d, v)
            elif v <= ext[1] * (1 - t):
                pivots.append(Pivot(ext[0], ext[1], "peak"))
                trend, ext = "down", (d, v)
        else:  # down
            if v < ext[1]:
                ext = (d, v)
            elif v >= ext[1] * (1 + t):
                pivots.append(Pivot(ext[0], ext[1], "trough"))
                trend, ext = "up", (d, v)

    if trend is None:
        return [], None
    ongoing = Pivot(ext[0], ext[1], "peak" if trend == "up" else "trough")
    return pivots, ongoing


def swing_label(change_pct: float) -> str:
    if change_pct <= -20:
        return "약세장급 급락"
    if change_pct < 0:
        return "조정"
    if change_pct >= 20:
        return "급등"
    return "반등"


def _days(a: str, b: str) -> int:
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


def recovery_date(series: Series, after: str, target: float) -> str | None:
    """after 이후 처음으로 종가가 target 이상이 된 날."""
    for d, v in series:
        if d > after and v >= target:
            return d
    return None


def find_swings(series: Series, threshold_pct: float, since: str) -> list[dict]:
    """끝난 날짜가 since 이후인 구간들 (최신순). 마지막 구간은 ongoing=True 일 수 있다."""
    pivots, ongoing = zigzag(series, threshold_pct)
    if not pivots:
        return []
    points = pivots + ([ongoing] if ongoing else [])
    last_date, last_value = series[-1]

    swings: list[dict] = []
    for i in range(1, len(points)):
        a, b = points[i - 1], points[i]
        is_ongoing = ongoing is not None and i == len(points) - 1
        change = pct_change(b.value, a.value)
        if b.date < since or abs(change) < threshold_pct:
            continue
        s = {
            "kind": "down" if change < 0 else "up",
            "label": swing_label(change),
            "start": {"date": a.date, "value": round(a.value, 2)},
            "end": {"date": b.date, "value": round(b.value, 2)},
            "change_pct": round(change, 2),
            "days": _days(a.date, b.date),
            "ongoing": is_ongoing,
        }
        if s["kind"] == "down":
            rec = recovery_date(series, b.date, a.value)
            s["recovered"] = {"date": rec, "days_from_bottom": _days(b.date, rec)} if rec else None
        if is_ongoing:
            s["current"] = {"date": last_date, "value": round(last_value, 2),
                            "from_end_pct": round(pct_change(last_value, b.value), 2)}
        swings.append(s)
    return list(reversed(swings))


def drawdown_episodes(series: Series, min_depth_pct: float, since: str) -> list[dict]:
    """최고점 대비 min_depth_pct% 이상 떨어졌던 에피소드 (최신순).

    에피소드 = 사상 최고점 → 바닥 → 다시 그 최고점 회복(또는 아직 회복 중).
    끝(회복일, 미회복이면 마지막 날)이 since 이후인 것만.
    """
    out: list[dict] = []
    if not series:
        return out
    peak = series[0]
    trough: tuple[str, float] | None = None

    def record(recovered_on: str | None) -> None:
        depth = pct_change(trough[1], peak[1])
        end = recovered_on or series[-1][0]
        if depth <= -min_depth_pct and end >= since:
            out.append({
                "peak": {"date": peak[0], "value": round(peak[1], 2)},
                "bottom": {"date": trough[0], "value": round(trough[1], 2)},
                "depth_pct": round(depth, 2),
                "fall_days": _days(peak[0], trough[0]),
                "recovered": (
                    {"date": recovered_on, "days_from_bottom": _days(trough[0], recovered_on),
                     "days_total": _days(peak[0], recovered_on)}
                    if recovered_on else None
                ),
                "label": swing_label(depth),
            })

    for d, v in series[1:]:
        if v >= peak[1]:
            if trough is not None:
                record(d)
            peak, trough = (d, v), None
        elif trough is None or v < trough[1]:
            trough = (d, v)
    if trough is not None:
        record(None)
    return list(reversed(out))


def weekly(series: Series) -> Series:
    """주별 마지막 종가로 줄이기 (차트용). ISO 주 기준."""
    out: dict[tuple[int, int], tuple[str, float]] = {}
    for d, v in series:
        iso = date.fromisoformat(d).isocalendar()
        out[(iso.year, iso.week)] = (d, v)
    return [out[k] for k in sorted(out)]
