"""헤드라인 키워드 집계 (영문만). 순수 함수."""

from __future__ import annotations

import re
from collections import Counter

# 일반 영어 불용어 + 뉴스 상투어 + 너무 당연한 시장 단어
STOPWORDS = frozenset(
    """
    a an the and or but nor so yet for of to in on at by from with without into onto over under
    about above below after before since until amid among between through during against per via
    is are was were be been being am do does did done have has had having will would shall should
    can could may might must not no yes this that these those it its it's they them their there
    here what which who whom whose why how when where than then as if also just only more most
    less least very much many some any all each every both few other another such own same too
    new says said say set get gets got make makes made take takes took see sees seen out up down
    off back now still even ever again here's what's who's you your we our us i me my he she his her
    one two three first last next week weeks day days today year years month months time
    report reports news live update updates latest video watch inside why's could've
    stock stocks market markets share shares
    behind history move moves prediction predictions ago worth invested heres could why
    like big biggest right way ways things thing need know look looks going coming come comes
    ahead hold forever top best worst shouldn't don't can't won't isn't
    """.split()
)

_TOKEN = re.compile(r"[a-z][a-z0-9&'\-]*[a-z0-9]|[a-z]")


def tokenize(title: str) -> list[str]:
    words = []
    for tok in _TOKEN.findall(title.lower()):
        tok = tok.removesuffix("'s").strip("'-")
        if len(tok) >= 3 and tok not in STOPWORDS and not tok.isdigit():
            words.append(tok)
    return words


def top_keywords(titles: list[str], n: int) -> list[dict]:
    """헤드라인별로 한 번씩만 세서(같은 제목 안 중복 무시) 많이 나온 순.

    동률이면 단어 사전순으로 정렬해 결과가 항상 같게 한다.
    """
    counter: Counter[str] = Counter()
    for t in titles:
        counter.update(set(tokenize(t)))
    ranked = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
    return [{"word": w, "count": c} for w, c in ranked[:n] if c >= 2]
