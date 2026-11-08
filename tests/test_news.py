from market_dash.sources.news import (
    _split_google_title,
    dedupe_and_sort,
    pick_diverse,
    pick_reason,
    score_reason,
)


def test_score_reason_prefers_feature_article_with_matching_percent():
    good = "[美증시 특징주] 로켓랩, 발사 규제완화에 15% 폭등"
    vague = "로켓 랩(RKLB) 주가, 우주 시스템 사업 전환으로 공정가치 이상에서 거래될 전망"
    assert score_reason(good, 15.39) > score_reason(vague, 15.39)


def test_score_reason_penalizes_wrong_direction():
    assert score_reason("액손, 실적 부진에 주가 16%↓", -18.18) > 0
    assert score_reason("액손 주가 16% 급등", -18.18) < score_reason("액손, 실적 부진에 주가 16%↓", -18.18)


def test_score_reason_penalizes_unrelated_percent():
    # 실제 +9.86% 인데 제목은 31% → 다른 날 기사
    assert score_reason("APP Stock Jumps 31% After Earnings Beat", 9.86) < 3
    assert score_reason("코어위브, 2032년 만기 채권 수익률 16% 넘어", 6.28) < 3
    assert score_reason("에어비앤비, 호실적에 주가 12%↑", 11.67) >= 3


def test_score_reason_penalizes_auto_generated_price_articles():
    robot = "부킹홀딩스 주가 4.77% 하락 마감 160달러선 기록 : 기업주식정보"
    assert score_reason(robot, -4.77) < 3


def test_pick_reason_filters_name_and_date():
    items = [
        {"title": "[美특징주] 로켓랩, 규제완화에 15% 폭등", "published": "2026-11-07T00:00:00+00:00"},
        {"title": "[美특징주] 로켓랩, 계약 따내 20% 폭등", "published": "2026-10-01T00:00:00+00:00"},  # 오래됨
        {"title": "[美특징주] 테슬라 15% 폭등", "published": "2026-11-07T00:00:00+00:00"},  # 다른 종목
    ]
    best = pick_reason(items, 15.4, ("로켓랩", "RKLB"), "2026-11-06T00:00:00+00:00")
    assert best is items[0]


def test_pick_reason_none_when_nothing_relevant():
    items = [{"title": "로켓 랩 주가 전망", "published": "2026-11-07T00:00:00+00:00"}]
    assert pick_reason(items, 15.4, ("로켓랩",), "2026-11-06T00:00:00+00:00") is None


def _item(title, source, published):
    return {"title": title, "source": source, "published": published, "link": "http://x", "lang": "en"}


def test_dedupe_ignores_case_and_punctuation_and_sorts_newest_first():
    items = [
        _item("Fed holds rates", "A", "2026-11-07T01:00:00+00:00"),
        _item("Fed holds rates!", "B", "2026-11-07T02:00:00+00:00"),
        _item("Oil up", "C", "2026-11-07T03:00:00+00:00"),
        _item("No date", "D", None),
    ]
    out = dedupe_and_sort(items)
    assert [i["title"] for i in out] == ["Oil up", "Fed holds rates", "No date"]


def test_pick_diverse_caps_each_source():
    items = [_item(f"y{i}", "Yahoo", f"2026-11-07T1{i}:00:00+00:00") for i in range(6)][::-1]
    items += [_item("c1", "CNBC", "2026-11-07T00:00:00+00:00")]
    out = pick_diverse(items, 3, per_source_max=2)
    assert [i["source"] for i in out].count("Yahoo") == 2
    assert any(i["source"] == "CNBC" for i in out)


def test_pick_diverse_backfills_when_sources_run_out():
    items = [_item(f"y{i}", "Yahoo", f"2026-11-07T1{i}:00:00+00:00") for i in range(5)]
    assert len(pick_diverse(items, 4, per_source_max=2)) == 4


def test_split_google_title():
    assert _split_google_title("Big news - Reuters", "Reuters") == "Big news"
    assert _split_google_title("Big - news", None) == "Big - news"
