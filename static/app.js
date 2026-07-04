/* Prisoner's Arena frontend.
   Precompute-then-replay: the server computes the full tournament dataset,
   the client animates and slices it (instant jump-to-round scrubbing). */

"use strict";

/* ================= Palette (dataviz reference, dark mode, fixed order) ================= */
const SERIES = ["#3987e5", "#199e70", "#c98500", "#008300", "#9085e9", "#e66767", "#d55181", "#d95926"];
const GRAY = "#6b6a64";
const INK = "#ffffff", INK2 = "#c3c2b7", MUTED = "#898781", GRID = "#2c2c2a", SURFACE = "#1a1a19";

if (window.Chart) {
  Chart.defaults.color = MUTED;
  Chart.defaults.borderColor = GRID;
  Chart.defaults.font.family = 'system-ui, -apple-system, "Segoe UI", sans-serif';
  Chart.defaults.font.size = 11;
}

/* ================= State ================= */
const state = {
  meta: [],            // built-in strategy metadata
  metaById: {},
  mine: [],            // my custom strategies
  selected: new Set(),
  result: null,        // current tournament dataset
  colors: {},          // strategy id -> color
  spotlight: null,
  sort: { key: "total_score", dir: -1 },
  charts: {},
  replay: { matches: [], ffaRound: 0, ffaTimer: null, fight: null },
  builder: null,       // builder editor state
  editingId: null,     // custom strategy being edited
};

const CATEGORY_CLASS = {
  "Cooperative / Reciprocal": "coop", "Retaliatory": "ret", "Adaptive": "adapt",
  "Exploitative": "exploit", "Statistical / Probabilistic": "stats", "Experimental / Complex": "complex",
};

/* ================= Utilities ================= */
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const pct = (v) => v == null ? "—" : (v * 100).toFixed(1) + "%";
const num = (v, d = 2) => v == null ? "—" : Number(v).toFixed(d);

async function api(method, path, body, withToken) {
  const headers = { "Content-Type": "application/json" };
  if (withToken) headers["X-Anon-Token"] = await ensureToken();
  const resp = await fetch(path, { method, headers, body: body ? JSON.stringify(body) : undefined });
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) throw new Error(typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail || data));
  return data;
}

let tokenPromise = null;
function ensureToken() {
  const existing = localStorage.getItem("arena_token");
  if (existing) return Promise.resolve(existing);
  if (!tokenPromise) {
    tokenPromise = api("POST", "/anon/session").then((d) => {
      localStorage.setItem("arena_token", d.token);
      updateSessionHint();
      return d.token;
    });
  }
  return tokenPromise;
}

function updateSessionHint() {
  const token = localStorage.getItem("arena_token");
  $("session-hint").textContent = token ? `anon-${token.slice(0, 6)}` : "anonymous session";
}

function labelOf(id) {
  if (state.result && state.result.labels[id]) return state.result.labels[id];
  if (state.metaById[id]) return state.metaById[id].short_name;
  const mine = state.mine.find((s) => s.id === id);
  if (mine) return mine.name;
  return id.includes(" - ") ? id.split(" - ")[1] : id;
}

function colorOf(id) { return state.colors[id] || GRAY; }
function chip(id) { return `<span class="chip" style="background:${colorOf(id)}"></span>`; }

/* Payoff scoring client-side (mirrors the server's matrix, sent with each result). */
function payoffOf(m1, m2) {
  const p = state.result.payoff;
  return m1 ? (m2 ? p.cc : p.cd) : (m2 ? p.dc : p.dd);
}

/* ================= Tabs ================= */
$("tabs").addEventListener("click", (e) => {
  const btn = e.target.closest(".tab-btn");
  if (!btn) return;
  showView(btn.dataset.view);
});

function showView(name) {
  document.querySelectorAll(".tab-btn").forEach((b) => b.classList.toggle("active", b.dataset.view === name));
  document.querySelectorAll(".view").forEach((v) => v.classList.toggle("active", v.id === "view-" + name));
  if (name === "marketplace") loadMarketplace();
}

/* ================= Arena: roster & run ================= */
async function loadMeta() {
  const data = await api("GET", "/strategies/meta");
  state.meta = data.strategies;
  state.metaById = Object.fromEntries(data.strategies.map((s) => [s.id, s]));
  renderRoster();
  renderEncyclopedia();
}

function rosterCard(id, name, category, categoryShort, intro) {
  const cls = CATEGORY_CLASS[category] || (category === "Custom" ? "custom" : "complex");
  return `<div class="s-card ${state.selected.has(id) ? "selected" : ""}" data-sid="${esc(id)}" tabindex="0" role="checkbox" aria-checked="${state.selected.has(id)}">
    <span class="check">✓ IN</span>
    <span class="tag ${cls}">${esc(categoryShort)}</span>
    <div class="name">${esc(name)}</div>
    <div class="intro">${esc(intro || "")}</div>
  </div>`;
}

function renderRoster() {
  $("roster").innerHTML = state.meta.map((s) => rosterCard(s.id, s.short_name, s.category, s.category_short, s.intro)).join("");
  const mineCards = state.mine.map((s) => rosterCard(s.id, s.name, "Custom", "Custom", s.description || "Built in the strategy builder."));
  $("my-roster").innerHTML = mineCards.join("");
  $("my-roster-head").style.display = mineCards.length ? "" : "none";
  updateSelectedCount();
}

function updateSelectedCount() {
  $("selected-count").textContent = `${state.selected.size} selected`;
}

function toggleCard(card) {
  const id = card.dataset.sid;
  if (state.selected.has(id)) state.selected.delete(id); else state.selected.add(id);
  card.classList.toggle("selected", state.selected.has(id));
  card.setAttribute("aria-checked", state.selected.has(id));
  updateSelectedCount();
}

for (const container of ["roster", "my-roster"]) {
  $(container).addEventListener("click", (e) => {
    const card = e.target.closest(".s-card");
    if (card) toggleCard(card);
  });
  $(container).addEventListener("keydown", (e) => {
    if (e.key !== "Enter" && e.key !== " ") return;
    const card = e.target.closest(".s-card");
    if (card) { e.preventDefault(); toggleCard(card); }
  });
}

$("btn-select-all").onclick = () => { state.meta.forEach((s) => state.selected.add(s.id)); state.mine.forEach((s) => state.selected.add(s.id)); renderRoster(); };
$("btn-select-none").onclick = () => { state.selected.clear(); renderRoster(); };
$("btn-select-classics").onclick = () => {
  state.selected.clear();
  ["s01", "s02", "s03", "s04", "s05", "s06", "s08", "s13"].forEach((prefix) => {
    const s = state.meta.find((m) => m.id.startsWith(prefix));
    if (s) state.selected.add(s.id);
  });
  renderRoster();
};

$("btn-run").onclick = runTournament;

async function runTournament() {
  const strategies = [...state.selected];
  const statusEl = $("run-status");
  statusEl.className = "status-line";
  if (strategies.length < 2) { statusEl.className = "status-line error"; statusEl.textContent = "Pick at least two strategies."; return; }

  const payload = {
    strategies,
    rounds: Math.max(10, Math.min(5000, Number($("in-rounds").value) || 200)),
    iterations: Math.max(1, Math.min(200, Number($("in-iterations").value) || 1)),
    noise: Math.max(0, Math.min(1, Number($("in-noise").value) || 0)),
  };

  $("btn-run").disabled = true;
  $("run-progress").classList.add("active");
  setProgress(0, "Precomputing tournament…");
  statusEl.textContent = "";

  try {
    const job = await api("POST", "/simulate/async", payload);
    let info = job;
    while (info.status === "pending" || info.status === "running") {
      await new Promise((r) => setTimeout(r, 250));
      info = await api("GET", `/jobs/${job.job_id}`);
      setProgress(info.progress, `Precomputing tournament… ${(info.progress * 100).toFixed(0)}%`);
    }
    if (info.status === "error") throw new Error(info.error || "Simulation failed.");
    setProgress(1, "Loading dataset…");
    const result = await api("GET", `/results/${info.result_id}`);
    onResult(result);
    statusEl.textContent = "Done — see the Dashboard and Replay tabs.";
    showView("dashboard");
  } catch (err) {
    statusEl.className = "status-line error";
    statusEl.textContent = err.message;
  } finally {
    $("btn-run").disabled = false;
    $("run-progress").classList.remove("active");
  }
}

function setProgress(fraction, label) {
  $("run-progress-fill").style.width = `${Math.round(fraction * 100)}%`;
  $("run-progress-label").textContent = label;
}

/* ================= Result intake ================= */
function onResult(result) {
  state.result = result;
  state.spotlight = null;
  state.sort = { key: "total_score", dir: -1 };
  // Fixed-order categorical assignment; entities keep their hue for the whole
  // session of this result. Past 8, series fold into gray + table/spotlight.
  state.colors = {};
  result.config.strategies.forEach((id, index) => {
    state.colors[id] = index < SERIES.length ? SERIES[index] : GRAY;
  });
  prepareReplay();
  renderDashboard();
  renderReplayList();
}

/* ================= Dashboard ================= */
const COLUMNS = [
  { key: "total_score", label: "Total", tip: "All points this strategy scored across every match and iteration.", fmt: (v) => v.toLocaleString() },
  { key: "avg_score_per_round", label: "Pts/round", tip: "Average points earned per round. 3.0 means steady mutual cooperation; above it means successful exploitation.", fmt: (v) => num(v, 3) },
  { key: "win_rate", label: "Win %", tip: "Share of matches finished with a higher score than the opponent. Careful: you can lose most matches and still top the total-score ranking.", fmt: pct },
  { key: "cooperation_rate", label: "Coop %", tip: "Share of all this strategy's moves that were cooperation.", fmt: pct },
  { key: "retaliation_rate", label: "Retaliation", tip: "When the opponent defected, how often this strategy hit back on the very next round.", fmt: pct },
  { key: "forgiveness_rate", label: "Forgiveness", tip: "After a round where both sides defected, how often this strategy offered cooperation again — its ability to escape revenge spirals.", fmt: pct },
  { key: "avg_first_defection_round", label: "1st defect", tip: "Average round of this strategy's first defection in a match. Higher = more patient. (Never defecting counts as rounds+1.)", fmt: (v) => num(v, 1) },
  { key: "early_avg", label: "Early", tip: "Average points per round in the first third of matches.", fmt: (v) => num(v, 2) },
  { key: "mid_avg", label: "Mid", tip: "Average points per round in the middle third of matches.", fmt: (v) => num(v, 2) },
  { key: "late_avg", label: "Late", tip: "Average points per round in the final third. Compare with Early to spot late-game collapses.", fmt: (v) => num(v, 2) },
  { key: "score_volatility", label: "Volatility", tip: "Standard deviation of match scores. High volatility = big wins and big losses; low = consistent results.", fmt: (v) => num(v, 1) },
  { key: "robustness_to_noise", label: "Noise robust", tip: "Score under this run's noise divided by score in a noise-free rerun. Below 1.0 means noise hurts this strategy. Only computed when noise > 0.", fmt: (v) => num(v, 3) },
];

function renderDashboard() {
  const r = state.result;
  if (!r) return;
  $("dash-empty").style.display = "none";
  $("dash-content").style.display = "";

  const champion = r.leaderboard[0];
  const overallCoop = r.leaderboard.reduce((a, x) => a + x.cooperation_rate, 0) / r.leaderboard.length;
  const totalMatches = r.matches.length * r.config.iterations;
  $("dash-tiles").innerHTML = `
    <div class="tile"><div class="t-label" data-tip="Highest total score across all matches.">Champion</div>
      <div class="t-value hero">${chip(champion.strategy)}${esc(labelOf(champion.strategy))}</div>
      <div class="t-sub">${champion.total_score.toLocaleString()} pts</div></div>
    <div class="tile"><div class="t-label">Matches played</div><div class="t-value">${totalMatches.toLocaleString()}</div>
      <div class="t-sub">${r.config.strategies.length} strategies · ${r.config.iterations} iteration${r.config.iterations > 1 ? "s" : ""}</div></div>
    <div class="tile"><div class="t-label">Rounds per match</div><div class="t-value">${r.config.rounds.toLocaleString()}</div>
      <div class="t-sub">early ≤ ${r.config.phase_bounds.early_end} · late > ${r.config.phase_bounds.mid_end}</div></div>
    <div class="tile"><div class="t-label" data-tip="Average cooperation rate across all strategies.">Avg cooperation</div><div class="t-value">${pct(overallCoop)}</div></div>
    <div class="tile"><div class="t-label" data-tip="Moves flipped by noise across the whole tournament (noise setting: ${r.config.noise}).">Noise flips</div>
      <div class="t-value">${r.total_noise_events.toLocaleString()}</div><div class="t-sub">noise = ${r.config.noise}</div></div>`;

  renderRankTable();
  renderCoopChart();
  renderScoreChart();
  renderHeatmap();
  renderPhaseTable();

  $("export-row").innerHTML = `
    <span style="color:${MUTED}; font-size:12px">research export:</span>
    <a href="/results/${r.result_id}/export?format=json" download>full JSON</a>
    <a href="/results/${r.result_id}/export?format=csv&dataset=rounds" download>rounds CSV</a>
    <a href="/results/${r.result_id}/export?format=csv&dataset=leaderboard" download>leaderboard CSV</a>
    <a href="/results/${r.result_id}/export?format=csv&dataset=matrix" download>matrix CSV</a>`;
}

function sortedLeaderboard() {
  const { key, dir } = state.sort;
  return [...state.result.leaderboard].sort((a, b) => {
    const av = a[key], bv = b[key];
    if (av == null && bv == null) return 0;
    if (av == null) return 1;
    if (bv == null) return -1;
    return (av < bv ? -1 : av > bv ? 1 : 0) * dir;
  });
}

function renderRankTable() {
  const rows = sortedLeaderboard();
  const head = `<thead><tr><th>#</th><th class="left">Strategy</th>${COLUMNS.map((c) =>
    `<th class="sortable ${state.sort.key === c.key ? "sorted" : ""}" data-key="${c.key}" data-tip="${esc(c.tip)}">${c.label}${state.sort.key === c.key ? (state.sort.dir < 0 ? " ▾" : " ▴") : ""}</th>`).join("")}</tr></thead>`;
  const body = `<tbody>${rows.map((row, i) => `
    <tr class="clickable ${state.spotlight === row.strategy ? "hl" : ""}" data-strategy="${esc(row.strategy)}">
      <td>${i + 1}</td>
      <td class="left strong">${chip(row.strategy)}${esc(labelOf(row.strategy))}</td>
      ${COLUMNS.map((c) => `<td>${row[c.key] == null ? "—" : c.fmt(row[c.key])}</td>`).join("")}
    </tr>`).join("")}</tbody>`;
  const table = $("rank-table");
  table.innerHTML = head + body;
  table.querySelectorAll("th.sortable").forEach((th) => th.addEventListener("click", () => {
    const key = th.dataset.key;
    state.sort = { key, dir: state.sort.key === key ? -state.sort.dir : -1 };
    renderRankTable();
  }));
  table.querySelectorAll("tr.clickable").forEach((tr) => tr.addEventListener("click", () => {
    state.spotlight = state.spotlight === tr.dataset.strategy ? null : tr.dataset.strategy;
    renderRankTable();
    renderCoopChart();
    renderScoreChart();
  }));
}

/* Which series get their own line: colored slots (first 8) plus the spotlight. */
function chartSeries() {
  const names = state.result.config.strategies;
  const shown = names.filter((n) => state.colors[n] !== GRAY);
  if (state.spotlight && !shown.includes(state.spotlight)) shown.push(state.spotlight);
  return shown;
}

function lineDataset(id, data, opts = {}) {
  const spot = state.spotlight;
  const dim = spot && spot !== id;
  const color = colorOf(id);
  return {
    label: labelOf(id),
    data,
    borderColor: dim ? color + "35" : color,
    backgroundColor: color + "1a",
    borderWidth: spot === id ? 2.5 : 2,
    pointRadius: 0,
    pointHoverRadius: 5,
    pointHoverBackgroundColor: color,
    pointHoverBorderColor: SURFACE,
    pointHoverBorderWidth: 2,
    tension: 0.15,
    ...opts,
  };
}

const BASE_LINE_OPTS = {
  responsive: true,
  maintainAspectRatio: false,
  animation: false,
  interaction: { mode: "index", intersect: false },
  plugins: {
    legend: { labels: { color: INK2, boxWidth: 14, boxHeight: 3 } },
    tooltip: { backgroundColor: "#2c2c2a", titleColor: INK, bodyColor: INK2, borderColor: "rgba(255,255,255,0.1)", borderWidth: 1 },
  },
  scales: {
    x: { grid: { color: GRID, drawTicks: false }, border: { color: "#383835" }, ticks: { maxTicksLimit: 10 } },
    y: { grid: { color: GRID, drawTicks: false }, border: { color: "#383835" } },
  },
};

function replaceChart(key, canvasId, config) {
  if (state.charts[key]) state.charts[key].destroy();
  state.charts[key] = new Chart($(canvasId), config);
}

/* Centered moving average so single-iteration runs don't read as noise. */
function smooth(series, window) {
  if (window <= 1) return series;
  const half = Math.floor(window / 2);
  return series.map((_, i) => {
    const from = Math.max(0, i - half), to = Math.min(series.length - 1, i + half);
    let sum = 0;
    for (let k = from; k <= to; k++) sum += series[k];
    return sum / (to - from + 1);
  });
}

function renderCoopChart() {
  const r = state.result;
  const roundsAxis = Array.from({ length: r.config.rounds }, (_, i) => i + 1);
  // More iterations already average out randomness; smooth less as they grow.
  const window = Math.max(1, Math.round(r.config.rounds / 40 / Math.sqrt(r.config.iterations)) * 2 + 1);
  const datasets = [
    lineDataset("__overall", smooth(r.cooperation_over_time.overall, window), {
      label: "All strategies", borderColor: INK2, borderWidth: 2, borderDash: undefined,
    }),
    ...chartSeries().map((id) => lineDataset(id, smooth(r.cooperation_over_time.by_strategy[id], window))),
  ];
  replaceChart("coop", "coop-chart", {
    type: "line",
    data: { labels: roundsAxis, datasets },
    options: {
      ...BASE_LINE_OPTS,
      scales: {
        ...BASE_LINE_OPTS.scales,
        y: { ...BASE_LINE_OPTS.scales.y, min: 0, max: 1, ticks: { callback: (v) => (v * 100) + "%" } },
      },
    },
  });
  const hidden = r.config.strategies.length - chartSeries().length;
  const smoothNote = window > 1 ? `Lines are smoothed over ${window} rounds; exact values live in the exports. ` : "";
  $("coop-note").textContent = smoothNote + (hidden > 0
    ? `${hidden} more strategies not lined individually — click a ranking row to spotlight one. The ranking board carries every value.`
    : "Per-match noise flips are marked in the Replay view.");
}

function renderScoreChart() {
  const r = state.result;
  const roundsAxis = Array.from({ length: r.config.rounds }, (_, i) => i + 1);
  const datasets = chartSeries().map((id) => lineDataset(id, r.cumulative_scores_by_round[id]));
  replaceChart("score", "score-chart", {
    type: "line",
    data: { labels: roundsAxis, datasets },
    options: BASE_LINE_OPTS,
  });
  const hidden = r.config.strategies.length - chartSeries().length;
  $("score-note").textContent = hidden > 0 ? `${hidden} more strategies in the table — spotlight a row to draw its line.` : "";
}

/* Sequential single-hue ramp on the dark surface: low recedes, high glows. */
function heatColor(t) {
  const lo = [22, 39, 63], hi = [134, 182, 239]; // near-surface blue-black -> bright blue
  const c = lo.map((l, i) => Math.round(l + (hi[i] - l) * t));
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}

function renderHeatmap() {
  const r = state.result;
  const names = r.matrix.names;
  const values = r.matrix.avg_scores.flat().filter((v) => v != null);
  const min = Math.min(...values), max = Math.max(...values);
  const norm = (v) => max === min ? 0.5 : (v - min) / (max - min);

  const grid = $("heatmap");
  grid.style.gridTemplateColumns = `minmax(90px, 150px) repeat(${names.length}, minmax(34px, 1fr))`;
  let html = `<div class="hm-label"></div>` + names.map((n) => `<div class="hm-label col" title="${esc(labelOf(n))}">${esc(labelOf(n)).slice(0, 8)}</div>`).join("");
  r.matrix.avg_scores.forEach((row, i) => {
    html += `<div class="hm-label" title="${esc(labelOf(names[i]))}">${chip(names[i])}${esc(labelOf(names[i]))}</div>`;
    row.forEach((v, j) => {
      if (v == null) { html += `<div class="hm-cell empty">·</div>`; return; }
      const t = norm(v);
      const ink = t > 0.62 ? "#0b0b0b" : "#ffffff";
      html += `<div class="hm-cell" data-i="${i}" data-j="${j}" style="background:${heatColor(t)};color:${ink}"
        title="${esc(labelOf(names[i]))} scored ${v} pts/match vs ${esc(labelOf(names[j]))} — click to replay">${Math.round(v)}</div>`;
    });
  });
  grid.innerHTML = html;
  grid.querySelectorAll(".hm-cell[data-i]").forEach((cell) => cell.addEventListener("click", () => {
    const a = names[Number(cell.dataset.i)], b = names[Number(cell.dataset.j)];
    const index = state.result.matches.findIndex((m) => (m.p1 === a && m.p2 === b) || (m.p1 === b && m.p2 === a));
    if (index >= 0) { showView("replay"); openFight(index); }
  }));
  $("hm-scale").innerHTML = `<span>${num(min, 0)} pts</span>
    <div class="bar" style="background:linear-gradient(to right, ${heatColor(0)}, ${heatColor(0.5)}, ${heatColor(1)})"></div>
    <span>${num(max, 0)} pts</span><span style="margin-left:8px">avg points per match (row vs column)</span>`;
}

/* Ordinal blue steps for the three ordered phases (dark-mode legal steps). */
const PHASE_COLORS = { early: "#86b6ef", mid: "#3987e5", late: "#1c5cab" };

function renderPhaseTable() {
  const rows = sortedLeaderboard();
  const bar = (v, phase) => `
    <div class="phase-cell">
      <div class="phase-bar-track"><div class="phase-bar" style="width:${Math.min(100, v / 5 * 100)}%;background:${PHASE_COLORS[phase]}"></div></div>
      <span class="phase-val">${num(v, 2)}</span>
    </div>`;
  $("phase-table").innerHTML = `
    <div class="phase-row" style="border-bottom-color:#383835">
      <span></span>
      <span style="color:${MUTED};font-size:11px;text-transform:uppercase;letter-spacing:.5px">Early</span>
      <span style="color:${MUTED};font-size:11px;text-transform:uppercase;letter-spacing:.5px">Mid</span>
      <span style="color:${MUTED};font-size:11px;text-transform:uppercase;letter-spacing:.5px">Late</span>
    </div>
    ${rows.map((row) => `<div class="phase-row">
      <span class="phase-name">${chip(row.strategy)}${esc(labelOf(row.strategy))}</span>
      ${bar(row.early_avg, "early")}${bar(row.mid_avg, "mid")}${bar(row.late_avg, "late")}
    </div>`).join("")}
    <div class="chart-note">Bars are average points per round (max 5) in each third of the match.</div>`;
}

/* ================= Replay ================= */
function prepareReplay() {
  const r = state.result;
  state.replay.matches = r.matches.map((m) => {
    const moves1 = [...m.moves_p1].map((c) => c === "C");
    const moves2 = [...m.moves_p2].map((c) => c === "C");
    const noiseSet = new Set(m.noise_events.map(([round, player]) => `${round}:${player}`));
    const cum1 = [], cum2 = [];
    let a = 0, b = 0;
    for (let i = 0; i < moves1.length; i++) {
      const [s1, s2] = payoffOf(moves1[i], moves2[i]);
      a += s1; b += s2;
      cum1.push(a); cum2.push(b);
    }
    return { ...m, moves1, moves2, noiseSet, cum1, cum2, feed: buildFeed(m, moves1, moves2, noiseSet) };
  });
  stopFfa();
  state.replay.ffaRound = r.config.rounds;
  $("ffa-scrubber").max = r.config.rounds;
  $("ffa-scrubber").value = r.config.rounds;
}

function renderReplayList() {
  if (!state.result) return;
  $("replay-empty").style.display = "none";
  $("replay-content").style.display = "";
  $("fight-panel").style.display = "none";
  $("ffa-panel").style.display = "";
  $("match-grid").innerHTML = state.replay.matches.map((m, i) => `
    <div class="match-card" data-mi="${i}">
      <div class="vs"><span>${chip(m.p1)}${esc(labelOf(m.p1))}</span><span style="color:${MUTED}">vs</span><span>${esc(labelOf(m.p2))}${chip(m.p2)}</span></div>
      <div class="mini-meter">
        <div class="m1" data-role="m1" style="width:50%;background:${colorOf(m.p1)}"></div>
        <div class="m2" data-role="m2" style="flex:1;background:${colorOf(m.p2)}"></div>
      </div>
      <div class="score-line"><span data-role="s1">0</span><span data-role="s2">0</span></div>
    </div>`).join("");
  $("match-grid").querySelectorAll(".match-card").forEach((card) =>
    card.addEventListener("click", () => openFight(Number(card.dataset.mi))));
  updateFfa(state.replay.ffaRound);
}

function updateFfa(round) {
  state.replay.ffaRound = round;
  $("ffa-scrubber").value = round;
  $("ffa-round").textContent = round === 0 ? "start" : `round ${round}/${state.result.config.rounds}`;
  document.querySelectorAll("#match-grid .match-card").forEach((card) => {
    const m = state.replay.matches[Number(card.dataset.mi)];
    const idx = round - 1;
    const a = idx < 0 ? 0 : m.cum1[Math.min(idx, m.cum1.length - 1)];
    const b = idx < 0 ? 0 : m.cum2[Math.min(idx, m.cum2.length - 1)];
    const total = a + b || 1;
    card.querySelector('[data-role="m1"]').style.width = `${(a / total) * 100}%`;
    card.querySelector('[data-role="s1"]').textContent = a;
    card.querySelector('[data-role="s2"]').textContent = b;
  });
}

$("ffa-scrubber").addEventListener("input", (e) => { stopFfa(); updateFfa(Number(e.target.value)); });
$("ffa-play").addEventListener("click", () => {
  if (state.replay.ffaTimer) { stopFfa(); return; }
  if (state.replay.ffaRound >= state.result.config.rounds) state.replay.ffaRound = 0;
  $("ffa-play").textContent = "⏸ Pause";
  state.replay.ffaTimer = setInterval(() => {
    const next = state.replay.ffaRound + Math.max(1, Math.round(state.result.config.rounds / 300));
    if (next >= state.result.config.rounds) { updateFfa(state.result.config.rounds); stopFfa(); return; }
    updateFfa(next);
  }, 33);
});
function stopFfa() {
  if (state.replay.ffaTimer) clearInterval(state.replay.ffaTimer);
  state.replay.ffaTimer = null;
  $("ffa-play").textContent = "▶ Play all";
}

/* ---- Fight feed: commentary events precomputed per round ---- */
function buildFeed(m, moves1, moves2, noiseSet) {
  const feed = [];
  const n1 = labelOf(m.p1), n2 = labelOf(m.p2);
  let coopStreak = 0, defectStreak = 0;
  for (let i = 0; i < moves1.length; i++) {
    const c1 = moves1[i], c2 = moves2[i];
    if (noiseSet.has(`${i}:0`)) feed.push({ r: i, cls: "noise", text: `⚡ Noise! ${n1}'s move got flipped by a misunderstanding.` });
    if (noiseSet.has(`${i}:1`)) feed.push({ r: i, cls: "noise", text: `⚡ Noise! ${n2}'s move got flipped by a misunderstanding.` });

    if (c1 && c2) {
      if (defectStreak >= 3) feed.push({ r: i, cls: "peace", text: `🕊 Ceasefire — both sides cooperate after ${defectStreak} rounds of war.` });
      defectStreak = 0; coopStreak++;
      if (coopStreak > 0 && coopStreak % 10 === 0) feed.push({ r: i, cls: "combo", text: `COOP COMBO ×${coopStreak} — the alliance holds.` });
    } else if (!c1 && !c2) {
      if (coopStreak >= 3) feed.push({ r: i, cls: "betrayal", text: `💥 Total breakdown — both defect after ${coopStreak} peaceful rounds.` });
      coopStreak = 0; defectStreak++;
      if (defectStreak % 10 === 0) feed.push({ r: i, cls: "betrayal", text: `DEFECTION SPIRAL ×${defectStreak} — nobody blinks.` });
    } else {
      const attacker = c2 ? n1 : n2;
      const victim = c2 ? n2 : n1;
      if (coopStreak >= 3) feed.push({ r: i, cls: "betrayal", text: `🗡 ${attacker} breaks the truce and stabs ${victim}!` });
      else if (i > 0 && ((c2 && !moves1[i - 1] && moves2[i - 1]) || (c1 && !moves2[i - 1] && moves1[i - 1]))) {
        // attacker exploited again while the other cooperated
        feed.push({ r: i, cls: "betrayal", text: `${attacker} keeps hammering ${victim}'s open hand.` });
      } else if (i > 0 && !moves2[i - 1] && !c1 && c2) {
        feed.push({ r: i, cls: "", text: `${n1} strikes back.` });
      } else if (i > 0 && !moves1[i - 1] && !c2 && c1) {
        feed.push({ r: i, cls: "", text: `${n2} strikes back.` });
      }
      coopStreak = 0; defectStreak = 0;
    }
    if (i > 0 && !moves1[i - 1] && !moves2[i - 1] && (c1 !== c2)) {
      feed.push({ r: i, cls: "peace", text: `${c1 ? n1 : n2} offers an olive branch.` });
    }
  }
  feed.push({ r: 0, cls: "", text: "🔔 The match begins." });
  return feed.sort((a, b) => a.r - b.r);
}

const STRIP_MAX_TICKS = 400;

function openFight(index) {
  stopFightPlayback();
  const m = state.replay.matches[index];
  state.replay.fight = { index, round: 1, timer: null };
  $("ffa-panel").style.display = "none";
  $("fight-panel").style.display = "";
  $("f1-name").innerHTML = `${chip(m.p1)}${esc(labelOf(m.p1))}`;
  $("f2-name").innerHTML = `${chip(m.p2)}${esc(labelOf(m.p2))}`;
  $("f1-health").style.background = colorOf(m.p1);
  $("f2-health").style.background = colorOf(m.p2);
  $("fight-narrative").textContent = m.narrative;
  $("fight-scrubber").max = m.moves1.length;
  $("strip1-label").textContent = labelOf(m.p1);
  $("strip2-label").textContent = labelOf(m.p2);
  buildStrip("strip1", m.moves1, m.noiseSet, 0);
  buildStrip("strip2", m.moves2, m.noiseSet, 1);
  $("fight-phases").innerHTML = phaseMiniTable(m);
  setFightRound(m.moves1.length); // land on the finished state; scrub to explore
}

function phaseMiniTable(m) {
  const rows = ["early", "mid", "late"].map((phase) => {
    const p = m.phases[phase];
    return `<tr><td class="left" style="text-transform:capitalize">${phase} <span style="color:${MUTED}">(${p.round_count}r)</span></td>
      <td>${p.p1_score}</td><td>${p.p2_score}</td><td>${pct(p.p1_coop_rate)}</td><td>${pct(p.p2_coop_rate)}</td></tr>`;
  }).join("");
  return `<div class="table-scroll"><table>
    <thead><tr><th class="left">Phase</th><th data-tip="Points scored by ${esc(labelOf(m.p1))} in this phase.">${esc(labelOf(m.p1)).slice(0, 12)} pts</th>
    <th data-tip="Points scored by ${esc(labelOf(m.p2))} in this phase.">${esc(labelOf(m.p2)).slice(0, 12)} pts</th>
    <th>Coop % (P1)</th><th>Coop % (P2)</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}

function buildStrip(elId, moves, noiseSet, playerIdx) {
  const el = $(elId);
  const n = moves.length;
  const bucket = Math.max(1, Math.ceil(n / STRIP_MAX_TICKS));
  let html = "";
  for (let start = 0; start < n; start += bucket) {
    const slice = moves.slice(start, start + bucket);
    const coops = slice.filter(Boolean).length;
    let hasNoise = false;
    for (let k = start; k < Math.min(start + bucket, n); k++) if (noiseSet.has(`${k}:${playerIdx}`)) { hasNoise = true; break; }
    html += `<div class="mv ${coops * 2 >= slice.length ? "c" : "d"}${hasNoise ? " noise" : ""}" data-start="${start}"></div>`;
  }
  el.innerHTML = html;
}

function setFightRound(round) {
  const fight = state.replay.fight;
  if (!fight) return;
  const m = state.replay.matches[fight.index];
  const total = m.moves1.length;
  round = Math.max(1, Math.min(total, round));
  fight.round = round;
  const idx = round - 1;

  $("fight-scrubber").value = round;
  $("fight-round").textContent = `Round ${round}/${total}`;

  const a = m.cum1[idx], b = m.cum2[idx];
  $("f1-score").textContent = a;
  $("f2-score").textContent = b;
  const sum = a + b || 1;
  $("f1-health").style.width = `${(a / sum) * 100}%`;
  $("f2-health").style.width = `${(b / sum) * 100}%`;

  // Phase chip
  const { early_end, mid_end } = state.result.config.phase_bounds;
  const phase = idx < early_end ? "early" : idx < mid_end ? "mid" : "late";
  const chipEl = $("fight-phase");
  chipEl.textContent = phase.toUpperCase();
  chipEl.className = `phase-chip ${phase}`;

  // Combo counters
  setCombo("f1-combo", m.moves1, idx);
  setCombo("f2-combo", m.moves2, idx);

  // Strips: dim future ticks
  for (const [stripId] of [["strip1"], ["strip2"]]) {
    $(stripId).querySelectorAll(".mv").forEach((tick) => {
      tick.classList.toggle("future", Number(tick.dataset.start) > idx);
    });
  }

  // Feed: entries up to current round, newest first (column-reverse container)
  const entries = m.feed.filter((f) => f.r <= idx).slice(-40);
  $("fight-feed").innerHTML = entries.map((f) =>
    `<div class="feed-entry ${f.cls}"><span class="rn">R${f.r + 1}</span>${esc(f.text)}</div>`).join("");
}

function setCombo(elId, moves, idx) {
  let streak = 1;
  for (let i = idx; i > 0 && moves[i - 1] === moves[idx]; i--) streak++;
  const el = $(elId);
  if (moves[idx]) { el.className = "f-combo coop"; el.textContent = streak >= 3 ? `COOP COMBO ×${streak}` : "cooperating"; }
  else { el.className = "f-combo defect"; el.textContent = streak >= 3 ? `DEFECT STREAK ×${streak}` : "defecting"; }
}

$("fight-scrubber").addEventListener("input", (e) => { stopFightPlayback(); setFightRound(Number(e.target.value)); });
$("fight-play").addEventListener("click", () => {
  const fight = state.replay.fight;
  if (!fight) return;
  if (fight.timer) { stopFightPlayback(); return; }
  const m = state.replay.matches[fight.index];
  if (fight.round >= m.moves1.length) fight.round = 0;
  $("fight-play").textContent = "⏸ Pause";
  fight.timer = setInterval(() => {
    if (fight.round >= m.moves1.length) { stopFightPlayback(); return; }
    setFightRound(fight.round + 1);
  }, Number($("fight-speed").value));
});
$("fight-speed").addEventListener("change", () => {
  const fight = state.replay.fight;
  if (fight && fight.timer) { stopFightPlayback(); $("fight-play").click(); }
});
function stopFightPlayback() {
  const fight = state.replay.fight;
  if (fight && fight.timer) clearInterval(fight.timer);
  if (fight) fight.timer = null;
  $("fight-play").textContent = "▶ Play";
}
$("btn-back-ffa").addEventListener("click", () => {
  stopFightPlayback();
  $("fight-panel").style.display = "none";
  $("ffa-panel").style.display = "";
});

/* ================= Encyclopedia ================= */
function renderEncyclopedia() {
  const order = ["Cooperative / Reciprocal", "Retaliatory", "Adaptive", "Exploitative", "Statistical / Probabilistic", "Experimental / Complex"];
  const sorted = [...state.meta].sort((a, b) => order.indexOf(a.category) - order.indexOf(b.category) || a.number - b.number);
  $("ency-grid").innerHTML = sorted.map((s) => `
    <div class="ency-card">
      <div style="display:flex; justify-content:space-between; align-items:center; gap:8px">
        <h3 style="margin:0">${esc(s.short_name)}</h3>
        <span class="tag ${CATEGORY_CLASS[s.category] || "complex"}">${esc(s.category_short)}</span>
      </div>
      <div class="desc">${esc(s.description)}</div>
      <div class="ency-detail" data-role="detail">
        <div class="ency-detail-inner"><p>${esc(s.details || s.description)}</p></div>
      </div>
      <div class="strip-label" style="display:none" data-role="demo-label"></div>
      <div class="movestrip" data-role="demo1" style="margin-bottom:2px"></div>
      <div class="movestrip" data-role="demo2"></div>
      <div class="ency-actions">
        <button class="small ghost ency-more" data-more aria-expanded="false">How it works <span class="chev">▾</span></button>
        <button class="small" data-demo="${esc(s.id)}">▶ Demo vs Tit For Tat</button>
      </div>
    </div>`).join("");

  $("ency-grid").addEventListener("click", async (e) => {
    const more = e.target.closest("[data-more]");
    if (more) {
      const card = more.closest(".ency-card");
      const open = card.classList.toggle("open");
      more.setAttribute("aria-expanded", String(open));
      more.innerHTML = open ? 'Hide details <span class="chev">▴</span>' : 'How it works <span class="chev">▾</span>';
      return;
    }
    const btn = e.target.closest("[data-demo]");
    if (!btn) return;
    btn.disabled = true;
    try {
      const demo = await api("GET", `/strategies/demo?id=${encodeURIComponent(btn.dataset.demo)}`);
      const card = btn.closest(".ency-card");
      const label = card.querySelector('[data-role="demo-label"]');
      label.style.display = "";
      label.textContent = `${demo.label} (top) vs Tit For Tat — green = cooperate, red = defect`;
      animateDemo(card.querySelector('[data-role="demo1"]'), demo.moves);
      animateDemo(card.querySelector('[data-role="demo2"]'), demo.opponent_moves);
    } catch (err) { console.error(err); }
    btn.disabled = false;
  });
}

function animateDemo(el, moves) {
  el.innerHTML = [...moves].map((c) => `<div class="mv ${c === "C" ? "c" : "d"} future"></div>`).join("");
  const ticks = [...el.children];
  let i = 0;
  const timer = setInterval(() => {
    if (i >= ticks.length) { clearInterval(timer); return; }
    ticks[i++].classList.remove("future");
  }, 90);
}

/* ================= Builder ================= */
const FACTS = {
  opp_last_move: { label: "opponent's last move", kind: "move" },
  my_last_move: { label: "my last move", kind: "move" },
  opp_move_n_back: { label: "opponent's move N rounds back", kind: "move", n: true },
  my_move_n_back: { label: "my move N rounds back", kind: "move", n: true },
  round_number: { label: "round number", kind: "number", hint: "1, 2, 3…" },
  opp_defection_count: { label: "opponent's total defections", kind: "number" },
  opp_defection_rate: { label: "opponent's defection rate (0–1)", kind: "number" },
  opp_cooperation_rate: { label: "opponent's cooperation rate (0–1)", kind: "number" },
  opp_coop_streak: { label: "opponent's cooperation streak", kind: "number" },
  opp_defect_streak: { label: "opponent's defection streak", kind: "number" },
  mutual_coop_streak: { label: "mutual cooperation streak", kind: "number" },
  my_score: { label: "my score", kind: "number" },
  opp_score: { label: "opponent's score", kind: "number" },
  score_diff: { label: "my score minus theirs", kind: "number" },
  chance: { label: "random chance (0–1)", kind: "chance" },
};
const OPS = { gte: "≥", gt: ">", eq: "=", lt: "<", lte: "≤" };
const ACTION_LABELS = {
  cooperate: "Cooperate", defect: "Defect", copy_opponent: "Copy opponent's last move",
  opposite_of_opponent: "Do the opposite of opponent", random: "Cooperate with probability p",
};

const TEMPLATES = {
  blank: { first_move: "cooperate", rules: [], default_action: { type: "cooperate" } },
  tft: {
    first_move: "cooperate",
    rules: [{ conditions: [{ fact: "opp_last_move", op: "is", value: "defect" }], action: { type: "defect" } }],
    default_action: { type: "cooperate" },
  },
  grim: {
    first_move: "cooperate",
    rules: [{ conditions: [{ fact: "opp_defection_count", op: "gte", value: 1 }], action: { type: "defect" } }],
    default_action: { type: "cooperate" },
  },
  sneaky: {
    first_move: "cooperate",
    rules: [
      { conditions: [{ fact: "opp_last_move", op: "is", value: "defect" }], action: { type: "defect" } },
      { conditions: [{ fact: "chance", op: "lt", value: 0.1 }], action: { type: "defect" } },
    ],
    default_action: { type: "cooperate" },
  },
  forgiving: {
    first_move: "cooperate",
    rules: [
      { conditions: [{ fact: "opp_defect_streak", op: "gte", value: 2 }], action: { type: "defect" } },
      { conditions: [{ fact: "opp_last_move", op: "is", value: "defect" }], action: { type: "random", p: 0.2 } },
    ],
    default_action: { type: "cooperate" },
  },
};

function initBuilder() {
  state.builder = structuredClone(TEMPLATES.tft);
  renderBuilder();
  scheduleCompile();
  refreshMine().catch(() => {});
}

$("builder-load-template").onclick = () => {
  state.builder = structuredClone(TEMPLATES[$("builder-template").value] || TEMPLATES.blank);
  state.editingId = null;
  $("builder-name").value = "";
  $("builder-desc").value = "";
  renderBuilder();
  scheduleCompile();
};

function actionSelect(action, onchange) {
  const sel = document.createElement("select");
  sel.innerHTML = Object.entries(ACTION_LABELS).map(([v, l]) => `<option value="${v}" ${action.type === v ? "selected" : ""}>${l}</option>`).join("");
  const p = document.createElement("input");
  p.type = "number"; p.min = 0; p.max = 1; p.step = 0.05; p.value = action.p ?? 0.5;
  p.style.width = "70px";
  p.style.display = action.type === "random" ? "" : "none";
  sel.onchange = () => { action.type = sel.value; if (sel.value === "random") { action.p = Number(p.value); p.style.display = ""; } else { delete action.p; p.style.display = "none"; } onchange(); };
  p.oninput = () => { action.p = Number(p.value); onchange(); };
  const frag = document.createDocumentFragment();
  frag.append(sel, p);
  return frag;
}

function renderBuilder() {
  const b = state.builder;
  $("builder-first-move").value = b.first_move;
  $("builder-first-move").onchange = () => { b.first_move = $("builder-first-move").value; scheduleCompile(); };

  const rulesEl = $("builder-rules");
  rulesEl.innerHTML = "";
  b.rules.forEach((rule, ri) => {
    const card = document.createElement("div");
    card.className = "rule-card";
    const head = document.createElement("div");
    head.className = "rule-head";
    head.innerHTML = `<span class="rule-no">RULE ${ri + 1}</span>`;
    const controls = document.createElement("div");
    for (const [label, fn] of [["↑", () => moveRule(ri, -1)], ["↓", () => moveRule(ri, 1)], ["✕", () => { b.rules.splice(ri, 1); renderBuilder(); scheduleCompile(); }]]) {
      const btn = document.createElement("button");
      btn.className = "small ghost"; btn.textContent = label; btn.onclick = fn;
      controls.appendChild(btn);
    }
    head.appendChild(controls);
    card.appendChild(head);

    rule.conditions.forEach((cond, ci) => {
      card.appendChild(conditionRow(rule, cond, ci));
    });

    const addCond = document.createElement("button");
    addCond.className = "small ghost";
    addCond.textContent = "+ AND condition";
    addCond.onclick = () => { rule.conditions.push({ fact: "opp_last_move", op: "is", value: "defect" }); renderBuilder(); scheduleCompile(); };
    card.appendChild(addCond);

    const thenRow = document.createElement("div");
    thenRow.className = "then-row";
    const kw = document.createElement("span");
    kw.className = "kw"; kw.textContent = "THEN";
    thenRow.appendChild(kw);
    thenRow.appendChild(actionSelect(rule.action, scheduleCompile));
    card.appendChild(thenRow);
    rulesEl.appendChild(card);
  });

  // Default action row
  const defSel = $("builder-default-action");
  defSel.innerHTML = Object.entries(ACTION_LABELS).map(([v, l]) => `<option value="${v}" ${b.default_action.type === v ? "selected" : ""}>${l}</option>`).join("");
  const defP = $("builder-default-p");
  defP.style.display = b.default_action.type === "random" ? "" : "none";
  defP.value = b.default_action.p ?? 0.5;
  defSel.onchange = () => {
    b.default_action = defSel.value === "random" ? { type: "random", p: Number(defP.value) } : { type: defSel.value };
    defP.style.display = defSel.value === "random" ? "" : "none";
    scheduleCompile();
  };
  defP.oninput = () => { b.default_action.p = Number(defP.value); scheduleCompile(); };
}

function moveRule(index, delta) {
  const rules = state.builder.rules;
  const target = index + delta;
  if (target < 0 || target >= rules.length) return;
  [rules[index], rules[target]] = [rules[target], rules[index]];
  renderBuilder();
  scheduleCompile();
}

function conditionRow(rule, cond, ci) {
  const row = document.createElement("div");
  row.className = "cond-row";
  const kw = document.createElement("span");
  kw.className = "kw";
  kw.textContent = ci === 0 ? "IF" : "AND";
  row.appendChild(kw);

  const factSel = document.createElement("select");
  factSel.innerHTML = Object.entries(FACTS).map(([v, f]) => `<option value="${v}" ${cond.fact === v ? "selected" : ""}>${f.label}</option>`).join("");
  row.appendChild(factSel);

  const nIn = document.createElement("input");
  nIn.type = "number"; nIn.min = 1; nIn.max = 10; nIn.value = cond.n ?? 1; nIn.style.width = "58px";
  nIn.title = "N rounds back";

  const opSel = document.createElement("select");
  const valMove = document.createElement("select");
  valMove.innerHTML = `<option value="cooperate">was cooperate</option><option value="defect">was defect</option>`;
  const valNum = document.createElement("input");
  valNum.type = "number"; valNum.step = "any"; valNum.style.width = "80px";

  function syncKind() {
    const kind = FACTS[cond.fact].kind;
    nIn.style.display = FACTS[cond.fact].n ? "" : "none";
    opSel.style.display = kind === "number" ? "" : "none";
    valMove.style.display = kind === "move" ? "" : "none";
    valNum.style.display = kind !== "move" ? "" : "none";
    if (kind === "move") {
      cond.op = "is";
      if (cond.value !== "cooperate" && cond.value !== "defect") cond.value = "defect";
      valMove.value = cond.value;
      if (FACTS[cond.fact].n) cond.n = Number(nIn.value) || 1; else delete cond.n;
    } else if (kind === "chance") {
      cond.op = "lt";
      if (typeof cond.value !== "number") cond.value = 0.1;
      valNum.value = cond.value;
      delete cond.n;
    } else {
      if (!(cond.op in OPS)) cond.op = "gte";
      if (typeof cond.value !== "number") cond.value = 1;
      opSel.innerHTML = Object.entries(OPS).map(([v, l]) => `<option value="${v}" ${cond.op === v ? "selected" : ""}>${l}</option>`).join("");
      valNum.value = cond.value;
      delete cond.n;
    }
  }

  factSel.onchange = () => { cond.fact = factSel.value; syncKind(); scheduleCompile(); };
  nIn.oninput = () => { cond.n = Number(nIn.value) || 1; scheduleCompile(); };
  opSel.onchange = () => { cond.op = opSel.value; scheduleCompile(); };
  valMove.onchange = () => { cond.value = valMove.value; scheduleCompile(); };
  valNum.oninput = () => { cond.value = Number(valNum.value); scheduleCompile(); };

  row.append(nIn, opSel, valMove, valNum);
  syncKind();

  const del = document.createElement("button");
  del.className = "small ghost"; del.textContent = "✕";
  del.onclick = () => {
    if (rule.conditions.length <= 1) return;
    rule.conditions.splice(ci, 1);
    renderBuilder(); scheduleCompile();
  };
  row.appendChild(del);
  return row;
}

$("builder-add-rule").onclick = () => {
  if (state.builder.rules.length >= 20) return;
  state.builder.rules.push({ conditions: [{ fact: "opp_last_move", op: "is", value: "defect" }], action: { type: "defect" } });
  renderBuilder();
  scheduleCompile();
};

let compileTimer = null;
function scheduleCompile() {
  clearTimeout(compileTimer);
  compileTimer = setTimeout(compileNow, 350);
}

async function compileNow() {
  try {
    const resp = await fetch("/builder/compile", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ definition: state.builder }),
    });
    const data = await resp.json();
    if (!data.valid) {
      $("builder-error").style.display = "";
      $("builder-error").textContent = data.error || "Invalid strategy.";
      return;
    }
    $("builder-error").style.display = "none";
    $("builder-desc-lines").innerHTML = data.description_lines.map((line) => `<div>${esc(line)}</div>`).join("");
    $("builder-python").textContent = data.python_source;
  } catch (err) {
    $("builder-error").style.display = "";
    $("builder-error").textContent = err.message;
  }
}

$("builder-test").onclick = async () => {
  const status = $("builder-status");
  status.textContent = "Testing…";
  try {
    const data = await api("POST", "/builder/test", { definition: state.builder, rounds: 100 });
    $("sandbox-card").style.display = "";
    $("sandbox-results").innerHTML = data.matches.map((m) => `
      <div class="sb-row">
        <span>${esc(m.opponent)}</span>
        <span class="sb-outcome ${m.outcome}">${m.outcome.toUpperCase()} ${m.my_score}–${m.opponent_score}</span>
        <div>
          <div class="movestrip">${[...m.my_moves].map((c) => `<div class="mv ${c === "C" ? "c" : "d"}"></div>`).join("")}</div>
        </div>
      </div>`).join("") +
      `<div class="chart-note">Your moves over the first ${Math.min(60, data.rounds)} rounds of each ${data.rounds}-round match. Total: ${data.total_score} pts.</div>`;
    status.textContent = "";
  } catch (err) {
    status.textContent = err.message;
  }
};

$("builder-save").onclick = async () => {
  const status = $("builder-status");
  const name = $("builder-name").value.trim();
  if (!name) { status.textContent = "Give it a name first."; return; }
  status.textContent = "Saving…";
  try {
    const body = { name, description: $("builder-desc").value.trim(), definition: state.builder };
    if (state.editingId) {
      await api("PUT", `/custom-strategies/${state.editingId}`, body, true);
    } else {
      await api("POST", "/custom-strategies", body, true);
    }
    status.textContent = state.editingId ? "Updated." : "Saved — it now appears in the Arena roster.";
    state.editingId = null;
    await refreshMine();
  } catch (err) {
    status.textContent = err.message;
  }
};

async function refreshMine() {
  if (!localStorage.getItem("arena_token")) { renderMine(); return; }
  const data = await api("GET", "/custom-strategies", null, true);
  state.mine = data.strategies;
  renderMine();
  renderRoster();
}

function renderMine() {
  const el = $("mine-list");
  if (!state.mine.length) { el.innerHTML = `<div class="empty-note">Nothing saved yet.</div>`; return; }
  el.innerHTML = state.mine.map((s) => `
    <div class="mine-row" data-id="${esc(s.id)}">
      <span class="m-name">${esc(s.name)} ${s.published ? '<span class="m-pub">PUBLISHED</span>' : ""}${s.forked_from ? ` <span style="color:${MUTED};font-size:11px">fork</span>` : ""}</span>
      <button class="small" data-act="edit">Edit</button>
      <button class="small" data-act="publish">${s.published ? "Unpublish" : "Publish"}</button>
      <button class="small danger-ghost" data-act="delete">Delete</button>
    </div>`).join("");
  el.querySelectorAll("[data-act]").forEach((btn) => btn.addEventListener("click", async () => {
    const id = btn.closest(".mine-row").dataset.id;
    const record = state.mine.find((s) => s.id === id);
    try {
      if (btn.dataset.act === "edit") {
        state.builder = structuredClone(record.definition);
        state.editingId = id;
        $("builder-name").value = record.name;
        $("builder-desc").value = record.description || "";
        renderBuilder();
        scheduleCompile();
        window.scrollTo({ top: 0, behavior: "smooth" });
      } else if (btn.dataset.act === "publish") {
        await api("POST", `/custom-strategies/${id}/publish`, { published: !record.published }, true);
        await refreshMine();
      } else if (btn.dataset.act === "delete") {
        if (!confirm(`Delete "${record.name}"?`)) return;
        await api("DELETE", `/custom-strategies/${id}`, null, true);
        state.selected.delete(id);
        await refreshMine();
      }
    } catch (err) { $("builder-status").textContent = err.message; }
  }));
}

/* ================= Marketplace ================= */
async function loadMarketplace() {
  const grid = $("market-grid");
  grid.innerHTML = `<div class="empty-note">Loading…</div>`;
  try {
    const data = await api("GET", "/marketplace");
    if (!data.strategies.length) {
      grid.innerHTML = `<div class="empty-note">Nothing published yet. Build a strategy and hit Publish to be the first.</div>`;
      return;
    }
    grid.innerHTML = data.strategies.map((s) => `
      <div class="market-card">
        <div style="display:flex; justify-content:space-between; align-items:center">
          <h3 style="margin:0">${esc(s.name)}</h3>
          <span class="tag custom">by anon-${esc(s.author)}</span>
        </div>
        ${s.description ? `<div style="color:${INK2}; font-size:13px">${esc(s.description)}</div>` : ""}
        <div class="desc-lines">${s.description_lines.map((line) => `<div>${esc(line)}</div>`).join("")}</div>
        <details><summary>Compiled Python</summary><pre>${esc(s.python_source)}</pre></details>
        <div style="display:flex; gap:8px; align-items:center">
          <button class="small primary" data-fork="${esc(s.id)}">Fork to my workspace</button>
          <span class="m-meta">${new Date(s.created_at * 1000).toLocaleDateString()}</span>
        </div>
      </div>`).join("");
    grid.querySelectorAll("[data-fork]").forEach((btn) => btn.addEventListener("click", async () => {
      btn.disabled = true;
      btn.textContent = "Forking…";
      try {
        await api("POST", `/marketplace/${btn.dataset.fork}/fork`, {}, true);
        btn.textContent = "Forked ✓ — see Builder";
        await refreshMine();
      } catch (err) {
        btn.textContent = err.message;
      }
    }));
  } catch (err) {
    grid.innerHTML = `<div class="empty-note">${esc(err.message)}</div>`;
  }
}

/* ================= Boot ================= */
updateSessionHint();
loadMeta().catch((err) => { $("run-status").className = "status-line error"; $("run-status").textContent = "Failed to load strategies: " + err.message; });
initBuilder();
