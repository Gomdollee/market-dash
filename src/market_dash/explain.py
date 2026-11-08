"""주린이용 쉬운 설명 문장 - 규칙 기반 템플릿 (LLM 아님, 순수 함수).

숫자는 이미 계산된 값을 받아 문장으로만 바꾼다.
"""

from __future__ import annotations

# (상한 하락률, 이름, 설명). dd 가 상한보다 크면(덜 떨어졌으면) 해당 구간
ZONES = [
    (-5.0, "고점 근처", "사상 최고점과 거의 비슷한 수준이에요."),
    (-10.0, "약한 하락", "주식시장에서 흔히 있는 정도의 출렁임이에요."),
    (-20.0, "조정", "최고점보다 10% 이상 떨어지면 '조정'이라고 불러요."),
    (-30.0, "약세장", "20% 이상 떨어지면 '약세장(베어마켓)'이라고 불러요. 경기 걱정이 큰 시기예요."),
    (-40.0, "깊은 약세장", "역사적으로도 드문 큰 하락이에요."),
]
LAST_ZONE = ("역사적 폭락", "닷컴버블·금융위기 때나 있었던 수준의 하락이에요.")

# 게이지 기준선 이름 (선을 넘으면 들어가는 구간)
LINE_NAMES = {-10.0: "조정", -20.0: "약세장", -30.0: "깊은 약세장", -40.0: "역사적 폭락"}


def drawdown_zone(dd_pct: float) -> dict:
    for upper, label, desc in ZONES:
        if dd_pct > upper:
            return {"label": label, "desc": desc}
    return {"label": LAST_ZONE[0], "desc": LAST_ZONE[1]}


def _move(pct: float) -> str:
    if pct > 0:
        return f"{pct:.2f}% 올랐어요"
    if pct < 0:
        return f"{abs(pct):.2f}% 내렸어요"
    return "변동이 없었어요"


def index_summary(subject: str, change_pct: float, dd_pct: float, next_line: float | None,
                  remaining_pp: float | None) -> list[str]:
    """subject 는 조사까지 포함한 주어 ('나스닥 지수는', '금 값은').

    예) ['나스닥 지수는 지난 거래일에 1.09% 올랐어요.', "최고점보다 10.9% 낮은 '조정' 상태예요.", ...]
    """
    lines = [f"{subject} 지난 거래일에 {_move(change_pct)}."]
    if dd_pct >= 0:
        lines.append("지금이 사상 최고점이에요!")
    else:
        zone = drawdown_zone(dd_pct)["label"]
        lines.append(f"최고점보다 {abs(dd_pct):.1f}% 낮은 '{zone}' 상태예요.")
    if next_line is not None and remaining_pp is not None:
        lines.append(f"'{LINE_NAMES.get(next_line, f'{next_line:.0f}%')}' 단계({next_line:.0f}%)까지 "
                     f"{remaining_pp:.1f}%p 더 떨어지면 도달해요.")
    return lines


def fx_summary(rate: float, prev_rate: float) -> list[str]:
    diff = rate - prev_rate
    won = f"{abs(diff):,.0f}원" if abs(diff) >= 1 else f"{abs(diff):.1f}원"
    if diff > 0:
        return [f"환율이 {won} 올랐어요 (1달러 = {rate:,.0f}원).",
                "달러가 비싸지면, 미국 주식을 원화로 따진 가치는 늘어나요."]
    if diff < 0:
        return [f"환율이 {won} 내렸어요 (1달러 = {rate:,.0f}원).",
                "달러가 싸지면, 미국 주식을 원화로 따진 가치는 줄어들어요."]
    return [f"환율은 그대로예요 (1달러 = {rate:,.0f}원)."]


def _duration(days: int) -> str:
    """일수 → '약 2년 3개월' / '약 5개월' / '23일'."""
    if days < 45:
        return f"{days}일"
    months = round(days / 30.44)
    y, m = divmod(months, 12)
    if y and m:
        return f"약 {y}년 {m}개월"
    if y:
        return f"약 {y}년"
    return f"약 {m}개월"


def five_year_summary(subject: str, episodes: list[dict]) -> list[str]:
    """최고점 대비 큰 하락 에피소드 → 쉬운 문장. subject 예: '나스닥 지수는'."""
    if not episodes:
        return [f"지난 5년 동안 {subject} 최고점보다 10% 넘게 떨어진 적이 없어요."]
    lines = [f"지난 5년 동안 {subject} 최고점보다 10% 넘게 떨어진 적이 {len(episodes)}번 있었어요."]
    worst = min(episodes, key=lambda e: e["depth_pct"])
    period = f"{worst['peak']['date'][:7].replace('-', '.')}~{worst['bottom']['date'][:7].replace('-', '.')}"
    lines.append(f"가장 크게 떨어진 건 {period}의 {worst['depth_pct']:.1f}%예요.")
    rec = worst["recovered"]
    if rec:
        lines.append(f"그때는 바닥에서 다시 최고점을 회복하기까지 {_duration(rec['days_from_bottom'])} 걸렸어요.")
    else:
        lines.append("그 하락은 아직 최고점을 회복하지 못했어요.")
    return lines


def krw_summary(subject: str, krw_pct: float, idx_pct: float, fx_pct: float) -> str:
    sign = lambda v: f"{v:+.2f}%"  # noqa: E731
    # subject 에 조사를 포함시켜 받침과 상관없이 항상 맞게 ('나스닥 지수는', '금 값은')
    return (f"원화로 투자했다면 {subject} {sign(krw_pct)}예요 "
            f"(달러 기준 {sign(idx_pct)} + 환율 {sign(fx_pct)} 효과).")
