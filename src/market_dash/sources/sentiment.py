"""CNN 공포·탐욕 지수 (비공식 JSON 엔드포인트 → 실패를 전제로 사용)."""

from __future__ import annotations

from datetime import datetime, timezone

import requests

from market_dash import config


def parse_fear_greed(j: dict, keep_days: int = 95) -> dict:
    """CNN 응답 → 현재 점수·비교값·일별 기록 [(날짜, 점수)]. 순수 함수.

    기록은 같은 날짜가 여러 번 나오면(장중 갱신) 마지막 값을 쓴다.
    """
    cur = j["fear_and_greed"]
    by_date: dict[str, float] = {}
    for p in j.get("fear_and_greed_historical", {}).get("data", []):
        d = datetime.fromtimestamp(p["x"] / 1000, tz=timezone.utc).date().isoformat()
        by_date[d] = float(p["y"])
    history = sorted(by_date.items())[-keep_days:]
    score = float(cur["score"])
    if not 0 <= score <= 100:
        raise ValueError(f"공포·탐욕 점수 범위 밖: {score}")
    return {
        "score": score,
        "as_of": cur.get("timestamp"),
        "prev_close": cur.get("previous_close"),
        "week_ago": cur.get("previous_1_week"),
        "month_ago": cur.get("previous_1_month"),
        "year_ago": cur.get("previous_1_year"),
        "history": history,
    }


def fetch_fear_greed() -> dict:
    r = requests.get(config.FEAR_GREED_URL, headers=config.HTTP_HEADERS, timeout=config.HTTP_TIMEOUT)
    r.raise_for_status()
    return parse_fear_greed(r.json())
