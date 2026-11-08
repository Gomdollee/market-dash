"""RSS 뉴스 수집."""

from __future__ import annotations

import calendar
import logging
import re
from datetime import datetime, timezone

import feedparser
import requests

from market_dash import config

log = logging.getLogger(__name__)


def _published_iso(entry) -> str | None:
    t = entry.get("published_parsed") or entry.get("updated_parsed")
    if not t:
        return None
    # feedparser 의 struct_time 은 UTC 기준
    return datetime.fromtimestamp(calendar.timegm(t), tz=timezone.utc).isoformat()


def _split_google_title(title: str, source: str | None) -> str:
    """구글 뉴스 제목 끝의 ' - 언론사' 제거."""
    if source and title.endswith(f" - {source}"):
        return title[: -len(source) - 3]
    return title


def fetch_feed(url: str, name: str, lang: str, limit: int | None = None) -> list[dict]:
    r = requests.get(url, headers=config.HTTP_HEADERS, timeout=config.HTTP_TIMEOUT)
    r.raise_for_status()
    feed = feedparser.parse(r.content)
    items = []
    for e in feed.entries[:limit]:
        src = (e.get("source") or {}).get("title")
        title = _split_google_title(e.get("title", "").strip(), src)
        link = e.get("link")
        if not title or not link:
            continue
        items.append(
            {
                "title": title,
                "link": link,
                "source": src or name,
                "published": _published_iso(e),
                "lang": lang,
            }
        )
    return items


def _norm(title: str) -> str:
    return re.sub(r"\W+", "", title.lower())


def dedupe_and_sort(items: list[dict]) -> list[dict]:
    """제목 기준 중복 제거 후 최신순 (발행 시각 없는 기사는 뒤로)."""
    seen: set[str] = set()
    unique = []
    for it in items:
        key = _norm(it["title"])
        if key and key not in seen:
            seen.add(key)
            unique.append(it)
    return sorted(unique, key=lambda it: it["published"] or "", reverse=True)


def pick_diverse(items: list[dict], n: int, per_source_max: int) -> list[dict]:
    """최신순 목록에서 n개 고르되 한 출처가 per_source_max 개를 넘지 않게.

    출처가 부족해 n개를 못 채우면 남은 기사로 최신순 보충.
    """
    picked: list[dict] = []
    counts: dict[str, int] = {}
    for it in items:
        if len(picked) == n:
            break
        if counts.get(it["source"], 0) < per_source_max:
            picked.append(it)
            counts[it["source"]] = counts.get(it["source"], 0) + 1
    if len(picked) < n:
        picked += [it for it in items if it not in picked][: n - len(picked)]
    return sorted(picked, key=lambda it: it["published"] or "", reverse=True)


def fetch_market_news() -> list[dict]:
    """모든 시장 피드를 합친 전체 목록 (화면용 10개 자르기·키워드 집계는 호출자가)."""
    items: list[dict] = []
    for f in config.MARKET_FEEDS:
        try:
            items += fetch_feed(f["url"], f["name"], f["lang"])
        except Exception as e:  # noqa: BLE001 - 피드 하나 실패는 무시
            log.warning("뉴스 피드 실패 %s: %s", f["name"], e)
    if not items:
        raise RuntimeError("모든 뉴스 피드 실패")
    return dedupe_and_sort(items)


# ── '왜 움직였나' 기사 고르기 ───────────────────────────
_UP_WORDS = ("급등", "폭등", "상승", "강세", "랠리", "soar", "jump", "surge", "rall", "climb", "gain", "pop", "rise")
_DOWN_WORDS = ("급락", "폭락", "하락", "약세", "↓", "plunge", "sink", "tumble", "fall", "drop", "slide", "crater", "slump")
_REASON_WORDS = ("특징주", "이유", "왜", "why", "after", "on ")


def score_reason(title: str, change_pct: float) -> int:
    """제목이 '이 종목이 왜 이만큼 움직였는지' 말해주는 정도. 순수 함수.

    - 실제 변동률 숫자(예: 15%)가 들어 있으면 강한 신호
    - 방향 단어가 실제 방향과 맞으면 +, 반대면 크게 -
    - '특징주', '이유', 'why' 같은 단어 +
    """
    t = title.lower()
    s = 0
    # 제목 속 % 숫자: 실제 변동률과 비슷하면 +3, 전부 동떨어지면 다른 날·다른 얘기일 가능성 → -4
    # 허용 오차는 변동폭의 25%(최소 1.5%p) - 기사가 장중/시간외 수치를 쓰는 경우가 많아서
    nums = [float(x) for x in re.findall(r"(\d+(?:\.\d+)?)\s*%", t)]
    tol = max(1.5, abs(change_pct) * 0.25)
    if nums:
        if any(abs(n - abs(change_pct)) <= tol for n in nums):
            s += 3
        else:
            s -= 4
    up = any(w in t for w in _UP_WORDS)
    down = any(w in t for w in _DOWN_WORDS)
    if change_pct > 0:
        s += 2 if up else 0
        s -= 4 if down and not up else 0
    else:
        s += 2 if down else 0
        s -= 4 if up and not down else 0
    s += sum(1 for w in _REASON_WORDS if w in t)
    if "특징주" in t:
        s += 2
    # 'OO 주가 4.77% 하락 마감' 같은 자동 생성 시세 기사: 얼마나 움직였는지만 있고 이유가 없음
    elif "마감" in t or "기업주식정보" in t:
        s -= 3
    return s


def pick_reason(items: list[dict], change_pct: float, must_contain: tuple[str, ...],
                not_before: str, min_score: int = 3) -> dict | None:
    """후보 중 점수 최고 1개. must_contain 중 하나가 제목에 있어야 하고, not_before 이후 발행이어야 함."""
    best, best_score = None, min_score - 1
    for it in items:
        title_cmp = it["title"].replace(" ", "").lower()
        if not any(m.replace(" ", "").lower() in title_cmp for m in must_contain if m):
            continue
        if not it.get("published") or it["published"] < not_before:
            continue
        sc = score_reason(it["title"], change_pct)
        if sc > best_score:
            best, best_score = it, sc
    return best


def fetch_move_reason(symbol: str, name_ko: str | None, change_pct: float, trade_date: str) -> dict | None:
    """그 종목이 왜 움직였는지 제목에 드러난 기사 1개. 한국어 '특징주' 우선, 없으면 영어.

    trade_date: 미국 거래일 (YYYY-MM-DD). 그날 이후 발행된 기사만 본다.
    """
    from urllib.parse import quote

    not_before = f"{trade_date}T00:00:00+00:00"
    tries = []
    if name_ko:
        q = f"{name_ko} (특징주 OR 급등 OR 급락 OR 폭등 OR 폭락 OR 이유) when:3d"
        tries.append((f"https://news.google.com/rss/search?q={quote(q)}&hl=ko&gl=KR&ceid=KR:ko",
                      "ko", (name_ko, symbol)))
    q = f"{symbol} stock (soars OR jumps OR surges OR plunges OR sinks OR tumbles OR falls OR why) when:2d"
    tries.append((f"https://news.google.com/rss/search?q={quote(q)}&hl=en-US&gl=US&ceid=US:en",
                  "en", (symbol,)))

    for url, lang, must in tries:
        try:
            items = fetch_feed(url, "Google News", lang, limit=30)
        except Exception as e:  # noqa: BLE001
            log.warning("이유 기사 검색 실패 %s (%s): %s", symbol, lang, e)
            continue
        best = pick_reason(items, change_pct, must, not_before)
        if best:
            return {k: best[k] for k in ("title", "link", "source", "published", "lang")}
    return None


def fetch_ticker_news(symbol: str, n: int) -> list[dict]:
    """종목 관련 헤드라인 n개. 야후 → 실패/빈 결과면 구글 뉴스."""
    for url, name in (
        (config.TICKER_FEED_URL, "Yahoo Finance"),
        (config.TICKER_FEED_FALLBACK_URL, "Google News"),
    ):
        try:
            items = fetch_feed(url.format(symbol=symbol), name, "en", limit=10)
            items = dedupe_and_sort(items)[:n]
            if items:
                return [{k: it[k] for k in ("title", "link", "source", "published", "lang")} for it in items]
        except Exception as e:  # noqa: BLE001
            log.warning("종목 뉴스 실패 %s (%s): %s", symbol, name, e)
    return []
