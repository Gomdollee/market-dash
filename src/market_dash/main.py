"""진입점: 수집 → 계산 → 병합 → 저장.

실행: uv run python -m market_dash.main
(≈ Spring Batch Job 하나. 각 섹션이 독립 Step 이고, 한 Step 실패가 다른 Step 을 막지 않는다.)
"""

from __future__ import annotations

import logging
import sys
from datetime import date, datetime, timedelta, timezone
from typing import Callable

from market_dash import config
from market_dash.calc import (
    Series,
    drawdown_series,
    find_peak,
    gold_krw,
    krw_change_pct,
    pct_change,
    rank_movers,
    threshold_gauge,
    value_on_or_before,
)
from market_dash.episode_notes import news_search_url, note_for
from market_dash.explain import (
    drawdown_zone,
    fear_greed_zone,
    five_year_summary,
    fx_summary,
    index_summary,
    krw_summary,
    mood_summary,
    vix_zone,
)
from market_dash.swings import drawdown_episodes, find_swings, weekly
from market_dash.keywords import top_keywords
from market_dash.alerts import detect_alerts, status_lines
from market_dash.market_calendar import ET, KST, is_market_open, rule_events, upcoming_sessions
from market_dash.sources import events as events_src
from market_dash.names_ko import KEYWORD_KO, TICKER_KO
from market_dash.sources import fx as fx_src
from market_dash.sources import market, news, sentiment, telegram
from market_dash.sources.translate import Translator, prune_cache
from market_dash.storage import FetchResult, load_json, merge_section, save_json, upsert_rows

log = logging.getLogger("market_dash")


def r2(x: float | None) -> float | None:
    return None if x is None else round(x, 2)


def attempt(name: str, fn: Callable[[], object]) -> FetchResult:
    """fn 실행. 예외는 FetchResult(ok=False) 로 바꿔 다음 섹션 진행을 보장."""
    try:
        return FetchResult(ok=True, data=fn())
    except Exception as e:  # noqa: BLE001
        log.exception("[%s] 실패", name)
        return FetchResult(ok=False, error=f"{type(e).__name__}: {e}"[:300])


# ── 섹션별 빌더 ─────────────────────────────────────────


def build_fx() -> dict:
    series, source = fx_src.fetch_usdkrw_history()
    (d_prev, prev), (d_now, now) = series[-2], series[-1]
    return {
        "as_of": d_now,
        "rate": r2(now),
        "prev_rate": r2(prev),
        "prev_date": d_prev,
        "change_pct": r2(pct_change(now, prev)),
        "summary": fx_summary(now, prev),
        "source": source,
        "_series": series,  # 지수 원화 환산·history 용. 저장 전에 제거
    }


def annotate_episode(asset: str, e: dict) -> dict:
    """하락 구간에 사건 메모와 당시 뉴스 검색 링크를 붙인다."""
    bottom_next = (date.fromisoformat(e["bottom"]["date"]) + timedelta(days=1)).isoformat()
    return {
        **e,
        "note": note_for(asset, e["peak"]["date"]),
        "news_url": news_search_url(config.INDICES[asset]["news_query"], e["peak"]["date"], bottom_next),
    }


def build_index(key: str, fx_series: Series | None) -> dict:
    meta = config.INDICES[key]
    closes = market.fetch_close_history(meta["symbol"])
    rows = drawdown_series(closes)
    last, prev = rows[-1], rows[-2]
    peak = find_peak(closes)
    gauge = threshold_gauge(last["drawdown_pct"], config.DRAWDOWN_LINES)
    idx_pct = pct_change(last["close"], prev["close"])

    # 원화 기준: 지수의 두 거래일과 같은(또는 직전) 날짜의 환율로 맞춰 계산
    krw = None
    if fx_series:
        fx_now = value_on_or_before(fx_series, last["date"])
        fx_prev = value_on_or_before(fx_series, prev["date"])
        if fx_now and fx_prev:
            fx_pct = pct_change(fx_now, fx_prev)
            krw = {
                "change_pct": r2(krw_change_pct(idx_pct, fx_pct)),
                "fx_change_pct": r2(fx_pct),
                "fx_now": r2(fx_now),
                "fx_prev": r2(fx_prev),
                "summary": krw_summary(meta["subject"], krw_change_pct(idx_pct, fx_pct), idx_pct, fx_pct),
            }

    # 금: 1돈(3.75g)·1g 원화 가격 (국제 시세 × 환율, 세금·프리미엄 제외)
    gold_krw_price = None
    if meta["kind"] == "commodity" and krw:
        gold_krw_price = {
            "per_don": round(gold_krw(last["close"], krw["fx_now"], config.DON_G)),
            "per_gram": round(gold_krw(last["close"], krw["fx_now"], 1.0)),
        }

    # 지난 5년 큰 오르내림 + 그보다 옛날의 큰 폭락
    since = (date.fromisoformat(last["date"]) - timedelta(days=round(365.25 * 5))).isoformat()
    episodes = [annotate_episode(key, e) for e in drawdown_episodes(closes, config.BIG_MOVE_PCT, since)]
    long_ago = [
        annotate_episode(key, e)
        for e in drawdown_episodes(closes, meta["long_min_pct"], meta["long_since"])
        if (e["recovered"] or {}).get("date", "9999") < since  # 5년 목록과 겹치지 않게
    ]
    five_year = {
        "since": since,
        "weekly": [[d, r2(v)] for d, v in weekly([p for p in closes if p[0] >= since])],
        "drawdowns": episodes,
        "swings": find_swings(closes, config.BIG_MOVE_PCT, since),
        "summary": five_year_summary(meta["subject"], episodes),
        "long_ago": long_ago,
        "long_min_pct": meta["long_min_pct"],
        "data_since": closes[0][0],
    }

    return {
        "name": meta["name"],
        "short": meta["short"],
        "kind": meta["kind"],
        "gold_krw": gold_krw_price,
        "five_year": five_year,
        "zone": drawdown_zone(last["drawdown_pct"]),
        "summary": index_summary(meta["subject"], idx_pct, last["drawdown_pct"],
                                 gauge.next_line, gauge.remaining_pp),
        "symbol": meta["symbol"],
        "as_of": last["date"],
        "prev_date": prev["date"],
        "close": r2(last["close"]),
        "prev_close": r2(prev["close"]),
        "change_pct": r2(idx_pct),
        "peak": {"value": r2(peak.value), "date": peak.date},
        "drawdown_pct": r2(last["drawdown_pct"]),
        "gauge": {
            "prev_line": gauge.prev_line,
            "next_line": gauge.next_line,
            "remaining_pp": r2(gauge.remaining_pp),
            "progress": round(gauge.progress, 4),
        },
        "krw": krw,
        "_history": [
            {
                "date": r["date"],
                "close": r2(r["close"]),
                "peak": r2(r["peak"]),
                "drawdown_pct": r2(r["drawdown_pct"]),
            }
            for r in rows[-config.HISTORY_KEEP_DAYS :]
        ],
    }


def build_fear_greed() -> dict:
    fg = sentiment.fetch_fear_greed()
    return {
        **{k: (r2(v) if isinstance(v, float) else v) for k, v in fg.items() if k != "history"},
        "zone": fear_greed_zone(fg["score"]),
        "summary": mood_summary(fg["score"], None),
        "history": [[d, r2(v)] for d, v in fg["history"]],
    }


def build_vix() -> dict:
    closes = market.fetch_close_history(config.VIX_SYMBOL, period="6mo")
    (d_prev, prev), (d_now, now) = closes[-2], closes[-1]
    return {
        "as_of": d_now,
        "close": r2(now),
        "prev_close": r2(prev),
        "change": r2(now - prev),
        "change_pct": r2(pct_change(now, prev)),
        "zone": vix_zone(now),
        "summary": mood_summary(None, now),
        "history": [[d, r2(v)] for d, v in closes[-config.MOOD_KEEP_DAYS:] if d >= _days_before(d_now, 92)],
    }


def _days_before(iso: str, days: int) -> str:
    return (date.fromisoformat(iso) - timedelta(days=days)).isoformat()


def _slim_quote(q: dict) -> dict:
    return {
        "symbol": q["symbol"],
        "name_ko": TICKER_KO.get(q["symbol"]),
        "date": q["date"],
        "close": r2(q["close"]),
        "change_pct": r2(q["change_pct"]),
        "volume": q["volume"],
    }


def build_movers() -> dict:
    quotes = market.fetch_quotes(config.NASDAQ100)
    ranked = rank_movers(quotes, config.MOVERS_TOP_N)

    uniq = {q["symbol"]: q for group in ranked.values() for q in group}
    news_by_symbol = {s: news.fetch_ticker_news(s, config.NEWS_PER_TICKER) for s in sorted(uniq)}
    reason_by_symbol = {
        s: news.fetch_move_reason(s, TICKER_KO.get(s), q["change_pct"], q["date"]) for s, q in sorted(uniq.items())
    }

    return {
        "universe": "나스닥-100",
        "universe_count": len(quotes),
        "as_of": max(q["date"] for q in quotes),
        **{
            k: [{**_slim_quote(q), "reason": reason_by_symbol.get(q["symbol"]),
                 "news": news_by_symbol.get(q["symbol"], [])} for q in group]
            for k, group in ranked.items()
        },
    }


def build_sectors() -> dict:
    quotes = market.fetch_quotes(list(config.SECTOR_ETFS))
    items = sorted(
        ({**_slim_quote(q), "name": config.SECTOR_ETFS[q["symbol"]]} for q in quotes),
        key=lambda q: q["change_pct"],
        reverse=True,
    )
    return {"as_of": max(q["date"] for q in items), "items": items}


def build_news() -> dict:
    items = news.fetch_market_news()
    en_titles = [it["title"] for it in items if it["lang"] == "en"]
    return {
        "items": news.pick_diverse(items, config.MARKET_NEWS_COUNT, config.NEWS_PER_SOURCE_MAX),
        "keywords": [
            {**k, "ko": KEYWORD_KO.get(k["word"])} for k in top_keywords(en_titles, config.KEYWORD_TOP_N)
        ],
        "keyword_base_count": len(en_titles),
    }


def _month_range(today: date, months_ahead: int) -> tuple[date, date]:
    start = today.replace(day=1)
    y, m = divmod(today.month - 1 + months_ahead + 1, 12)
    end = date(today.year + y, m + 1, 1) - timedelta(days=1)
    return start, end


def build_calendar(prev: dict | None) -> dict:
    """규칙 일정은 항상 계산. FOMC·실적은 실패 시 이전 값 재사용 + 경고."""
    prev = prev or {}
    prev_events = prev.get("events", [])
    today_et = datetime.now(ET).date()
    start, end = _month_range(today_et, config.CALENDAR_MONTHS_AHEAD)
    in_range = lambda e: start.isoformat() <= e["date"] <= end.isoformat()  # noqa: E731

    def iso(events: list[dict]) -> list[dict]:
        return [{**e, "date": e["date"].isoformat()} for e in events]

    events = iso(rule_events(start, end))
    warnings: list[str] = []

    try:
        meetings = events_src.fetch_fomc()
        events += [e for e in iso([events_src.fomc_event(m) for m in meetings]) if in_range(e)]
    except Exception as e:  # noqa: BLE001
        log.warning("FOMC 실패: %s", e)
        warnings.append("FOMC 일정 갱신 실패 → 이전 데이터 표시")
        events += [ev for ev in prev_events if ev["type"] == "fomc" and in_range(ev)]

    earnings, failed = events_src.fetch_earnings(config.EARNINGS_WATCH)
    events += [e for e in iso(earnings) if in_range(e)]
    if failed:
        warnings.append(f"실적일 조회 실패: {', '.join(failed)}")
        events += [ev for ev in prev_events
                   if ev["type"] == "earnings" and ev.get("symbol") in failed and in_range(ev)]

    events.sort(key=lambda e: (e["date"], e["type"]))
    return {"today_et": today_et.isoformat(), "start": start.isoformat(), "end": end.isoformat(),
            "events": events, "warnings": warnings,
            # 어제부터 15거래일: 페이지를 늦게 열어도 '지금 장 상태'를 판단할 수 있게
            "sessions": upcoming_sessions(today_et - timedelta(days=1), 15)}


def translate_titles(results: dict[str, FetchResult]) -> dict:
    """이번에 새로 받은 영문 제목에 title_ko 를 붙인다. 실패해도 원문은 그대로 남는다."""
    targets: list[dict] = []
    if results["news"].ok:
        targets += [it for it in results["news"].data["items"] if it.get("lang") == "en"]
    if results["movers"].ok:
        for key in ("gainers", "losers", "most_active"):
            for q in results["movers"].data[key]:
                targets += [n for n in q["news"] if n.get("lang") == "en"]
                if q.get("reason") and q["reason"].get("lang") == "en":
                    targets.append(q["reason"])
    if not targets:
        return {"engine": None, "translated": 0, "total": 0}

    cache = load_json(config.TRANSLATION_CACHE_PATH, {})
    tr = Translator(cache)
    mapping = tr.translate_many([t["title"] for t in targets])
    for t in targets:
        if t["title"] in mapping:
            t["title_ko"] = mapping[t["title"]]
    save_json(config.TRANSLATION_CACHE_PATH, prune_cache(tr.cache, config.TRANSLATION_CACHE_KEEP))

    done = sum(1 for t in targets if "title_ko" in t)
    log.info("번역 %d/%d (엔진: %s)", done, len(targets), tr.engine_used or "캐시")
    return {"engine": tr.engine_used, "translated": done, "total": len(targets)}


def mark_live(results: dict[str, FetchResult], now: datetime) -> None:
    """장중 수집이면 해당 섹션에 live=True 를 붙인다 (화면에 '장중 · HH:MM' 표시용)."""
    today_et = now.astimezone(ET).date().isoformat()
    open_now = is_market_open(now)
    for key in (*config.INDICES, "vix", "movers", "sectors"):
        res = results.get(key)
        if res and res.ok:
            res.data["live"] = open_now and res.data.get("as_of") == today_et
            res.data["fetched_at"] = now.isoformat(timespec="seconds")


def alert_snapshot(results: dict[str, FetchResult], now: datetime) -> dict:
    """이번에 새로 받은(ok) 데이터만으로 알림 판정용 스냅샷을 만든다. 실패·이전 데이터로는 알리지 않음."""
    def when(d: dict) -> str:
        return f"장중 {now.astimezone(KST):%H:%M}" if d.get("live") else f"{d['as_of'][5:].replace('-', '.')} 마감"

    assets = {
        k: {"name": config.INDICES[k]["short"], "as_of": d["as_of"], "close": d["close"],
            "change_pct": d["change_pct"], "drawdown_pct": d["drawdown_pct"], "when": when(d)}
        for k in config.INDICES if results[k].ok for d in [results[k].data]
    }
    vix = results.get("vix")
    return {"assets": assets,
            "vix": {"close": vix.data["close"], "when": when(vix.data)} if vix and vix.ok else None}


def notify(results: dict[str, FetchResult], now: datetime) -> str:
    """급락 알림 전송. 토큰이 없으면 아무것도 안 함. 전송 실패 시 상태를 저장하지 않아 다음 실행에 다시 시도."""
    creds = telegram.credentials()
    if not creds:
        return "텔레그램 설정 없음 → 건너뜀"
    snap = alert_snapshot(results, now)
    state = load_json(config.ALERT_STATE_PATH, None)
    msgs, new_state = detect_alerts(snap, state or {})
    if state is None:
        # 첫 연결: 지금 상태를 기준으로 삼고(이미 빠져 있는 하락은 알리지 않음) 연결 확인 메시지만
        text = "\n".join([
            "✅ 환율난민수용소 급락 알림이 연결됐어요.", "", "지금 상태", *status_lines(snap), "",
            "앞으로 크게 떨어지면 알려드릴게요.", config.PAGE_URL,
        ])
        telegram.send(text, creds)
        result = "연결 확인 메시지 전송"
    elif msgs:
        telegram.send("\n\n".join([*msgs, config.PAGE_URL]), creds)
        result = f"알림 {len(msgs)}건 전송"
    else:
        result = "알릴 것 없음"
    if new_state != state:
        save_json(config.ALERT_STATE_PATH, new_state)
    return result


# ── 조립 ───────────────────────────────────────────────


def run() -> int:
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    prev_latest = load_json(config.LATEST_PATH, {})
    prev_sections = prev_latest.get("sections", {})
    history = load_json(config.HISTORY_PATH, {})

    results: dict[str, FetchResult] = {}

    results["fx"] = attempt("fx", build_fx)
    fx_series = results["fx"].data.pop("_series") if results["fx"].ok else None
    if fx_series:
        rows = [{"date": d, "close": r2(v)} for d, v in fx_series]
        history["usdkrw"] = upsert_rows(history.get("usdkrw", []), rows, config.HISTORY_KEEP_DAYS)

    for key in config.INDICES:
        results[key] = attempt(key, lambda k=key: build_index(k, fx_series))
        if results[key].ok:
            rows = results[key].data.pop("_history")
            history[key] = upsert_rows(history.get(key, []), rows, config.HISTORY_KEEP_DAYS)

    results["fear_greed"] = attempt("fear_greed", build_fear_greed)
    results["vix"] = attempt("vix", build_vix)
    results["movers"] = attempt("movers", build_movers)
    results["sectors"] = attempt("sectors", build_sectors)
    results["news"] = attempt("news", build_news)
    results["calendar"] = attempt(
        "calendar", lambda: build_calendar((prev_sections.get("calendar") or {}).get("data"))
    )

    now = datetime.now(timezone.utc)
    mark_live(results, now)
    alert = attempt("alert", lambda: notify(results, now))
    log.info("알림: %s", alert.data if alert.ok else "실패")

    tr_info = attempt("translate", lambda: translate_titles(results))
    if not tr_info.ok:
        log.warning("번역 단계 실패 → 원문만 표시")

    sections = {k: merge_section(prev_sections.get(k), res, now_iso) for k, res in results.items()}
    save_json(config.LATEST_PATH, {"generated_at": now_iso, "sections": sections})
    save_json(config.HISTORY_PATH, history)

    summary = ", ".join(f"{k}={v['status']}" for k, v in sections.items())
    log.info("완료: %s", summary)
    # 전부 실패했을 때만 비정상 종료 → Actions 에서 빨간불로 알 수 있게
    return 0 if any(r.ok for r in results.values()) else 1


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    sys.exit(run())


if __name__ == "__main__":
    main()
