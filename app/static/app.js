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
  if (cfg.page_model) {  // say which model each side of the meter is priced with
    $("l-cached").textContent = `Full image, cached (${cfg.page_model})`;
    $("l-full").textContent = `Full image (${cfg.page_model})`;
  }
  $("pipeline").textContent = `pipeline: ${cfg.pipeline}`;
  if (cfg.live) {
    $("banner").hidden = false;
    $("banner").innerHTML = `<b>Live demo.</b> <span class='src ocr'>LIVE OCR</span> answers are local ($0). ` +
      (String(cfg.model || "").startsWith("local:")
        ? `<span class='src model'>MODEL</span> answers come from <code>${cfg.model.slice(6)}</code> running <b>on this laptop</b> ` +
          `(no API call, $0, the document never leaves the machine), on the crop or the full page.`
        : `<span class='src model'>MODEL</span> answers come from a real call to <code>${cfg.model || "the model"}</code> ` +
          `on the crop (or the full page when no template anchor applies); their cost is billed.`) +
      (cfg.replay ? " If a live call fails, that answer is replayed from fixture labels and marked REPLAY." : "");
  } else if (cfg.replay) {
    $("banner").hidden = false;
    $("banner").innerHTML = "<b>Key-free rehearsal.</b> <span class='src ocr'>LIVE OCR</span> answers are real " +
      "(local OCR, $0). <span class='src replay'>REPLAY</span> answers replay the fixture's gold labels through the real " +
      "router (OCR → template-anchored crop → full-page fallback) and box-mapping code, to show <i>which pixels</i> a model " +
      "would be sent. They are not model output, and their costs are estimates.";
  }
  for (const p of cfg.pairs) {
    const o = document.createElement("option");
    o.value = p.pair_id;
    const what = (p.forms.find((f) => f.note && f.note.includes("counterfactual")) || {}).note || "";
    const diff = what.includes("tick") ? "B's ticks differ" : what.includes("sketch") ? "the sketch differs" : "";
    const layout = p.pair_id.startsWith("eas3b") ? "layout 3 (configured template) · " :
      p.pair_id.startsWith("eas2") ? "layout 2 · " : p.pair_id.startsWith("eas-") ? "layout 1 · " : "";
    o.textContent = p.pair_id === "demo" ? "demo form" : `${layout}${p.pair_id}${diff ? " · pair: " + diff : ""}`;
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
    const b = document.createElement("button"); b.type = "button"; b.title = q;
    const short = q.replace(/\s*Answer (with|yes|A or B|in)\b.*$/i, "");
    b.textContent = short.length > 48 ? short.slice(0, 46) + "…" : short;
    b.onclick = () => askQ(q);
    box.append(b);
  }
}

$("ask").onsubmit = async (e) => {
  e.preventDefault();
  const q = $("q").value.trim(); if (!q || !image) return;
  await askQ(q);
};

async function askQ(q) {
  $("q").value = ""; $("send").disabled = true;
  addQ(q);
  // visible progress while a (possibly slow, on-device) model call runs
  const wait = document.createElement("div"); wait.className = "msg-a waiting";
  const who = !cfg.live ? "Running the route" : String(cfg.model || "").startsWith("local:")
    ? `OCR, then ${cfg.model.slice(6)} on this laptop if pixels are needed` : `OCR, then ${cfg.model} if pixels are needed`;
  const t0 = Date.now();
  const tick = () => { wait.textContent = `${who}… ${((Date.now() - t0) / 1000).toFixed(0)} s`; };
  tick(); const timer = setInterval(tick, 500);
  $("chat").append(wait); wait.scrollIntoView({ block: "end" });
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
  } finally { clearInterval(timer); wait.remove(); $("send").disabled = false; $("q").focus(); }
}

function addQ(q) {
  const d = document.createElement("div"); d.className = "msg-q"; d.textContent = q;
  $("chat").append(d); d.scrollIntoView({ block: "end" });
}
function addError(t) {
  const d = document.createElement("div"); d.className = "msg-a"; d.textContent = "Error: " + t;
  $("chat").append(d);
}
// One plain-language sentence: what happened and what it saved (for a judge, not a developer).
function explain(data) {
  const { result: r, source, baseline } = data;
  const zoom = r.route.find((st) => st.step === "zoom");
  const px = zoom && /(\d+)x(\d+)px/.exec(zoom.note || "");
  const inTok = r.usage.reduce((a, u) => a + (u.input_image_tokens || 0) + (u.input_text_tokens || 0) +
    (u.cache_read_tokens || 0) + (u.cache_write_tokens || 0), 0);
  const pageTok = (baseline.image_tokens || 0) + (baseline.text_tokens || 0);
  const est = r.usage.some((u) => u.estimated) ? " (estimated)" : "";
  const lab = (r.evidence_boxes || []).map((e) => e.label).find(Boolean);
  if (source === "ocr") return `Read on this computer by OCR${lab ? ` from the printed line "${lab}"` : ""}: no model call, $0.`;
  if (!zoom) return source === "unavailable" ? "No stage could answer this question, so nothing was invented." : "";
  const t = zoom.target || "", size = px ? `${px[1]}×${px[2]} px` : "";
  const pct = pageTok ? Math.round((1 - inTok / pageTok) * 100) : 0;
  if (t.startsWith("anchor:")) {
    const what = t.includes("tick_row") ? "the circumstance row in question" : t.includes("ticks")
      ? "the driver's tick column next to the row numbers" : t.includes("sketch") ? "the sketch panel" : "the relevant region";
    return `The form's own layout (read by OCR, no model) located ${what}. The model was sent only that ${size} crop: ` +
      `~${inTok} input tokens${est} instead of ~${pageTok} (estimated) for the whole page, ${pct}% fewer` +
      (t.includes("deskew") ? "; the tilted page was straightened first." : ".");
  }
  if (t === "full page")
    return `No configured layout covers this question, so the whole page was sent (${size}, ~${inTok} input tokens${est}).` +
      (r.abstained && !r.error ? " The model reported that the answer is not on the form, instead of inventing one." : "");
  return `A model chose the region to inspect (${t}).`;
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
  // which printed line answered (message 124): the OCR'd field label, or an explicit "not verified" for model answers
  if (!result.abstained) {
    const lab = (result.evidence_boxes || []).map((e) => e.label).find(Boolean);
    const from = document.createElement("div"); from.className = "note";
    from.textContent = lab ? `from the line labelled "${lab}"` : (source === "ocr" ? "" : "field label not verified");
    if (from.textContent) head.append(from);
  }
  if (data.live_error) {
    const le = document.createElement("div"); le.className = "note";
    le.textContent = "live call failed (" + data.live_error.slice(0, 120) + "); " +
      (source === "replay" ? "replayed from fixture labels" : "no fixture replay for this question, so no answer");
    head.append(le);
  }
  const route = document.createElement("div"); route.className = "route";
  result.route.forEach((s, k) => {
    if (k) route.insertAdjacentHTML("beforeend", '<span class="arrow">→</span>');
    const c = document.createElement("span"); c.className = `chip ${s.step}`;
    c.textContent = s.step === "fallback" ? "OCR not enough"
      : s.target ? `${s.step} ${s.target.length > 18 ? s.target.slice(0, 18) + "…" : s.target}` : s.step;
    c.title = [s.target, s.note].filter(Boolean).join(" · ");
    route.append(c);
  });
  // all input tokens as billed (OpenRouter reports one input total, without an image/text split)
  const inTok = result.usage.reduce((s, u) => s + (u.input_image_tokens || 0) + (u.input_text_tokens || 0) +
    (u.cache_read_tokens || 0) + (u.cache_write_tokens || 0), 0);
  const save = baseline.uncached_usd > 0 ? (1 - ours / baseline.uncached_usd) * 100 : 0;
  const est = result.usage.some((u) => u.estimated) ? " (est.)" : "";
  const cost = document.createElement("div"); cost.className = "cost";
  cost.innerHTML = `${usd(ours)}${est} · ${inTok} input tok vs full page ~${baseline.image_tokens + (baseline.text_tokens || 0)} ` +
    `· <span class="save">${save >= 0 ? "−" : "+"}${Math.abs(save).toFixed(0)}%</span> vs uncached full page`;
  const why = document.createElement("div"); why.className = "explain"; why.textContent = explain(data);
  d.append(head, ...(why.textContent ? [why] : []), route, cost);
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
    `${pct(totals.full)} cost vs full page, ${pct(totals.cached)} vs cached page` +
    (cfg.route_model && cfg.page_model && cfg.route_model.replace(/^or:anthropic\//, "").replace(/\./g, "-") !== cfg.page_model
      ? ` · route model ${cfg.route_model} vs page model ${cfg.page_model} (different models)` : "") +
    " (page side estimated)" : "0 questions";
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
    if (e.label) {  // caption: the printed label that located this value
      ctx.font = "600 11px ui-sans-serif, system-ui";
      const tx = x0 * W, ty = Math.max(13, y0 * H - 6), tw = ctx.measureText(e.label).width;
      ctx.fillStyle = "rgba(255,255,255,.92)"; ctx.fillRect(tx - 3, ty - 11, tw + 6, 14);
      ctx.fillStyle = ctx.strokeStyle; ctx.fillText(e.label, tx, ty);
    }
  });
}

// ---- guided tour: the judge script, one click per step (works key-free; badges stay honest) -------------
const TOUR = [
  { say: "A standard European accident statement. Printed fields are read on this computer by OCR, for $0.",
    pair: "eas-002", side: "a", q: "What is vehicle A's insurance policy number?" },
  { say: "Ticks need pixels. The form's layout locates driver B's tick column, so a model sees a small crop, not the page.",
    q: "Which circumstance boxes did driver B tick? Answer with the box numbers." },
  { say: "Form b is identical except one of B's ticks moved. The answer changes and the box moves with it.",
    side: "b", q: "Which circumstance boxes did driver B tick? Answer with the box numbers." },
  { say: "A question the form cannot answer: one page call, and the system says so instead of inventing a value.",
    q: "What is driver A's driving licence number?" },
  { say: "A differently designed form (layout 3). A short configured template reads it: printed fields locally again.",
    pair: "eas3b-003", side: "a", q: "What is vehicle A's insurance policy number?" },
  { say: "…and the template finds B's tick column on this layout too.",
    q: "Which circumstance boxes did driver B tick? Answer with the box numbers." },
  { say: "Session cost, top right: this route against sending the whole page each time. That's the tour." },
];
let tourStep = -1;
async function tourGo() {
  tourStep += 1;
  const st = TOUR[tourStep];
  if (!st) { tourEnd(); return; }
  $("tour-say").textContent = `${tourStep + 1}/${TOUR.length} · ${st.say}`;
  $("tour-next").disabled = true;
  try {
    if (st.pair && (!pair || pair.pair_id !== st.pair)) {
      $("pair").value = st.pair; $("pair").onchange(); await new Promise((r) => setTimeout(r, 900));
    }
    if (st.side && st.side !== side) {
      document.querySelector(`#ab button[data-k="${st.side}"]`).click(); await new Promise((r) => setTimeout(r, 900));
    }
    if (st.q) await askQ(st.q);
  } finally {
    $("tour-next").disabled = false;
    $("tour-next").textContent = tourStep + 1 >= TOUR.length ? "Finish" : "Next ▶";
  }
}
function tourEnd() { tourStep = -1; $("tour").hidden = true; }
$("tour-btn").onclick = () => { tourStep = -1; $("tour").hidden = false; $("tour-next").textContent = "Start ▶";
  $("tour-say").textContent = `Guided tour: ${TOUR.length} steps. Click Start, then Next at your own pace.`; };
$("tour-next").onclick = tourGo;
$("tour-exit").onclick = tourEnd;

// ---- "What we measured": approved claims only, each with its limits and its receipt path ---------------
$("claims-btn").onclick = async () => {
  const body = $("drawer-body"); body.innerHTML = "";
  $("drawer").hidden = false;
  try {
    const d = await (await fetch("/api/claims")).json();
    if (!d.approved) {
      body.textContent = "Measured results are pending release review" + (d.status ? ` (${d.status})` : "") + ".";
      return;
    }
    const p = document.createElement("p"); p.className = "claims-about";
    p.textContent = "Every figure below comes from a committed run; the path under each one is its receipt in the repository.";
    body.append(p);
    for (const c of d.claims) {
      const card = document.createElement("div"); card.className = "claim";
      const h = document.createElement("div"); h.className = "claim-title"; h.textContent = c.title;
      const k = document.createElement("span"); k.className = "claim-kind"; k.textContent = c.kind || "";
      const t = document.createElement("p"); t.textContent = c.text;
      const l = document.createElement("p"); l.className = "claim-limits"; l.textContent = "Limits: " + (c.limits || "–");
      const src = document.createElement("code"); src.className = "claim-src"; src.textContent = c.source || "";
      h.append(" ", k); card.append(h, t, l, src); body.append(card);
    }
  } catch (e) { body.textContent = "Could not load the claims: " + e; }
};
$("drawer-close").onclick = () => { $("drawer").hidden = true; };

init();
