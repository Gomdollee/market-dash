"""영→한 제목 기계번역 (LLM 아님).

우선순위: DeepL API Free (환경변수 DEEPL_API_KEY 있을 때) → 구글 번역 비공식 엔드포인트.
둘 다 실패하면 번역 없이 원문만 표시된다.

- 캐시: 한 번 번역한 문장은 cache/translations.json 에 저장해 재사용 (≈ Spring @Cacheable)
- 연속 실패 시 그 실행에서는 더 시도하지 않음 (≈ Resilience4j CircuitBreaker 의 아주 단순한 버전)
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone

import requests

from market_dash import config

log = logging.getLogger(__name__)

GOOGLE_URL = "https://translate.googleapis.com/translate_a/single"
DEEPL_FREE_URL = "https://api-free.deepl.com/v2/translate"
DEEPL_PRO_URL = "https://api.deepl.com/v2/translate"
MAX_CONSECUTIVE_FAILURES = 3


def prune_cache(cache: dict[str, dict], keep: int) -> dict[str, dict]:
    """최근 사용(t) 기준 keep 개만 남김."""
    if len(cache) <= keep:
        return cache
    newest = sorted(cache.items(), key=lambda kv: kv[1].get("t", ""), reverse=True)[:keep]
    return dict(newest)


class Translator:
    def __init__(self, cache: dict[str, dict], deepl_key: str | None = None):
        self.cache = cache
        self.deepl_key = deepl_key if deepl_key is not None else os.environ.get("DEEPL_API_KEY")
        self.session = requests.Session()
        self.session.headers.update(config.HTTP_HEADERS)
        self.failures = 0
        self.engine_used: str | None = None

    # ── 엔진 ──────────────────────────────────────────
    def _deepl(self, texts: list[str]) -> list[str]:
        url = DEEPL_FREE_URL if self.deepl_key.endswith(":fx") else DEEPL_PRO_URL
        r = self.session.post(
            url,
            headers={"Authorization": f"DeepL-Auth-Key {self.deepl_key}"},
            json={"text": texts, "source_lang": "EN", "target_lang": "KO"},
            timeout=config.HTTP_TIMEOUT,
        )
        r.raise_for_status()
        return [t["text"] for t in r.json()["translations"]]

    def _google_one(self, text: str) -> str:
        r = self.session.get(
            GOOGLE_URL,
            params={"client": "gtx", "sl": "en", "tl": "ko", "dt": "t", "q": text},
            timeout=config.HTTP_TIMEOUT,
        )
        r.raise_for_status()
        out = "".join(seg[0] for seg in r.json()[0] if seg and seg[0])
        if not out:
            raise RuntimeError("빈 번역 결과")
        return out

    # ── 공개 API ──────────────────────────────────────
    def translate_many(self, texts: list[str]) -> dict[str, str]:
        """{원문: 번역}. 실패한 문장은 결과에서 빠진다."""
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        result: dict[str, str] = {}
        todo: list[str] = []
        for t in dict.fromkeys(texts):  # 순서 유지 중복 제거
            if t in self.cache:
                self.cache[t]["t"] = now
                result[t] = self.cache[t]["ko"]
            else:
                todo.append(t)
        if not todo:
            return result

        translated: dict[str, str] = {}
        if self.deepl_key:
            try:
                for i in range(0, len(todo), 50):  # DeepL 요청당 최대 50문장
                    chunk = todo[i : i + 50]
                    translated.update(zip(chunk, self._deepl(chunk)))
                self.engine_used = "DeepL"
            except Exception as e:  # noqa: BLE001
                log.warning("DeepL 실패, 구글로 대체: %s", e)

        for t in todo:
            if t in translated:
                continue
            if self.failures >= MAX_CONSECUTIVE_FAILURES:
                log.warning("번역 연속 실패 %d회 → 남은 %d건 건너뜀", self.failures, len(todo) - len(translated))
                break
            try:
                translated[t] = self._google_one(t)
                self.failures = 0
                self.engine_used = self.engine_used or "Google"
                time.sleep(0.15)  # 비공식 엔드포인트에 예의상 간격
            except Exception as e:  # noqa: BLE001
                self.failures += 1
                log.warning("구글 번역 실패: %s", e)

        for src, ko in translated.items():
            self.cache[src] = {"ko": ko, "t": now}
        result.update(translated)
        return result
