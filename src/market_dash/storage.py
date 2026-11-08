"""JSON 저장/로드와 '실패 시 마지막 성공값 유지' 병합. (≈ Repository 계층)"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class FetchResult:
    """수집 1건의 결과. ok=False 면 data 는 무시되고 error 에 사유."""

    ok: bool
    data: Any = None
    error: str | None = None


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path: Path, obj: Any) -> None:
    """임시 파일에 쓴 뒤 교체 → 중간에 죽어도 기존 파일이 반쯤 깨지지 않음."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def merge_section(prev: dict | None, result: FetchResult, now_iso: str) -> dict:
    """섹션 하나의 최종 상태.

    status:
      ok    - 이번 실행에서 성공
      stale - 이번에 실패, 이전 성공 데이터 표시 중
      error - 실패했고 보여줄 이전 데이터도 없음
    """
    if result.ok:
        return {
            "status": "ok",
            "attempted_at": now_iso,
            "last_success_at": now_iso,
            "error": None,
            "data": result.data,
        }
    prev = prev or {}
    has_prev = prev.get("data") is not None
    return {
        "status": "stale" if has_prev else "error",
        "attempted_at": now_iso,
        "last_success_at": prev.get("last_success_at") if has_prev else None,
        "error": result.error,
        "data": prev.get("data") if has_prev else None,
    }


def upsert_rows(existing: list[dict], new_rows: list[dict], keep: int) -> list[dict]:
    """date 키로 합치고(새 값 우선) 날짜순 정렬 후 최근 keep 개만 남김."""
    by_date = {r["date"]: r for r in existing}
    for r in new_rows:
        by_date[r["date"]] = r
    merged = [by_date[d] for d in sorted(by_date)]
    return merged[-keep:]
