"""설정값 모음. (≈ Spring의 application.yml + @ConfigurationProperties)

값만 두고 로직은 두지 않는다.
"""

from pathlib import Path

# ── 경로 ────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "docs" / "data"
LATEST_PATH = DATA_DIR / "latest.json"
HISTORY_PATH = DATA_DIR / "history.json"

# history.json 에 지수별로 남길 최대 일수 (화면은 3개월만 쓰지만 여유 있게 보관)
HISTORY_KEEP_DAYS = 800

# ── 지수 ────────────────────────────────────────────────
# key 는 JSON/화면에서 쓰는 식별자
INDICES = {
    # subject: 쉬운 설명 문장의 주어 (조사 포함, 받침 문제 없게 고정)
    # long_*: '역대 큰 폭락' 목록 기준 (최소 하락률, 시작일)
    "nasdaq": {"symbol": "^IXIC", "name": "나스닥 종합", "short": "나스닥", "subject": "나스닥 지수는",
               "kind": "index", "news_query": "나스닥 급락", "long_min_pct": 30.0, "long_since": "1970-01-01"},
    "sp500": {"symbol": "^GSPC", "name": "S&P 500", "short": "S&P 500", "subject": "S&P 500 지수는",
              "kind": "index", "news_query": "뉴욕증시 급락", "long_min_pct": 30.0, "long_since": "1970-01-01"},
    # 금: 뉴욕 금 선물(연속물), 달러/온스. 데이터는 2000년부터
    "gold": {"symbol": "GC=F", "name": "국제 금값", "short": "금", "subject": "금 값은",
             "kind": "commodity", "news_query": "금값 급락", "long_min_pct": 20.0, "long_since": "2000-01-01"},
}
TROY_OUNCE_G = 31.1034768
DON_G = 3.75  # 금 1돈

# 고점 대비 하락 기준선 (%)
DRAWDOWN_LINES = (-10.0, -20.0, -30.0, -40.0)
# '지난 5년 큰 오르내림' 에서 구간으로 칠 최소 변동률 (%)
BIG_MOVE_PCT = 10.0

# ── 환율 ────────────────────────────────────────────────
FX_YF_SYMBOL = "KRW=X"  # USD/KRW
FX_FALLBACK_URL = "https://api.frankfurter.dev/v1/{start}..?base=USD&symbols=KRW"

# ── 섹터 ETF ────────────────────────────────────────────
SECTOR_ETFS = {
    "SOXX": "반도체",
    "XLK": "기술",
    "XLC": "통신",
    "XLY": "임의소비재",
    "XLP": "필수소비재",
    "XLF": "금융",
    "XLV": "헬스케어",
    "XLI": "산업재",
    "XLE": "에너지",
    "XLB": "소재",
    "XLU": "유틸리티",
    "XLRE": "부동산",
}

# ── 상위 종목 유니버스: 나스닥-100 ─────────────────────────
# 출처: api.nasdaq.com list-type/nasdaq100, 2026-11-08 스냅샷.
# 구성종목은 분기별로 바뀌므로 가끔 수동 갱신한다. (GOOG 는 GOOGL 과 중복이라 제외)
NASDAQ100 = (
    "AAPL ABNB ADBE ADI ADP ADSK AEP ALAB ALNY AMAT AMD AMGN AMZN APP ARM ASML "
    "AVGO AXON BKNG BKR CCEP CDNS CEG CMCSA COST CPRT CRWD CRWV CSCO CSX CTAS "
    "DASH DDOG DXCM EXC FANG FAST FER FTNT GEHC GILD GOOGL HON HONA IDXX INTC "
    "INTU ISRG KDP KLAC LIN LITE LRCX MAR MCHP MDLZ MELI META MNST MPWR MRNA "
    "MRVL MSFT MSTR MU NBIS NFLX NVDA NXPI ODFL ORLY PANW PAYX PCAR PDD PEP "
    "PLTR PYPL QCOM REGN RKLB ROP ROST SBUX SHOP SNDK SNPS SPCX STX TER TMUS "
    "TRI TSLA TTWO TXN VRTX WDAY WDC WMT XEL"
).split()

MOVERS_TOP_N = 5
NEWS_PER_TICKER = 2

# ── 뉴스 RSS ────────────────────────────────────────────
HTTP_HEADERS = {"User-Agent": "Mozilla/5.0 (personal market dashboard)"}
HTTP_TIMEOUT = 15

# 시장 분위기
VIX_SYMBOL = "^VIX"
FEAR_GREED_URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
MOOD_KEEP_DAYS = 95  # 미니 차트용 약 3개월

# lang 은 키워드 집계 대상 판별용 (영문만 집계)
MARKET_FEEDS = [
    {
        "name": "Yahoo Finance",
        "url": "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC,^IXIC&region=US&lang=en-US",
        "lang": "en",
    },
    {
        "name": "CNBC",
        "url": "https://www.cnbc.com/id/10000664/device/rss/rss.html",
        "lang": "en",
    },
    {
        "name": "Google News",
        "url": "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=en-US&gl=US&ceid=US:en",
        "lang": "en",
    },
    {
        # 한국어 마감 시황 요약 (연합뉴스·인포맥스 등). 번역 불필요
        "name": "구글 뉴스(한국어)",
        "url": "https://news.google.com/rss/search?q=%EB%89%B4%EC%9A%95%EC%A6%9D%EC%8B%9C+when:1d&hl=ko&gl=KR&ceid=KR:ko",
        "lang": "ko",
    },
]

# ── 일정 달력 ───────────────────────────────────────────
CALENDAR_MONTHS_AHEAD = 2  # 이번 달 + 다음 2개월
EARNINGS_WATCH = {
    "AAPL": "애플", "MSFT": "마이크로소프트", "NVDA": "엔비디아", "AMZN": "아마존",
    "GOOGL": "알파벳", "META": "메타", "TSLA": "테슬라",
}

# ── 번역 (영→한, 제목만) ─────────────────────────────────
TRANSLATION_CACHE_PATH = ROOT / "cache" / "translations.json"
TRANSLATION_CACHE_KEEP = 3000
MARKET_NEWS_COUNT = 10
NEWS_PER_SOURCE_MAX = 4  # 화면 10개 중 한 출처 최대 개수
KEYWORD_TOP_N = 15

TICKER_FEED_URL = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}&region=US&lang=en-US"
TICKER_FEED_FALLBACK_URL = "https://news.google.com/rss/search?q={symbol}+stock&hl=en-US&gl=US&ceid=US:en"
