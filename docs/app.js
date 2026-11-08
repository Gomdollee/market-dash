// 표시 전용. 숫자 계산은 전부 Python(market_dash) 에서 끝내고 여기서는 포맷만 한다.
"use strict";

const LINES = [-10, -20, -30, -40];
const ASSETS = [
  { key: "nasdaq", label: "나스닥", color: "--s-nasdaq" },
  { key: "sp500", label: "S&P 500", color: "--s-sp500" },
  { key: "gold", label: "금", color: "--s-gold" },
];
const LINE_NAMES = { "-10": "조정", "-20": "약세장", "-30": "깊은 약세장", "-40": "폭락" };
const GAUGE_SCALE = 50; // 게이지 오른쪽 끝 = -50%
const state = {
  latest: null, history: null, indexKey: "nasdaq", moverKey: "gainers", chart: null,
  calMonth: null, calDay: null, fiveKey: "nasdaq", chart5: null,
};

// ── 유틸 ──────────────────────────────────────────────
function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === "class") node.className = v;
    else if (k === "style") node.style.cssText = v;
    else node.setAttribute(k, v);
  }
  for (const c of children.flat()) {
    if (c == null || c === false) continue;
    node.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return node;
}
const $ = (id) => document.getElementById(id);
const safeUrl = (u) => (/^https?:\/\//i.test(u || "") ? u : null);

const nf = (d) => new Intl.NumberFormat("ko-KR", { minimumFractionDigits: d, maximumFractionDigits: d });
const num = (v, d = 2) => (v == null ? "–" : nf(d).format(v));
const dir = (v) => (v == null || v === 0 ? "flat" : v > 0 ? "up" : "down");
function pct(v, d = 2) {
  if (v == null) return "–";
  const arrow = v > 0 ? "▲" : v < 0 ? "▼" : "";
  return `${arrow} ${v > 0 ? "+" : ""}${nf(d).format(v)}%`.trim();
}
const pctSpan = (v, d) => el("span", { class: dir(v) }, pct(v, d));

const kstFmt = new Intl.DateTimeFormat("ko-KR", {
  timeZone: "Asia/Seoul", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false,
});
function kst(iso) {
  if (!iso) return "–";
  const p = Object.fromEntries(kstFmt.formatToParts(new Date(iso)).map((x) => [x.type, x.value]));
  return `${p.month}/${p.day} ${p.hour}:${p.minute}`;
}
const md = (d) => (d ? `${d.slice(5, 7)}/${d.slice(8, 10)}` : "–");
const ymd = (d) => (d ? d.replaceAll("-", ".") : "–");

function vol(v) {
  if (v == null) return "–";
  if (v >= 1e8) return `${(v / 1e8).toFixed(2)}억주`;
  if (v >= 1e4) return `${Math.round(v / 1e4).toLocaleString("ko-KR")}만주`;
  return `${v.toLocaleString("ko-KR")}주`;
}

function relTime(iso) {
  if (!iso) return "";
  const min = Math.round((Date.now() - new Date(iso)) / 60000);
  if (min < 60) return `${Math.max(min, 1)}분 전`;
  if (min < 60 * 24) return `${Math.round(min / 60)}시간 전`;
  return kst(iso);
}

/** 섹션 상태 → 실패 배지 (ok 면 null) */
function staleBadge(sec) {
  if (!sec || sec.status === "ok") return null;
  const msg = sec.status === "stale"
    ? `업데이트 실패 (마지막 갱신 ${kst(sec.last_success_at)})`
    : "업데이트 실패 (표시할 데이터 없음)";
  return el("div", { class: "stale", title: sec.error || "" }, `⚠ ${msg}`);
}

function mount(target, ...nodes) {
  const t = typeof target === "string" ? $(target) : target;
  t.replaceChildren(...nodes.flat().filter(Boolean));
}

function setupTabs(containerId, stateKey, render) {
  $(containerId).addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-key]");
    if (!btn) return;
    state[stateKey] = btn.dataset.key;
    for (const b of $(containerId).querySelectorAll("button")) {
      b.setAttribute("aria-selected", String(b === btn));
    }
    render();
  });
}

// ── 한눈에 보기 ───────────────────────────────────────
function renderSummary() {
  const S = state.latest.sections;
  const st = marketStatus();
  const items = [];

  for (const { key } of ASSETS) {
    const d = S[key]?.data;
    if (d?.summary) items.push(el("li", {}, el("span", { class: "tag" }, d.short), d.summary.join(" ")));
  }
  const withKrw = ASSETS.map((a) => S[a.key]?.data).filter((d) => d?.krw);
  if (withKrw.length) {
    items.push(el("li", {}, el("span", { class: "tag" }, "원화"), "한국 돈으로 투자했다면 ",
      withKrw.map((d, i) => [i ? ", " : "", `${d.short} `, pctSpan(d.krw.change_pct)]),
      ` (환율 ${pct(withKrw[0].krw.fx_change_pct)} 효과 포함)`));
  }
  if (S.fx?.data?.summary) items.push(el("li", {}, el("span", { class: "tag" }, "환율"), S.fx.data.summary.join(" ")));

  const today = etToday();
  const limit = new Date(utcDate(today).getTime() + 7 * 864e5).toISOString().slice(0, 10);
  const soon = calendarEvents().filter((e) => e.date >= today && e.date <= limit).slice(0, 3);
  if (soon.length) {
    items.push(el("li", {}, el("span", { class: "tag" }, "일정"),
      soon.map((e, i) => [i ? " · " : "", el("b", {}, mdDow(e.date)), " ", e.title])));
  }

  const stale = ["nasdaq", "sp500", "gold", "fx"].some((k) => S[k] && S[k].status !== "ok");
  mount("summary-body",
    st && el("div", { class: `status ${st.open ? "open" : "closed"}` },
      el("span", { class: "dot", "aria-hidden": "true" }),
      el("div", {}, el("b", {}, st.text), el("div", { class: "sub" }, st.sub))),
    el("ul", { class: "plain-list" }, items),
    stale ? el("div", { class: "sub" }, "※ 일부 항목은 업데이트에 실패해 마지막으로 성공한 데이터 기준이에요.") : null);
}

// ── 1·2·4 지수 ────────────────────────────────────────
function renderGauge(d) {
  const dd = d.drawdown_pct;
  const g = d.gauge;
  const fillW = Math.min(Math.abs(dd), GAUGE_SCALE) / GAUGE_SCALE * 100;
  const pos = (line) => `${Math.abs(line) / GAUGE_SCALE * 100}%`;

  const headRight = g.next_line == null
    ? el("strong", { class: "down" }, `${LINES.at(-1)}% 아래 (역사적 폭락)`)
    : el("span", {}, `'${LINE_NAMES[g.next_line]}'(${g.next_line}%)까지 `, el("strong", {}, `${num(g.remaining_pp)}%p`));

  return el("div", { class: "gauge" },
    el("div", { class: "gauge-head" },
      el("span", { class: "muted" }, "하락 단계"),
      headRight),
    el("div", {
      class: "gauge-track", role: "meter", "aria-valuemin": "0", "aria-valuemax": String(GAUGE_SCALE),
      "aria-valuenow": String(Math.abs(dd)), "aria-label": `고점 대비 ${dd}%`,
    },
      el("div", { class: "gauge-fill", style: `width:${fillW}%` }),
      LINES.map((l) => el("div", { class: "gauge-tick", style: `left:calc(${pos(l)} - 1px)` }))),
    el("div", { class: "gauge-labels" },
      LINES.map((l) => el("span", { class: dd <= l ? "passed" : null, style: `left:${pos(l)}` },
        `${l}%`, el("br"), LINE_NAMES[l]))));
}

function renderIndex() {
  const sec = state.latest.sections[state.indexKey];
  const d = sec?.data;
  if (!d) return mount("index-body", staleBadge(sec));

  const isGold = d.kind === "commodity";
  const krw = d.krw
    ? el("dd", {}, pctSpan(d.krw.change_pct), el("br"),
        el("small", {}, `${isGold ? "달러 기준" : "지수"} ${pct(d.change_pct)} · 환율 ${pct(d.krw.fx_change_pct)}`))
    : el("dd", { class: "muted" }, "환율 데이터 없음");

  mount("index-body",
    staleBadge(sec),
    el("div", { class: "hero" },
      el("span", { class: "value" }, isGold ? `$${num(d.close)}` : num(d.close)),
      isGold ? el("span", { class: "muted" }, "/온스") : null,
      el("span", { class: "chg" }, pctSpan(d.change_pct))),
    isGold && d.gold_krw ? el("div", { class: "gold-krw" },
      "한국 돈으로 ", el("b", {}, `1돈(3.75g) 약 ${nf(1).format(d.gold_krw.per_don / 10000)}만원`),
      el("span", { class: "muted" }, ` · 1g ${nf(0).format(d.gold_krw.per_gram)}원`)) : null,
    el("div", { class: "sub" }, `${ymd(d.as_of)} 마감 기준 · 전날(${md(d.prev_date)}) ${num(d.prev_close)}`),
    el("dl", { class: "kv" },
      el("dt", {}, "최고점 대비"),
      el("dd", {},
        d.zone ? el("span", { class: "zone", title: d.zone.desc }, d.zone.label) : null,
        el("strong", { class: dir(d.drawdown_pct) }, `${num(d.drawdown_pct)}%`), el("br"),
        el("small", {}, `역대 최고 ${num(d.peak.value)} (${ymd(d.peak.date)})`)),
      el("dt", {}, "원화로 환산"),
      krw),
    d.zone ? el("div", { class: "zone-desc" }, `'${d.zone.label}' — ${d.zone.desc}`) : null,
    renderGauge(d));
}

// ── 3 환율 ────────────────────────────────────────────
function renderFx() {
  const sec = state.latest.sections.fx;
  const d = sec?.data;
  mount("fx-body",
    staleBadge(sec),
    d && el("div", { class: "fx-row" },
      el("span", { class: "value" }, `${num(d.rate)}원`),
      el("span", {}, pctSpan(d.change_pct), el("span", { class: "muted" }, ` (${d.change_pct >= 0 ? "+" : ""}${num(d.rate - d.prev_rate)}원)`))),
    d && el("div", { class: "sub" }, `${ymd(d.as_of)} 기준 · 전날 ${num(d.prev_rate)}원 · ${d.source}`),
    d?.summary ? el("p", { class: "plain" }, d.summary.join(" ")) : null);
}

// ── 5 하락률 차트 ─────────────────────────────────────
function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function chartRows() {
  const h = state.history || {};
  const last = ASSETS.map((a) => (h[a.key] || []).at(-1)?.date).filter(Boolean).sort().at(-1);
  if (!last) return [];
  const from = new Date(last + "T00:00:00Z");
  from.setUTCMonth(from.getUTCMonth() - 3);
  const fromStr = from.toISOString().slice(0, 10);

  const map = new Map();
  for (const { key } of ASSETS) {
    for (const r of h[key] || []) {
      if (r.date < fromStr) continue;
      if (!map.has(r.date)) map.set(r.date, { date: r.date });
      map.get(r.date)[key] = r.drawdown_pct;
    }
  }
  return [...map.values()].sort((a, b) => a.date.localeCompare(b.date));
}

// 호버 시 세로 가이드선 (크로스헤어)
const crosshair = {
  id: "crosshair",
  afterDatasetsDraw(chart) {
    const active = chart.tooltip?.getActiveElements?.();
    if (!active?.length) return;
    const { ctx, chartArea } = chart;
    const x = active[0].element.x;
    ctx.save();
    ctx.strokeStyle = cssVar("--line");
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x, chartArea.top);
    ctx.lineTo(x, chartArea.bottom);
    ctx.stroke();
    ctx.restore();
  },
};

function renderChart() {
  const rows = chartRows();
  const statusSecs = ASSETS.map((a) => state.latest.sections[a.key]);
  mount("chart-status", ...statusSecs.map(staleBadge));

  // 표 보기
  mount("dd-table", rows.length ? el("div", { class: "scroll" }, el("table", {},
    el("thead", {}, el("tr", {}, el("th", {}, "날짜"), ASSETS.map((a) => el("th", {}, a.label)))),
    el("tbody", {}, [...rows].reverse().map((r) =>
      el("tr", {}, el("td", {}, ymd(r.date)), ASSETS.map((a) => el("td", {}, `${num(r[a.key])}%`))))))) : "데이터 없음");

  if (typeof Chart === "undefined") {
    mount("chart-status", el("div", { class: "stale" }, "차트 라이브러리를 불러오지 못했습니다. 아래 표로 보기를 이용하세요."));
    return;
  }
  if (!rows.length) return;

  const values = rows.flatMap((r) => ASSETS.map((a) => r[a.key])).filter((v) => v != null);
  const yMin = Math.floor((Math.min(...values) - 3) / 5) * 5;
  const labels = rows.map((r) => r.date);
  const text2 = cssVar("--text-2"), muted = cssVar("--muted"), grid = cssVar("--border"), line = cssVar("--line");

  const series = ASSETS.map((a) => ({ ...a, color: cssVar(a.color) })).map((s) => ({
    label: s.label,
    data: rows.map((r) => r[s.key]),
    borderColor: s.color,
    backgroundColor: s.color,
    borderWidth: 2,
    pointRadius: 0,
    pointHoverRadius: 4,
    pointHoverBorderWidth: 2,
    pointHoverBorderColor: cssVar("--surface"),
    tension: 0.15,
    spanGaps: true,
  }));
  const refLines = LINES.filter((l) => l >= yMin).map((l) => ({
    label: `${l}% 기준선`,
    data: labels.map(() => l),
    borderColor: line,
    borderWidth: 1,
    borderDash: [4, 4],
    pointRadius: 0,
    pointHoverRadius: 0,
    isRef: true,
  }));

  state.chart?.destroy();
  state.chart = new Chart($("dd-chart"), {
    type: "line",
    data: { labels, datasets: [...series, ...refLines] },
    plugins: [crosshair],
    options: {
      maintainAspectRatio: false,
      animation: false,
      interaction: { mode: "index", intersect: false },
      scales: {
        x: {
          ticks: { color: muted, maxTicksLimit: 4, maxRotation: 0, callback: (v, i) => md(labels[i]) },
          grid: { display: false },
          border: { color: grid },
        },
        y: {
          min: yMin, max: 0,
          ticks: { color: muted, stepSize: 5, callback: (v) => `${v}%` },
          grid: { color: grid },
          border: { display: false },
        },
      },
      plugins: {
        legend: {
          position: "top", align: "start",
          labels: { color: text2, boxWidth: 12, boxHeight: 2, filter: (item, data) => !data.datasets[item.datasetIndex].isRef },
        },
        tooltip: {
          filter: (item) => !item.dataset.isRef,
          callbacks: {
            title: (items) => ymd(labels[items[0].dataIndex]),
            label: (item) => ` ${item.dataset.label}: ${num(item.parsed.y)}%`,
          },
        },
      },
    },
  });
}

// ── 지난 5년 큰 오르내림 ──────────────────────────────
function duration(days) {
  if (days < 45) return `${days}일`;
  const months = Math.round(days / 30.44);
  const y = Math.floor(months / 12), m = months % 12;
  if (y && m) return `약 ${y}년 ${m}개월`;
  return y ? `약 ${y}년` : `약 ${m}개월`;
}
const msOf = (iso) => Date.parse(iso + "T00:00:00Z");
function hexAlpha(hex, a) {
  const h = hex.replace("#", "");
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
  return `rgba(${r}, ${g}, ${b}, ${a})`;
}

// 하락 구간(최고점→바닥) 배경 칠하기
const shade = {
  id: "shade",
  beforeDatasetsDraw(chart, _args, opts) {
    const { ctx, chartArea, scales } = chart;
    ctx.save();
    for (const [a, b] of opts.ranges || []) {
      const x1 = Math.max(scales.x.getPixelForValue(a), chartArea.left);
      const x2 = Math.min(scales.x.getPixelForValue(b), chartArea.right);
      if (x2 <= x1) continue;
      ctx.fillStyle = opts.color;
      ctx.fillRect(x1, chartArea.top, x2 - x1, chartArea.bottom - chartArea.top);
    }
    ctx.restore();
  },
};

/** 하락 구간 1개: 기간·하락폭·회복 + '무슨 일이 있었나' 메모 */
function ddItem(e) {
  const note = e.note;
  return el("li", {},
    el("div", { class: "dd-top" },
      el("span", {},
        el("span", { class: `zone ${e.depth_pct <= -20 ? "bear" : ""}` }, e.label),
        note ? el("b", { class: "dd-title" }, note.title) : null),
      el("strong", { class: "down" }, `${num(e.depth_pct, 1)}%`)),
    el("div", { class: "dd-dates" },
      `${ymd(e.peak.date)} 최고점 → ${ymd(e.bottom.date)} 바닥 (${duration(e.fall_days)} 동안 하락)`),
    el("div", { class: "dd-rec" },
      e.recovered
        ? `✔ ${ymd(e.recovered.date)} 최고점 회복 · 바닥에서 ${duration(e.recovered.days_from_bottom)}`
        : el("b", {}, "⏳ 아직 회복 중이에요")),
    (note || e.news_url) ? el("details", { class: "dd-note" },
      el("summary", {}, "무슨 일이 있었나"),
      note
        ? el("ul", {}, note.points.map((p) => el("li", {}, p)))
        : el("div", { class: "muted" }, "아직 정리된 메모가 없어요."),
      note?.source === "web" ? el("div", { class: "dd-src" }, "※ 최근 사건이라 뉴스 보도를 바탕으로 정리했어요.") : null,
      e.news_url ? el("a", { href: safeUrl(e.news_url), target: "_blank", rel: "noopener noreferrer", class: "dd-link" },
        "↗ 당시 뉴스 검색") : null) : null);
}

function renderFive() {
  const sec = state.latest.sections[state.fiveKey];
  const f = sec?.data?.five_year;
  if (!f) return mount("five-body", staleBadge(sec));

  const drawdowns = f.drawdowns || [];
  const swings = f.swings || [];
  const longAgo = f.long_ago || [];
  const longFrom = f.data_since < "1970" ? "1970" : f.data_since.slice(0, 4);

  mount("five-body",
    staleBadge(sec),
    el("p", { class: "plain", style: "margin-top:0" }, f.summary.join(" ")),
    el("div", { class: "chart-wrap" }, el("canvas", { id: "five-chart", role: "img",
      "aria-label": `${sec.data.short} 5년 주간 가격과 10% 이상 하락 구간` })),
    el("div", { class: "ev-list-head" }, el("span", {}, "최고점 대비 10% 넘게 떨어졌던 때")),
    el("ul", { class: "dd-list" }, drawdowns.map(ddItem)),
    longAgo.length ? el("details", { class: "table-view" },
      el("summary", {}, `더 옛날 큰 폭락 보기 (${f.long_min_pct}% 이상 · ${longFrom}년 이후)`),
      el("ul", { class: "dd-list" }, longAgo.map(ddItem))) : null,
    el("details", { class: "table-view" },
      el("summary", {}, "10% 이상 오르내린 구간 전체 보기 (상승 포함)"),
      el("ul", { class: "dd-list" }, swings.map((s) =>
        el("li", {},
          el("div", { class: "dd-top" },
            el("span", {}, s.kind === "up" ? "▲ " : "▼ ", el("b", {}, s.label)),
            el("strong", { class: dir(s.change_pct) }, pct(s.change_pct, 1))),
          el("div", { class: "dd-dates" },
            `${ymd(s.start.date)} → ${ymd(s.end.date)} (${duration(s.days)})`,
            s.ongoing ? el("b", {}, ` · 진행 중${s.current ? `, 지금은 여기서 ${pct(s.current.from_end_pct, 1)}` : ""}`) : null))))));

  if (typeof Chart === "undefined") return;
  const color = cssVar(ASSETS.find((a) => a.key === state.fiveKey)?.color || "--s-nasdaq");
  const muted = cssVar("--muted"), grid = cssVar("--border");
  const points = f.weekly.map(([d, v]) => ({ x: msOf(d), y: v }));
  const bottoms = drawdowns.map((e) => ({ x: msOf(e.bottom.date), y: e.bottom.value, e }));

  state.chart5?.destroy();
  state.chart5 = new Chart($("five-chart"), {
    type: "line",
    data: {
      datasets: [
        { label: `${sec.data.short} (주간 종가)`, data: points, borderColor: color, backgroundColor: color,
          borderWidth: 2, pointRadius: 0, pointHoverRadius: 4, tension: 0.1 },
        { label: "하락 바닥", data: bottoms, type: "scatter", showLine: false, pointRadius: 5, pointHoverRadius: 7,
          backgroundColor: cssVar("--down"), borderColor: cssVar("--surface"), borderWidth: 2 },
      ],
    },
    plugins: [shade, crosshair],
    options: {
      maintainAspectRatio: false,
      animation: false,
      parsing: false,
      interaction: { mode: "nearest", axis: "x", intersect: false },
      scales: {
        x: { type: "linear", min: points[0]?.x, max: points.at(-1)?.x, grid: { display: false }, border: { color: grid },
          ticks: { color: muted, maxTicksLimit: 6, maxRotation: 0,
            callback: (v) => new Date(v).toISOString().slice(0, 7).replace("-", ".") } },
        y: { grid: { color: grid }, border: { display: false },
          ticks: { color: muted, maxTicksLimit: 5, callback: (v) => nf(0).format(v) } },
      },
      plugins: {
        legend: { display: false },
        shade: { ranges: drawdowns.map((e) => [msOf(e.peak.date), msOf(e.bottom.date)]),
          color: hexAlpha(cssVar("--down"), 0.14) },
        tooltip: {
          callbacks: {
            title: (items) => ymd(new Date(items[0].parsed.x).toISOString().slice(0, 10)),
            label: (item) => item.raw.e
              ? ` 바닥 ${num(item.parsed.y)} (최고점 대비 ${num(item.raw.e.depth_pct, 1)}%)`
              : ` ${num(item.parsed.y)}`,
          },
        },
      },
    },
  });
}

// ── 미국 증시 일정 ────────────────────────────────────
const EV = {
  holiday: { icon: "✕", label: "공휴일 휴장",
    desc: "미국 공휴일이라 주식시장이 열리지 않아요. 이날 밤(한국시간)에는 미국 주식을 사고팔 수 없어요." },
  early_close: { icon: "½", label: "조기폐장",
    desc: "평소(오후 4시)보다 3시간 이른 오후 1시(미국 시간)에 장이 끝나요. 명절 전후라 거래가 적은 편이에요." },
  witching: { icon: "★", label: "네 마녀의 날",
    desc: "주가지수 선물·옵션, 개별 주식 선물·옵션 4가지가 한꺼번에 만기되는 날(3·6·9·12월 셋째 금요일)이에요. 정리하는 거래가 몰려 주가가 크게 출렁이거나 거래량이 확 늘 수 있어요." },
  opex: { icon: "◇", label: "옵션 만기",
    desc: "매달 셋째 금요일, 그달의 옵션 계약이 끝나는 날이에요. 장 막판에 거래가 늘 수 있어요." },
  fomc: { icon: "●", label: "FOMC",
    desc: "미국 중앙은행(연준)이 기준금리를 정하는 회의예요. 금리를 올리면 보통 주식에 부담, 내리면 호재로 봐요. 발표는 한국시간 새벽이에요. '점도표'가 붙으면 앞으로의 금리 전망도 함께 나와요." },
  earnings: { icon: "◆", label: "실적 발표",
    desc: "회사가 지난 3개월 성적표(매출·이익)를 발표하는 날이에요. 예상보다 좋거나 나쁘면 다음 날 주가가 크게 움직일 수 있어요." },
  weekend: { icon: "✕", label: "주말", legend: false,
    desc: "미국 주식시장은 토·일요일에 열리지 않아요. 한국시간으로는 토요일 새벽 장 마감 후 월요일 밤 개장까지 쉬어요." },
  dst: { icon: "◐", label: "서머타임",
    desc: "미국이 시계를 1시간 조정해서, 한국에서 보는 미국장 시간이 1시간 바뀌어요." },
};
const DOW = ["일", "월", "화", "수", "목", "금", "토"];
const etToday = () => new Intl.DateTimeFormat("en-CA", { timeZone: "America/New_York" }).format(new Date());
const utcDate = (iso) => new Date(iso + "T00:00:00Z");
const mdDow = (iso) => `${md(iso)}(${DOW[utcDate(iso).getUTCDay()]})`;
const evIcon = (type) => el("span", { class: "ev-icon", style: `color:var(--ev-${type})`, "aria-hidden": "true" }, EV[type]?.icon || "•");

function calendarEvents() {
  return state.latest.sections.calendar?.data?.events || [];
}

const kstPartsFmt = new Intl.DateTimeFormat("ko-KR", {
  timeZone: "Asia/Seoul", month: "numeric", day: "numeric", weekday: "short", hour: "2-digit", minute: "2-digit", hour12: false,
});
function kstWhen(iso) {
  const p = Object.fromEntries(kstPartsFmt.formatToParts(new Date(iso)).map((x) => [x.type, x.value]));
  return `${p.month}/${p.day}(${p.weekday}) ${p.hour}:${p.minute}`;
}

/** 지금 미국 정규장 상태 (보는 시점 기준). sessions 는 Python 이 계산한 거래일별 개장·마감 시각 */
function marketStatus() {
  const cal = state.latest.sections.calendar?.data;
  const sessions = cal?.sessions || [];
  const now = Date.now();
  const cur = sessions.find((s) => now < Date.parse(s.close));
  if (!cur) return null;

  if (now >= Date.parse(cur.open)) {
    return { open: true, text: `지금 미국 정규장이 열려 있어요`, sub: `${kstWhen(cur.close)} 마감${cur.early ? " (조기폐장)" : ""}` };
  }
  const today = etToday();
  const dow = utcDate(today).getUTCDay();
  const hol = (cal.events || []).find((e) => e.date === today && e.type === "holiday");
  let reason;
  if (dow === 0 || dow === 6) reason = "주말이라 미국 시장이 쉬어요";
  else if (hol) reason = `오늘은 미국 ${hol.title.replace("휴장 · ", "")}이라 쉬어요`;
  else if (cur.date === today) reason = "아직 개장 전이에요";
  else reason = "오늘 장은 끝났어요";
  return { open: false, text: reason, sub: `다음 개장 ${kstWhen(cur.open)}${cur.early ? " · 조기폐장일" : ""}` };
}

function eventList(events, todayIso) {
  if (!events.length) return el("div", { class: "sub" }, "일정 없음");
  return el("ul", { class: "ev-list" }, events.map((e) =>
    el("li", {},
      el("span", { class: `ev-date ${e.date === todayIso ? "today" : ""}` }, mdDow(e.date)),
      el("details", { class: "ev-item" },
        el("summary", {}, el("span", { class: "ev-title" }, evIcon(e.type), " ", e.title),
          e.detail ? el("div", { class: "ev-detail" }, e.detail) : null),
        el("div", { class: "ev-desc" }, EV[e.type]?.desc || "")))));
}

function renderCalendar() {
  const sec = state.latest.sections.calendar;
  const d = sec?.data;
  if (!d) return mount("calendar-body", staleBadge(sec));

  const today = etToday();
  const months = [];
  for (let dt = utcDate(d.start); dt <= utcDate(d.end); dt.setUTCMonth(dt.getUTCMonth() + 1)) {
    months.push(dt.toISOString().slice(0, 7));
  }
  if (!months.includes(state.calMonth)) state.calMonth = months.includes(today.slice(0, 7)) ? today.slice(0, 7) : months[0];
  const mi = months.indexOf(state.calMonth);
  const [y, m] = state.calMonth.split("-").map(Number);

  const byDate = new Map();
  for (const e of d.events) {
    if (!byDate.has(e.date)) byDate.set(e.date, []);
    byDate.get(e.date).push(e);
  }

  const firstDow = new Date(Date.UTC(y, m - 1, 1)).getUTCDay();
  const daysIn = new Date(Date.UTC(y, m, 0)).getUTCDate();
  const cells = [];
  for (let i = 0; i < firstDow; i++) cells.push(el("div", { class: "cal-day out" }));
  for (let day = 1; day <= daysIn; day++) {
    const iso = `${state.calMonth}-${String(day).padStart(2, "0")}`;
    const evs = byDate.get(iso) || [];
    const dow = (firstDow + day - 1) % 7;
    const types = [...new Set(evs.map((e) => e.type))];
    const weekend = dow === 0 || dow === 6;
    const holiday = types.includes("holiday");
    const cls = ["cal-day",
      weekend ? "weekend" : "",
      holiday ? "closed" : "",
      iso === today ? "today" : "",
      iso === state.calDay ? "sel" : ""].join(" ");
    const closedLabel = holiday ? "휴장" : weekend ? "휴장" : null;
    cells.push(el("button", {
      class: cls, "data-date": iso,
      "aria-label": `${m}월 ${day}일${weekend ? " · 주말 휴장" : ""}${evs.length ? " · " + evs.map((e) => e.title).join(", ") : ""}`,
    },
      el("span", { class: "n" }, day),
      closedLabel ? el("span", { class: "closed-tag" }, closedLabel) : null,
      el("span", { class: "marks" }, types.filter((t) => t !== "holiday").map(evIcon))));
  }

  // 아래 목록: 날짜 선택 시 그날, 아니면 오늘부터 3주
  let listHead, listEvents;
  if (state.calDay) {
    listHead = el("div", { class: "ev-list-head" }, el("span", {}, `${mdDow(state.calDay)} 일정`),
      el("button", { "data-action": "cal-clear" }, "다가오는 일정 보기"));
    listEvents = byDate.get(state.calDay) || [];
    const selDow = utcDate(state.calDay).getUTCDay();
    if (!listEvents.length && (selDow === 0 || selDow === 6)) {
      listEvents = [{ date: state.calDay, type: "weekend", title: "주말 휴장" }];
    }
  } else {
    const limit = new Date(utcDate(today).getTime() + 21 * 864e5).toISOString().slice(0, 10);
    listHead = el("div", { class: "ev-list-head" }, el("span", {}, "다가오는 일정 · 3주"));
    listEvents = d.events.filter((e) => e.date >= today && e.date <= limit);
  }

  mount("calendar-body",
    staleBadge(sec),
    d.warnings?.length ? el("div", { class: "stale" }, `⚠ ${d.warnings.join(" / ")}`) : null,
    el("div", { class: "cal-nav" },
      el("button", { "data-action": "cal-prev", disabled: mi <= 0 ? "" : null, "aria-label": "이전 달" }, "◀"),
      el("strong", {}, `${y}년 ${m}월`),
      el("button", { "data-action": "cal-next", disabled: mi >= months.length - 1 ? "" : null, "aria-label": "다음 달" }, "▶")),
    el("div", { class: "cal-grid" },
      DOW.map((w, i) => el("div", { class: `cal-dow ${i === 0 ? "sun" : ""}` }, w)),
      cells),
    el("div", { class: "legend" },
      el("span", {}, el("span", { class: "closed-tag" }, "휴장"), " 주말·공휴일"),
      Object.entries(EV).filter(([t, v]) => v.legend !== false && t !== "holiday")
        .map(([t, v]) => el("span", {}, evIcon(t), " ", v.label))),
    listHead,
    eventList(listEvents, today));

  // 이벤트 위임 (매 렌더마다 새로 붙지 않도록 한 번만)
  const body = $("calendar-body");
  if (!body.dataset.bound) {
    body.dataset.bound = "1";
    body.addEventListener("click", (e) => {
      const t = e.target.closest("[data-date],[data-action]");
      if (!t) return;
      const act = t.dataset.action;
      if (t.dataset.date) state.calDay = state.calDay === t.dataset.date ? null : t.dataset.date;
      else if (act === "cal-clear") state.calDay = null;
      else if (act === "cal-prev" || act === "cal-next") {
        const [yy, mm] = state.calMonth.split("-").map(Number);
        const dt = new Date(Date.UTC(yy, mm - 1 + (act === "cal-next" ? 1 : -1), 1));
        state.calMonth = dt.toISOString().slice(0, 7); // 범위 밖이면 renderCalendar 가 보정
      }
      renderCalendar();
    });
  }
}

// ── 6 상위 종목 ───────────────────────────────────────
function renderMovers() {
  const sec = state.latest.sections.movers;
  const d = sec?.data;
  if (!d) return mount("movers-body", staleBadge(sec));
  const list = d[state.moverKey] || [];
  mount("movers-body",
    staleBadge(sec),
    el("ul", { class: "movers" }, list.map((q) =>
      el("li", {},
        el("div", { class: "mv-head" },
          el("span", {},
            el("span", { class: "mv-sym" }, q.name_ko || q.symbol),
            q.name_ko ? el("span", { class: "mv-tk" }, q.symbol) : null,
            el("span", { class: "muted" }, ` $${num(q.close)}`)),
          el("span", { class: "mv-vol" }, vol(q.volume)),
          el("span", { class: `mv-chg ${dir(q.change_pct)}` }, pct(q.change_pct))),
        q.reason ? el("a", { class: "mv-reason", href: safeUrl(q.reason.link), target: "_blank", rel: "noopener noreferrer" },
          el("span", { class: "mv-reason-tag" }, "왜?"),
          el("span", {}, q.reason.title_ko || q.reason.title, el("span", { class: "muted" }, ` · ${q.reason.source}`))) : null,
        q.news?.length ? el("ul", { class: "mv-news" }, q.news.map((n) =>
          el("li", {},
            el("a", { href: safeUrl(n.link), target: "_blank", rel: "noopener noreferrer" }, `↗ ${n.title_ko || n.title}`),
            n.title_ko ? el("div", { class: "orig" }, n.title) : null))) : null))),
    el("div", { class: "sub" }, `${ymd(d.as_of)} 종가 기준 · ${d.universe} ${d.universe_count}종목`));
}

// ── 7 섹터 ────────────────────────────────────────────
function renderSectors() {
  const sec = state.latest.sections.sectors;
  const d = sec?.data;
  if (!d) return mount("sectors-body", staleBadge(sec));
  // 색 진하기: |변동률| 3% 이상이면 최대. 상승 빨강 / 하락 파랑 / 0 은 중립
  const tile = (q) => {
    const amt = Math.round(Math.min(Math.abs(q.change_pct) / 3, 1) * 38);
    const base = q.change_pct > 0 ? "var(--up)" : q.change_pct < 0 ? "var(--down)" : "var(--track)";
    return el("div", {
      class: "sector",
      style: `background: color-mix(in srgb, ${base} ${q.change_pct === 0 ? 100 : amt}%, var(--track))`,
      title: `${q.symbol} ${q.name} ${pct(q.change_pct)} · $${num(q.close)}`,
    },
      el("div", { class: "nm" }, q.name),
      el("div", { class: "sym" }, q.symbol),
      el("div", { class: `pc ${dir(q.change_pct)}` }, pct(q.change_pct)));
  };
  mount("sectors-body",
    staleBadge(sec),
    el("div", { class: "sectors" }, d.items.map(tile)),
    el("div", { class: "sub", style: "margin-top:6px" }, `${ymd(d.as_of)} 종가 기준 · 전일 대비`));
}

// ── 8 뉴스 ────────────────────────────────────────────
function renderNews() {
  const sec = state.latest.sections.news;
  const d = sec?.data;
  if (!d) return mount("news-body", staleBadge(sec));
  mount("news-body",
    staleBadge(sec),
    d.keywords.length ? el("div", { class: "chips" }, d.keywords.map((k) =>
      el("span", { class: "chip", title: k.word }, k.ko || k.word, " ", el("b", {}, k.count)))) : null,
    el("div", { class: "sub" }, `키워드: 최근 영문 헤드라인 ${d.keyword_base_count}개 중 등장한 제목 수`),
    el("ul", { class: "news" }, d.items.map((n) =>
      el("li", {},
        el("a", { href: safeUrl(n.link), target: "_blank", rel: "noopener noreferrer" }, n.title_ko || n.title),
        n.title_ko ? el("div", { class: "orig" }, n.title) : null,
        el("div", { class: "meta" }, [n.source, relTime(n.published)].filter(Boolean).join(" · "))))));
}

// ── 시작 ──────────────────────────────────────────────
async function loadJson(path) {
  const res = await fetch(`${path}?t=${Date.now()}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${path}: HTTP ${res.status}`);
  return res.json();
}

function renderAll() {
  $("generated").textContent = `갱신 ${kst(state.latest.generated_at)}`;
  for (const fn of [renderSummary, renderIndex, renderFx, renderChart, renderFive, renderCalendar, renderMovers, renderSectors, renderNews]) {
    try { fn(); } catch (e) { console.error(fn.name, e); } // 한 칸 오류가 다른 칸을 막지 않게
  }
}

async function main() {
  setupTabs("index-tabs", "indexKey", renderIndex);
  setupTabs("mover-tabs", "moverKey", renderMovers);
  setupTabs("five-tabs", "fiveKey", renderFive);
  try {
    [state.latest, state.history] = await Promise.all([
      loadJson("data/latest.json"),
      loadJson("data/history.json").catch(() => ({})),
    ]);
  } catch (e) {
    $("generated").textContent = "데이터를 불러오지 못했습니다";
    console.error(e);
    return;
  }
  renderAll();
  // 다크/라이트 전환 시 차트 색 다시 적용
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => { renderChart(); renderFive(); });
}

main();
