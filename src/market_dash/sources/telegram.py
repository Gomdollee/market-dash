"""텔레그램 봇으로 메시지 보내기. 토큰·채팅 ID 는 환경변수(GitHub Secrets)로만 받는다."""

from __future__ import annotations

import os

import requests

from market_dash import config


def credentials() -> tuple[str, str] | None:
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    return (token, chat) if token and chat else None


def send(text: str, creds: tuple[str, str]) -> None:
    token, chat = creds
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": chat, "text": text, "disable_web_page_preview": "true"},
            timeout=config.HTTP_TIMEOUT,
        )
    except requests.RequestException as e:
        # requests 예외 메시지에는 URL(=토큰 포함)이 들어갈 수 있어 종류만 남긴다
        raise RuntimeError(f"텔레그램 연결 실패: {type(e).__name__}") from None
    if not r.ok:
        raise RuntimeError(f"텔레그램 전송 실패: HTTP {r.status_code} {r.text[:200].replace(token, '***')}")
