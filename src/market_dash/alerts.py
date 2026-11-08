"""급락 알림 판정 - 순수 함수 (보내기는 sources/telegram.py).

상태(state)에 '이미 알린 단계'를 기억해 같은 내용을 30분마다 반복해서 보내지 않는다.
≈ Spring 에서 '이미 발송한 알림' 테이블을 보고 중복 발송을 막는 것과 같은 역할.
"""

from __future__ import annotations

from market_dash.explain import LINE_NAMES, vix_zone

# 하루 하락률 단계(%). 더 깊은 단계에 처음 닿을 때만 알림
DAY_DROP_STEPS = (-2.0, -3.0, -5.0, -7.0)
# 최고점 대비 기준선. 회복해서 선보다 RESET_PP 이상 올라오면 다시 알릴 수 있게 초기화
DRAWDOWN_LINES = (-10.0, -20.0, -30.0, -40.0)
DD_RESET_PP = 2.0
# VIX 돌파 단계. 단계보다 VIX_RESET 이상 내려오면 초기화
VIX_LEVELS = (30.0, 40.0)
VIX_RESET = 3.0


def _deepest(value: float, steps: tuple[float, ...]) -> float | None:
    hit = [s for s in steps if value <= s]
    return min(hit) if hit else None


def detect_alerts(snap: dict, state: dict) -> tuple[list[str], dict]:
    """snap: {"assets": {key: {name, as_of, close, change_pct, drawdown_pct, when}}, "vix": {close, when} | None}

    when 은 '장중 23:30' / '11.06 마감' 같은 표시용 문자열.
    반환: (알림 문장 목록, 새 상태). state 는 바꾸지 않는다.
    """
    new = {"day": dict(state.get("day", {})), "dd": dict(state.get("dd", {})), "vix": state.get("vix")}
    msgs: list[str] = []

    for key, a in snap.get("assets", {}).items():
        # ① 하루 급락: 같은 거래일 안에서 더 깊은 단계에 처음 닿을 때
        step = _deepest(a["change_pct"], DAY_DROP_STEPS)
        prev = new["day"].get(key)
        prev_step = prev["step"] if prev and prev["date"] == a["as_of"] else None
        if step is not None and (prev_step is None or step < prev_step):
            msgs.append(f"🔻 {a['name']} 하루 {a['change_pct']:+.2f}% ({a['when']})\n"
                        f"   지금 {a['close']:,.2f} · 최고점 대비 {a['drawdown_pct']:.1f}%")
            new["day"][key] = {"date": a["as_of"], "step": step}

        # ② 최고점 대비 기준선 새로 돌파
        line = _deepest(a["drawdown_pct"], DRAWDOWN_LINES)
        prev_line = new["dd"].get(key)
        if line is not None and (prev_line is None or line < prev_line):
            msgs.append(f"⚠️ {a['name']} 최고점 대비 {a['drawdown_pct']:.1f}% → "
                        f"'{LINE_NAMES[line]}'({line:.0f}%) 구간 진입 ({a['when']})")
            new["dd"][key] = line
        elif prev_line is not None and a["drawdown_pct"] > prev_line + DD_RESET_PP:
            new["dd"][key] = line  # 회복 → 더 얕은 단계(또는 None)로 내려 다음 하락 때 다시 알림

    # ③ VIX 공포 구간 돌파
    vix = snap.get("vix")
    if vix:
        hit = [lv for lv in VIX_LEVELS if vix["close"] >= lv]
        level = max(hit) if hit else None
        prev_lv = new["vix"]
        if level is not None and (prev_lv is None or level > prev_lv):
            msgs.append(f"😱 공포지수 VIX {vix['close']:.1f} → {level:.0f} 돌파, "
                        f"'{vix_zone(vix['close'])['label']}' 구간 ({vix['when']})")
            new["vix"] = level
        elif prev_lv is not None and vix["close"] < prev_lv - VIX_RESET:
            new["vix"] = level

    return msgs, new


def status_lines(snap: dict) -> list[str]:
    """연결 확인 메시지용 현재 상태 요약."""
    out = [f"• {a['name']} {a['close']:,.2f} ({a['change_pct']:+.2f}%, 최고점 대비 {a['drawdown_pct']:.1f}%)"
           for a in snap.get("assets", {}).values()]
    if snap.get("vix"):
        out.append(f"• VIX {snap['vix']['close']:.1f}")
    return out
