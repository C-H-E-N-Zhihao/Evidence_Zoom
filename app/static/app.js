const $ = (id) => document.getElementById(id);
const img = $("img"), canvas = $("overlay"), ctx = canvas.getContext("2d");
const ROWS = 8, COLS = 6;  // must match pipeline.visual default grid
let cfg = { pairs: [], replay: false };
let image = null;           // {image_id, width, height, url, fixture}
let answers = [];           // [{result, baseline, source, views}]
let active = -1;
let totals = { ours: 0, cached: 0, full: 0 };
let pair = null, side = "a";
const sessions = {};        // fixture id -> {image, answers, totals, active, chat (DOM nodes)}
const pairAnswers = {};     // pair_id -> question -> {a: answer, b: answer}

const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const usd = (x) => `$${x.toFixed(x < 0.01 ? 4 : 3)}`;
const SOURCE = {
  ocr: ["LIVE OCR", "Answered on this machine by Apple Vision OCR. $0, no model call."],
  replay: ["REPLAY", "Visual route replayed from fixture labels to show the mechanism. Not a model answer; tokens and cost are estimates of what a model call would use."],
  model: ["MODEL", "Answered by a vision model call."],
  mock: ["MOCK", "Fake answer from the mock pipeline."],
  unavailable: ["NO ANSWER", "A pipeline stage was unavailable (e.g. no fixture replay or no API key); nothing was invented."],
};

async function init() {
  cfg = await (await fetch("/api/config")).json();
  $("pipeline").textContent = `pipeline: ${cfg.pipeline}`;
  if (cfg.replay) {
    $("banner").hidden = false;
    $("banner").innerHTML = "<b>Key-free rehearsal.</b> <span class='src ocr'>LIVE OCR</span> answers are real " +
      "(local OCR, $0). <span class='src replay'>REPLAY</span> answers replay the fixture's gold labels through the real " +
      "overview → zoom → mapping code, to show <i>which pixels</i> a model would inspect. They are not model output, and their costs are estimates.";
  }
  for (const p of cfg.pairs) {
    const o = document.createElement("option");
    o.value = p.pair_id;
    const what = (p.forms.find((f) => f.note && f.note.includes("counterfactual")) || {}).note || "";
    const diff = what.includes("tick") ? "B's ticks differ" : what.includes("sketch") ? "the sketch differs" : "";
    o.textContent = p.pair_id === "demo" ? "demo form" : `${p.pair_id}${diff ? " · pair: " + diff : ""}`;
    $("pair").append(o);
  }
}

async function loadImage(resp) {
  const data = await resp.json();
  if (!resp.ok) { alert(data.detail || "load failed"); return; }
  image = data;
  img.src = image.url;
  img.style.display = "block";
  $("empty").style.display = "none";
  $("q").disabled = $("send").disabled = false;
  answers = []; active = -1; totals = { ours: 0, cached: 0, full: 0 };
  $("chat").innerHTML = "";
  updateMeter();
  setSuggestions();
}

function currentForm() {
  if (!pair) return null;
  return pair.forms.find((f) => f.fixture.endsWith(side)) || pair.forms[0];
}

function saveSession() {
  if (!image || !image.fixture) return;
  sessions[image.fixture] = { image, answers, totals, active, chat: [...$("chat").childNodes] };
}

async function loadFixture() {
  const f = currentForm(); if (!f) return;
  saveSession();
  const saved = sessions[f.fixture];
  if (saved) {  // restore this form's conversation instead of starting over
    ({ image, answers, totals, active } = saved);
    img.src = image.url;
    $("chat").replaceChildren(...saved.chat);
    updateMeter(); setSuggestions(); showPairSummary(); draw();
    return;
  }
  await loadImage(await fetch(`/api/images/fixture/${f.fixture}`, { method: "POST" }));
  showPairSummary();
}

function showPairSummary() {
  const note = $("formnote");
  if (!pair || pair.forms.length < 2) { note.hidden = true; return; }
  const rows = Object.entries(pairAnswers[pair.pair_id] || {})
    .filter(([, v]) => "a" in v && "b" in v)
    .map(([q, v]) => `${q.replace(/ Answer .*$/, "")}  a: ${v.a ?? "—"} · b: ${v.b ?? "—"}`);
  note.hidden = false;
  note.textContent = `Showing form ${side} of pair ${pair.pair_id}. ` +
    (rows.length ? rows.join("  |  ") : "Ask the same question on form a and form b to compare.");
}

$("pair").onchange = () => {
  saveSession();
  pair = cfg.pairs.find((p) => p.pair_id === $("pair").value) || null;
  side = "a";
  $("ab").hidden = !pair || pair.forms.length < 2;
  document.querySelectorAll("#ab button").forEach((b) => b.classList.toggle("on", b.dataset.k === side));
  loadFixture();
};
document.querySelectorAll("#ab button").forEach((b) => b.onclick = () => {
  side = b.dataset.k;
  document.querySelectorAll("#ab button").forEach((x) => x.classList.toggle("on", x === b));
  loadFixture();
});
$("file").onchange = async (e) => {
  const f = e.target.files[0]; if (!f) return;
  saveSession();
  pair = null; $("pair").value = ""; $("ab").hidden = true; $("formnote").hidden = true;
  const fd = new FormData(); fd.append("file", f);
  loadImage(await fetch("/api/images", { method: "POST", body: fd }));
};
$("showGrid").onchange = draw;
img.onload = draw;
window.onresize = draw;

function setSuggestions() {
  const box = $("suggest"); box.innerHTML = "";
  const f = currentForm();
  const qs = f ? f.questions : [];
  for (const q of qs) {
    const b = document.createElement("button"); b.type = "button"; b.textContent = q;
    b.onclick = () => { $("q").value = q; $("ask").requestSubmit(); };
    box.append(b);
  }
}

$("ask").onsubmit = async (e) => {
  e.preventDefault();
  const q = $("q").value.trim(); if (!q || !image) return;
  $("q").value = ""; $("send").disabled = true;
  addQ(q);
  try {
    const r = await fetch("/api/ask", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image_id: image.image_id, question: q }) });
    const data = await r.json();
    if (!r.ok) throw new Error(data.detail || r.status);
    answers.push(data);
    const ours = data.result.usage.reduce((s, u) => s + (u.cost_usd || 0), 0);
    totals.ours += ours; totals.cached += data.baseline.cached_usd; totals.full += data.baseline.uncached_usd;
    addA(data, answers.length - 1, ours);
    if (pair && image.fixture) {
      const pa = (pairAnswers[pair.pair_id] ||= {});
      (pa[q] ||= {})[image.fixture.endsWith("b") ? "b" : "a"] = data.result.answer;
      showPairSummary();
    }
    select(answers.length - 1);
    updateMeter();
  } catch (err) {
    addError(String(err));
  } finally { $("send").disabled = false; $("q").focus(); }
};

function addQ(q) {
  const d = document.createElement("div"); d.className = "msg-q"; d.textContent = q;
  $("chat").append(d); d.scrollIntoView({ block: "end" });
}
function addError(t) {
  const d = document.createElement("div"); d.className = "msg-a"; d.textContent = "Error: " + t;
  $("chat").append(d);
}
function addA(data, i, ours) {
  const { result, baseline, source, views } = data;
  const d = document.createElement("div"); d.className = "msg-a";
  const head = document.createElement("div"); head.className = "ans";
  const [label, tip] = SOURCE[source] || [source, ""];
  const src = document.createElement("span"); src.className = `src ${source}`; src.textContent = label; src.title = tip;
  const txt = document.createElement("span");
  txt.textContent = result.abstained
    ? (result.error ? "No answer: " + result.error : "Cannot answer from the available evidence.")
    : result.answer;
  head.append(src, txt);
  const route = document.createElement("div"); route.className = "route";
  result.route.forEach((s, k) => {
    if (k) route.insertAdjacentHTML("beforeend", '<span class="arrow">→</span>');
    const c = document.createElement("span"); c.className = `chip ${s.step}`;
    c.textContent = s.step === "fallback" ? "OCR not enough"
      : s.target ? `${s.step} ${s.target.length > 18 ? s.target.slice(0, 18) + "…" : s.target}` : s.step;
    c.title = [s.target, s.note].filter(Boolean).join(" · ");
    route.append(c);
  });
  const imgTok = result.usage.reduce((s, u) => s + (u.input_image_tokens || 0), 0);
  const save = baseline.uncached_usd > 0 ? (1 - ours / baseline.uncached_usd) * 100 : 0;
  const est = result.usage.some((u) => u.estimated) ? " (est.)" : "";
  const cost = document.createElement("div"); cost.className = "cost";
  cost.innerHTML = `${usd(ours)}${est} · ${imgTok} img tok vs full page ${baseline.image_tokens} ` +
    `· <span class="save">${save >= 0 ? "−" : "+"}${Math.abs(save).toFixed(0)}%</span> vs uncached full page`;
  d.append(head, route, cost);
  if (views && views.length) {
    const strip = document.createElement("div"); strip.className = "views";
    for (const v of views) {
      const fig = document.createElement("figure");
      const im = document.createElement("img"); im.src = v.data_url; im.alt = v.step;
      im.onclick = (ev) => { ev.stopPropagation(); window.open().document.write(`<img src="${v.data_url}">`); };
      const cap = document.createElement("figcaption"); cap.textContent = `${v.step} · ${v.px[0]}×${v.px[1]}px sent`;
      fig.append(im, cap); strip.append(fig);
    }
    d.append(strip);
  }
  d.onclick = () => select(i);
  d.dataset.i = i;
  $("chat").append(d); d.scrollIntoView({ block: "end" });
}
function select(i) {
  active = i;
  document.querySelectorAll(".msg-a").forEach((el) => el.classList.toggle("active", +el.dataset.i === i));
  draw();
}

function updateMeter() {
  const max = Math.max(totals.full, totals.cached, totals.ours, 1e-9);
  for (const k of ["ours", "cached", "full"]) {
    $(`b-${k}`).style.width = `${(totals[k] / max) * 100}%`;
    $(`v-${k}`).textContent = usd(totals[k]);
  }
  const n = answers.length;
  const pct = (x) => { const v = (1 - totals.ours / x) * 100; return `${v >= 0 ? "−" : "+"}${Math.abs(v).toFixed(0)}%`; };
  $("meter-foot").textContent = n ? `${n} question${n > 1 ? "s" : ""} on this image · ` +
    `${pct(totals.full)} cost vs full page, ${pct(totals.cached)} vs cached page (estimates)` : "0 questions";
}

function draw() {
  if (!image || !img.complete) return;
  const r = img.getBoundingClientRect(), s = $("stage").getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  canvas.style.left = `${r.left - s.left + $("stage").scrollLeft}px`;
  canvas.style.top = `${r.top - s.top + $("stage").scrollTop}px`;
  canvas.style.width = `${r.width}px`; canvas.style.height = `${r.height}px`;
  canvas.width = r.width * dpr; canvas.height = r.height * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const W = r.width, H = r.height;
  const res = active >= 0 ? answers[active].result : null;

  if ($("showGrid").checked) {
    ctx.strokeStyle = "rgba(100,116,139,.35)"; ctx.lineWidth = 1;
    ctx.font = "600 11px ui-monospace, monospace"; ctx.fillStyle = "rgba(100,116,139,.8)";
    for (let c = 0; c < COLS; c++) for (let rr = 0; rr < ROWS; rr++)
      ctx.strokeRect(c * W / COLS, rr * H / ROWS, W / COLS, H / ROWS);
    for (let c = 0; c < COLS; c++) ctx.fillText(`C${c + 1}`, c * W / COLS + 4, 12);
    for (let rr = 1; rr < ROWS; rr++) ctx.fillText(`R${rr + 1}`, 3, rr * H / ROWS + 12);
  }
  if (!res) return;
  const zooms = res.route.filter((s) => s.step === "zoom" && s.box);
  ctx.setLineDash([6, 4]); ctx.lineWidth = 2; ctx.strokeStyle = css("--cell");
  zooms.forEach(({ box: b }) => ctx.strokeRect(b[0] * W, b[1] * H, (b[2] - b[0]) * W, (b[3] - b[1]) * H));
  ctx.setLineDash([]);
  res.evidence_boxes.forEach((e) => {
    const [x0, y0, x1, y1] = e.box;
    ctx.lineWidth = 3; ctx.strokeStyle = e.source === "ocr" ? css("--ocr") : css("--zoom");
    ctx.strokeRect(x0 * W - 2, y0 * H - 2, (x1 - x0) * W + 4, (y1 - y0) * H + 4);
  });
}

init();
