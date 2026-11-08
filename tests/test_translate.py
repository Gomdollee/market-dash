from market_dash.sources.translate import Translator, prune_cache


class FakeTranslator(Translator):
    """네트워크 대신 가짜 엔진. (≈ Mockito 로 외부 클라이언트를 대체하는 것과 같은 목적)"""

    def __init__(self, cache, fail_on=()):
        super().__init__(cache, deepl_key="")
        self.calls: list[str] = []
        self.fail_on = set(fail_on)

    def _google_one(self, text):
        self.calls.append(text)
        if text in self.fail_on:
            raise RuntimeError("fail")
        return f"KO:{text}"


def test_uses_cache_and_only_calls_engine_for_new_texts(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    cache = {"old": {"ko": "옛날", "t": "2026-01-01"}}
    tr = FakeTranslator(cache)
    out = tr.translate_many(["old", "new", "new"])
    assert out == {"old": "옛날", "new": "KO:new"}
    assert tr.calls == ["new"]
    assert cache["new"]["ko"] == "KO:new"


def test_failed_texts_are_omitted_not_cached(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    cache = {}
    tr = FakeTranslator(cache, fail_on={"bad"})
    out = tr.translate_many(["ok", "bad"])
    assert out == {"ok": "KO:ok"}
    assert "bad" not in cache


def test_circuit_breaker_stops_after_consecutive_failures(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    texts = [f"t{i}" for i in range(10)]
    tr = FakeTranslator({}, fail_on=set(texts))
    assert tr.translate_many(texts) == {}
    assert len(tr.calls) == 3  # 3번 연속 실패 후 중단


def test_prune_cache_keeps_most_recent():
    cache = {"a": {"ko": "", "t": "2026-01-01"}, "b": {"ko": "", "t": "2026-03-01"}, "c": {"ko": "", "t": "2026-02-01"}}
    assert set(prune_cache(cache, 2)) == {"b", "c"}
