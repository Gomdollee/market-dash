# market-dash

개인용 주식·환율 대시보드. GitHub Actions가 하루 3번 데이터를 모아 `docs/data/*.json`을 갱신하고, GitHub Pages가 정적 페이지로 보여준다.

## 로컬 실행

```powershell
uv sync
uv run pytest
uv run python -m market_dash.main          # docs/data 갱신
uv run python -m http.server -d docs 8000  # http://localhost:8000
```

## 배포 (최초 1회)

1. GitHub에 **public** 저장소를 만들고 push
2. Settings → Pages → Build and deployment → Source: **GitHub Actions**
3. Actions 탭 → `update-data` → **Run workflow** 로 첫 실행

## 구조

| 경로 | 역할 |
|---|---|
| `src/market_dash/calc.py` | 하락률·게이지·원화 환산 등 순수 계산 |
| `src/market_dash/keywords.py` | 헤드라인 키워드 집계 |
| `src/market_dash/storage.py` | JSON 저장, 실패 시 마지막 성공값 유지 |
| `src/market_dash/sources/` | yfinance · 환율 · RSS 수집 |
| `src/market_dash/main.py` | 진입점 |
| `docs/` | 정적 페이지 + `data/latest.json`, `data/history.json` |
| `.github/workflows/update.yml` | 예약 수집 + 배포 |
| `.github/workflows/ci.yml` | push 시 테스트 + 배포 |
