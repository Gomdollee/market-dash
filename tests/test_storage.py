from market_dash.storage import FetchResult, load_json, merge_section, save_json, upsert_rows

NOW = "2026-11-08T22:30:00+00:00"
EARLIER = "2026-11-08T03:30:00+00:00"


def test_merge_success_replaces_everything():
    prev = {"status": "ok", "last_success_at": EARLIER, "data": {"v": 1}}
    s = merge_section(prev, FetchResult(ok=True, data={"v": 2}), NOW)
    assert s["status"] == "ok"
    assert s["data"] == {"v": 2}
    assert s["last_success_at"] == NOW
    assert s["error"] is None


def test_merge_failure_keeps_previous_data_and_time():
    prev = {"status": "ok", "last_success_at": EARLIER, "data": {"v": 1}}
    s = merge_section(prev, FetchResult(ok=False, error="timeout"), NOW)
    assert s["status"] == "stale"
    assert s["data"] == {"v": 1}
    assert s["last_success_at"] == EARLIER
    assert s["attempted_at"] == NOW
    assert s["error"] == "timeout"


def test_merge_repeated_failure_keeps_original_success_time():
    first_fail = merge_section(
        {"status": "ok", "last_success_at": EARLIER, "data": {"v": 1}},
        FetchResult(ok=False, error="x"),
        "2026-11-09T00:30:00+00:00",
    )
    second_fail = merge_section(first_fail, FetchResult(ok=False, error="y"), NOW)
    assert second_fail["last_success_at"] == EARLIER
    assert second_fail["data"] == {"v": 1}


def test_merge_failure_without_previous_is_error():
    s = merge_section(None, FetchResult(ok=False, error="boom"), NOW)
    assert s["status"] == "error"
    assert s["data"] is None
    assert s["last_success_at"] is None


def test_upsert_rows_overwrites_same_date_sorts_and_trims():
    existing = [{"date": "2026-11-03", "v": 1}, {"date": "2026-11-04", "v": 2}]
    new = [{"date": "2026-11-05", "v": 3}, {"date": "2026-11-04", "v": 20}]
    merged = upsert_rows(existing, new, keep=2)
    assert merged == [{"date": "2026-11-04", "v": 20}, {"date": "2026-11-05", "v": 3}]


def test_save_and_load_roundtrip(tmp_path):  # tmp_path: pytest 내장 fixture (≈ JUnit @TempDir)
    p = tmp_path / "sub" / "x.json"
    save_json(p, {"한글": 1.5})
    assert load_json(p, None) == {"한글": 1.5}


def test_load_missing_or_broken_returns_default(tmp_path):
    assert load_json(tmp_path / "none.json", {"d": 1}) == {"d": 1}
    broken = tmp_path / "b.json"
    broken.write_text("{not json", encoding="utf-8")
    assert load_json(broken, []) == []
