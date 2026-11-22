const $ = (id) => document.getElementById(id);
const img = $("img"), canvas = $("overlay"), ctx = canvas.getContext("2d");
const ROWS = 8, COLS = 6;  // must match pipeline.visual default grid
let cfg = { pairs: [], replay: false };
let image = null;           // {image_id, width, height, url, fixture}
let answers = [];           // [{result, baseline, source, views}]
let active = -1;
let totals = { ours: 0, cached: 0, full: 0 };
let sess = { ours: 0, full: 0, n: 0 };
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
  if (cfg.live && (cfg.models || []).length > 1) {  // presenter can switch cloud <-> on-device per question
    const pick = $("model-pick"); pick.hidden = false;
    for (const m of cfg.models) {
      const o = document.createElement("option"); o.value = m.id;
      o.textContent = m.on_device ? `${m.id.replace(/^local:/, "")} · on this laptop` : `${m.id.replace(/^or:anthropic\//, "")} · cloud API`;
      pick.append(o);
    }
    pick.value = cfg.model || cfg.models[0].id;
    pick.onchange = () => { cfg.model = pick.value; cfg.on_device = !!(cfg.models.find((m) => m.id === pick.value) || {}).on_device; };
  }
  if (cfg.live) {
    $("live-chip").hidden = false;
    $("live-chip").textContent = "LIVE";
    $("live-chip").title = "OCR runs on this computer; questions that need pixels go to the selected vision model";
  } else if (cfg.replay) {
    $("banner").hidden = false;
    $("banner").innerHTML = "<b>Key-free rehearsal.</b> <span class='src ocr'>LIVE OCR</span> answers are real (local OCR, $0). " +
      "<span class='src replay'>REPLAY</span> answers replay the sample's stored gold labels through the real router to show " +
      "<i>which pixels</i> a model would be sent: not model output; costs are estimates.";
  }
  for (const p of cfg.pairs) {
    const o = document.createElement("option");
    o.value = p.pair_id;
    const what = (p.forms.find((f) => f.note && f.note.includes("counterfactual")) || {}).note || "";
    const diff = p.pair_id.startsWith("hw-") ? "the circled option and the chart differ" :
      what.includes("tick") ? "B's ticks differ" : what.includes("sketch") ? "the sketch differs" : "";
    const num = (p.pair_id.match(/(\d+)$/) || [])[1];
    const kind = p.pair_id.startsWith("hw-") ? "Homework sheet" :
      p.pair_id.startsWith("eas3b") ? "Accident claim form, style 3" :
      p.pair_id.startsWith("eas2") ? "Accident claim form, style 2" : p.pair_id.startsWith("eas-") ? "Accident claim form" : "Sample";
    o.textContent = p.pair_id === "demo" ? "Demo form" : `${kind} #${num ? +num : ""}${diff ? " (two versions: " + diff + ")" : ""}`;
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
  note.textContent = `Showing version ${side.toUpperCase()}. ` +
    (rows.length ? rows.join("  |  ") : "Ask the same question on version A and version B to compare.");
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
async function uploadFile(f) {
  if (!f) return;
  saveSession();
  pair = null; $("pair").value = ""; $("ab").hidden = true; $("formnote").hidden = true;
  const fd = new FormData(); fd.append("file", f);
  loadImage(await fetch("/api/images", { method: "POST", body: fd }));
}
$("file").onchange = (e) => uploadFile(e.target.files[0]);
if ($("file2")) $("file2").onchange = (e) => uploadFile(e.target.files[0]);
$("stage").addEventListener("dragover", (e) => { e.preventDefault(); $("stage").classList.add("dragging"); });
$("stage").addEventListener("dragleave", () => $("stage").classList.remove("dragging"));
$("stage").addEventListener("drop", (e) => {
  e.preventDefault(); $("stage").classList.remove("dragging");
  const f = e.dataTransfer.files && e.dataTransfer.files[0]; if (f) uploadFile(f);
});
$("showGrid").onchange = draw;
img.onload = draw;
window.onresize = draw;

function setSuggestions() {
  const box = $("suggest"); box.innerHTML = "";
  const f = currentForm();
  const qs = f ? f.questions : (image ? ["What is the total amount?", "What is the date?", "How much tax was paid?",
    "What is the invoice or order number?", "Who is the seller?"] : []);
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
  const imageId = image.image_id;
  $("q").value = ""; $("send").disabled = true;
  addQ(q);
  // visible progress while a (possibly slow, on-device) model call runs
  const wait = document.createElement("div"); wait.className = "msg-a waiting";
  const who = !cfg.live ? "Running the route" : String(cfg.model || "").startsWith("local:")
    ? `OCR, then ${cfg.model.slice(6)}${cfg.on_device ? " on this laptop" : ""} if pixels are needed` : `OCR, then ${cfg.model} if pixels are needed`;
  const t0 = Date.now();
  const tick = () => { wait.textContent = `${who}… ${((Date.now() - t0) / 1000).toFixed(0)} s`; };
  tick(); const timer = setInterval(tick, 500);
  $("chat").append(wait); wait.scrollIntoView({ block: "end" });
  try {
    const r = await fetch("/api/ask", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image_id: imageId, question: q, model: cfg.live ? cfg.model : null, mode: null }) });
    const data = await r.json();
    if (!r.ok) throw new Error(data.detail || r.status);
    data.question = q;
    data.imageId = imageId;
    data.elapsedMs = Date.now() - t0;
    answers.push(data);
    const ours = data.result.usage.reduce((s, u) => s + (u.cost_usd || 0), 0);
    totals.ours += ours; totals.cached += data.baseline.cached_usd; totals.full += data.baseline.uncached_usd;
    if (!data.answer_cache) {  // repeats are not a measured saving: keep them out of the card (audit 211)
      sess.ours += inputTokens(data.result); sess.full += (data.baseline.image_tokens || 0) + (data.baseline.text_tokens || 0);
      sess.n += 1; updateSaving();
    }
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
  if (data.answer_cache) return "Same image and same question as earlier in this session: answered from the answer cache, 0 model tokens.";
  if (r.error) return "";  // the failure is shown in the answer line; do not describe a route that did not answer
  if (source === "ocr") return `Read on this computer by OCR${lab ? ` from the printed line "${lab}"` : ""}: no model call, $0.`;
  const txt = r.route.find((st) => st.step === "native_text");
  if (txt && !zoom) {
    const nl = /(\d+) lines/.exec(txt.note || "");
    return `Answered from the OCR text alone: the model was sent ${nl ? nl[1] + " lines of text" : "the page's text"} and ` +
      `no image (~${inTok} input tokens${est} instead of ~${pageTok} (estimated) for the page image).`;
  }
  if (txt && zoom) {
    const fb = r.route.find((st) => st.step === "fallback" && st.target === "image");
    const why = fb && fb.note ? fb.note.replace(/^needs pixels: /, "") : "";
    if (zoom.target !== "full page" && r.route.some((st) => st.step === "zoom" && st.target === "full page"))
      return `The model inspected a band around the cited OCR lines, then the router sent the whole page. Total input across the route was ${inTok} tokens${est}.`;
    const pxs = /(\d+)x(\d+)px/.exec(zoom.note || "");
    return `The OCR text was not enough${why ? ` (needs: ${why})` : ""}, so the model was sent ` +
      `${zoom.target === "full page" ? "the whole page" : "a band of the page around the lines it pointed to"}` +
      `${pxs ? ` (${pxs[1]}×${pxs[2]} px)` : ""}: ~${inTok} input tokens in total${est}.`;
  }
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
  if (r.route.some((st) => /low-resolution answer found in the OCR text/.test(st.note || "")))
    return `Asked on a small version of the page first (${size}, ~${inTok} input tokens${est} instead of ~${pageTok} ` +
      `(estimated) for the original image). The answer appears in the page's local OCR text, ` +
      `so no larger image was sent.`;
  if (r.route.some((st) => /^ladder: answer not in the OCR text/.test(st.note || "")))
    return `Asked on a small version first; that answer was not found in the local OCR text, so the page was ` +
      `asked again at higher resolution (~${inTok} input tokens${est} in total, original image ~${pageTok} (estimated)).`;
  const small = r.route.find((st) => /^small image/.test(st.note || ""));
  if (t === "full page" && small)
    return `The router estimated that the whole image would use fewer or equal input tokens than the OCR-text request. ` +
      `It sent the whole page (${size}, ~${inTok} input tokens${est}). OCR ran locally.`;
  if (t === "full page" && r.route.some((st) => /text step off/.test(st.note || "")) && !data.on_device)
    return `The page was sent whole, downscaled to ${size} (~${inTok} input tokens${est} instead of ~${pageTok} ` +
      `(estimated) at full size, ${pageTok ? Math.max(0, Math.round((1 - inTok / pageTok) * 100)) : 0}% fewer). On 70 DocVQA scans ` +
      `whole pages at 1024 px had the same mean ANLS as full size (infographics lost accuracy). OCR still ran locally.`;
  if (t === "full page" && r.route.some((st) => /text step off/.test(st.note || "")))
    return `Small on-device models did not reliably tell when OCR text is not enough (measured on Qwen2.5-VL-7B), so this one was sent the whole page ` +
      `(${size}, ~${inTok} input tokens${est}); OCR still ran locally for the green boxes.`;
  if (t === "full page") {
    const cropped = zoom.box && (zoom.box[0] > 0 || zoom.box[1] > 0 || zoom.box[2] < 1 || zoom.box[3] < 1);
    const region = cropped ? "the OCR text area" : "the whole image";
    return `The model received ${region} at ${size}. The route used ${inTok} input tokens${est}. ` +
      `The estimated input for the original image and prompt is ${pageTok} tokens.` +
      (r.abstained && !r.error ? " The model declined to answer." : "");
  }
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
    ? (result.error ? "No answer: " + result.error + ". Human review needed."
      : "I can’t answer this from the image. Human review needed.")
    : result.answer;
  head.append(src, txt);
  // which printed line answered (message 124): the OCR'd field label, or an explicit "not verified" for model answers
  if (!result.abstained) {
    const lab = (result.evidence_boxes || []).map((e) => e.label).find(Boolean);
    const from = document.createElement("div"); from.className = "note";
    const general = data.pipeline === "pipeline.general";
    const lines = (result.evidence_boxes || []).filter((e) => e.source === "ocr" && e.label).length;
    const located = (result.evidence_boxes || []).some((e) => e.source === "ocr") &&
      result.route.some((st) => /found in the OCR text|answer located by OCR/.test(st.note || ""));
    from.textContent = located ? "✓ found in the page text (green box)"
      : general ? (lines ? `cites ${lines} OCR line${lines > 1 ? "s" : ""} (green boxes)` : "")
      : (lab ? `from the line labelled "${lab}"` : "");
    if (located) from.classList.add("ok");
    if (from.textContent) head.append(from);
  }
  if (source === "model" && data.model) {
    const mm = document.createElement("div"); mm.className = "note";
    mm.textContent = `answered by ${data.model.replace(/^local:|^or:anthropic\//, "")} · ${data.on_device ? "on this laptop" : "cloud API"}`;
    head.append(mm);
  }
  if (data.live_error) {
    const le = document.createElement("div"); le.className = "note";
    le.textContent = "live call failed (" + data.live_error.slice(0, 120) + "); " +
      (source === "replay" ? "replayed from fixture labels" : "no fixture replay for this question, so no answer");
    head.append(le);
  }
  const route = document.createElement("div"); route.className = "route";
  // consecutive fallbacks (OCR declined, no form layout) read as one step
  const steps = result.route.filter((s, k, a) => !((s.step === "fallback" || s.step === "answer") && a[k + 1] &&
    a[k + 1].step === s.step));
  steps.forEach((s, k) => {
    if (k) route.insertAdjacentHTML("beforeend", '<span class="arrow">→</span>');
    const c = document.createElement("span"); c.className = `chip ${s.step}`;
    c.textContent = s.step === "fallback"
      ? (/text step off/.test(s.note || "") ? "whole page" : /^small image/.test(s.note || "") ? "small image"
        : /band crop was not enough/.test(s.note || "") ? "band not enough"
        : /no OCR answer or anchor/.test(s.note || "") ? "no form layout: page"
        : /^ladder:/.test(s.note || "") ? "not in OCR text: higher res" : "OCR not enough")
      : s.step === "abstain" && /no larger image sent/.test(s.note || "") ? "not on the page: handed off"
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
    `· <span class="save">${save >= 0 ? "−" : "+"}${Math.abs(save).toFixed(0)}%</span> vs uncached full page` +
    `${cfg.page_model ? " on " + cfg.page_model : ""} (estimate)`;
  // model-free second opinion on tick questions
  const ck = data.check;
  let ckEl = null;
  if (ck && (ck.available || /resolution|blurred|crisp|tilted/.test(ck.reason || ""))) {
    ckEl = document.createElement("div"); ckEl.className = "check";
    if (!ck.available) { ckEl.classList.add("muted"); ckEl.textContent = `Pixel check: not run (${ck.reason}).`; }
    else {
      const verdict = ck.agrees === true ? "same as the answer" : ck.agrees === false ? "differs from the answer: check this by eye" : "";
      ckEl.textContent = `Pixel check (no model, clean scans only): ${ck.kind === "tick_row"
        ? `box ${ck.row} for driver ${ck.side.toUpperCase()} looks ${ck.answer === "yes" ? "ticked" : "empty"}`
        : `driver ${ck.side.toUpperCase()}'s ticked boxes look like ${ck.answer}`}${verdict ? " · " + verdict : ""}`;
      if (ck.agrees === false) ckEl.classList.add("warn");
    }
  }
  // the general route appends the tutoring explanation to its OCR-text step's note
  const tnote = (result.route.find((st) => /explanation: /.test(st.note || "")) || {}).note || "";
  let tutor = null;
  if (tnote) {
    tutor = document.createElement("div"); tutor.className = "tutor";
    tutor.textContent = tnote.split("explanation: ").slice(1).join("explanation: ");
  }
  const why = document.createElement("div"); why.className = "explain"; why.textContent = explain(data);
  // the headline for a customer: what this answer cost in model tokens, against sending the original image
  const pageTok = (baseline.image_tokens || 0) + (baseline.text_tokens || 0);
  const pill = document.createElement("div"); pill.className = "pill";
  if (data.answer_cache) pill.innerHTML = "<b>0 input tokens</b> · same question as before, answered from the cache";
  else if (source === "ocr" && !inTok) pill.innerHTML = "<b>0 model tokens</b> · read on this computer by OCR";
  else if (!inTok) pill.innerHTML = "<b>0 input tokens</b> · no model answer";
  else {
    const p = pageTok ? Math.round((1 - inTok / pageTok) * 100) : 0;
    pill.innerHTML = `<b>${inTok.toLocaleString()} input tokens</b> · ` + (p >= 0
      ? `${p}% fewer than the original image (~${pageTok.toLocaleString()}, est.)`
      : `${-p}% more than the original image (~${pageTok.toLocaleString()}, est.)`);
  }
  if (result.abstained) pill.classList.add("muted");
  const tok = tokenBars(data.answer_cache ? 0 : inTok, pageTok, pill);
  const stepper = pathSteps(data);
  const red = result.route.find((st) => /^redacted before sending: /.test(st.note || ""));
  let redEl = null;
  if (red) {
    redEl = document.createElement("div"); redEl.className = "privacy";
    redEl.textContent = "Masked OCR-detected lines in the page image sent to the model: " + red.note.replace(/^redacted before sending: /, "");
  }
  const how = document.createElement("details"); how.className = "how";
  const sum = document.createElement("summary"); sum.textContent = "How this was answered";
  how.append(sum, ...(why.textContent ? [why] : []), route, cost);
  d.append(head, stepper, tok, ...(redEl ? [redEl] : []), ...(tutor ? [tutor] : []), ...(ckEl ? [ckEl] : []));
  // live only: ask the same model with the whole page, and show both sides with real (billed) numbers
  const wholePage = result.route.some((st) => st.step === "zoom" && st.target === "full page") &&
    !result.route.some((st) => st.step === "zoom" && st.target !== "full page");
  if (cfg.live && (source === "model" || source === "ocr") && !wholePage) {  // nothing to compare if we sent the page
    const q = data.question || (d.previousElementSibling && d.previousElementSibling.textContent) || "";
    const btn = document.createElement("button"); btn.type = "button"; btn.className = "btn ghost cmp-btn";
    btn.textContent = "Compare: send the original, unmasked image";
    const out = document.createElement("div"); out.className = "cmp";
    btn.onclick = async () => {
      btn.disabled = true; const t0 = Date.now();
      const tk = setInterval(() => { out.textContent = `Sending the whole page to the same model… ${((Date.now() - t0) / 1000).toFixed(0)} s`; }, 400);
      try {
        const r = await fetch("/api/compare", { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ image_id: data.imageId, question: q, model: data.model, mode: data.mode || null }) });
        const c = await r.json(); if (!r.ok) throw new Error(c.detail || r.status);
        if (c.error) throw new Error(c.error);
        const bill = String(c.model).startsWith("local:") ? "no provider charge" : "billed";
        out.innerHTML = `<b>Our route</b>: ${usd(ours)} · ${inTok} input tok · ${(data.elapsedMs / 1000).toFixed(1)} s` +
          `<br><b>Whole page</b> (${c.image_px[0]}×${c.image_px[1]} px, same model): ${usd(c.cost_usd)} · ${c.input_tokens} input tok · ` +
          `${((Date.now() - t0) / 1000).toFixed(1)} s (${bill}) · answer: `;
        out.append(document.createTextNode(c.abstained ? "no answer" : (c.answer || "–")));
        btn.remove();
      } catch (e) { out.textContent = "Comparison failed: " + e; btn.disabled = false; }
      finally { clearInterval(tk); }
    };
    how.append(btn, out);
  }
  if (views && views.length) {
    const strip = document.createElement("div"); strip.className = "views";
    const cap0 = document.createElement("div"); cap0.className = "views-cap"; cap0.textContent = "What the model saw";
    d.append(cap0);
    for (const v of views) {
      const fig = document.createElement("figure");
      const im = document.createElement("img"); im.src = v.data_url; im.alt = v.step;
      im.onclick = (ev) => { ev.stopPropagation(); window.open().document.write(`<img src="${v.data_url}">`); };
      const cap = document.createElement("figcaption"); cap.textContent = `${v.step} · ${v.px[0]}×${v.px[1]}px sent`;
      fig.append(im, cap); strip.append(fig);
    }
    d.append(strip);
  }
  if (result.abstained) {  // human handoff: a ticket the agent can start from, built from what the bot already has
    const tb = document.createElement("button"); tb.type = "button"; tb.className = "btn ticket-btn";
    tb.textContent = "Create ticket for a human agent";
    const tk = document.createElement("pre"); tk.className = "ticket"; tk.hidden = true;
    tb.onclick = (ev) => {
      ev.stopPropagation();
      const q = data.question || "";
      const words = q.toLowerCase().match(/[a-z0-9]{3,}/g) || [];
      const ranked = (data.ticket_lines || []).map((t, k) => [words.filter((w) => t.toLowerCase().includes(w)).length, k, t])
        .sort((a, b) => b[0] - a[0] || a[1] - b[1]).slice(0, 8).sort((a, b) => a[1] - b[1]).map((x) => "  " + x[2]);
      tk.textContent = [`Customer question: ${q}`,
        `Bot result: could not answer from the image${result.error ? " (" + result.error.slice(0, 80) + ")" : ""}`,
        `Tried: ${steps.map((st) => st.step).join(" → ")} · ${inTok} input tokens`,
        `Image: ${image ? image.width + "×" + image.height + " px" : ""} (attached in the conversation)`,
        "Page text near the question (local OCR):", ...(ranked.length ? ranked : ["  (no text found)"])].join("\n");
      tk.hidden = false; tb.textContent = "Copy ticket";
      tb.onclick = (e2) => { e2.stopPropagation(); navigator.clipboard && navigator.clipboard.writeText(tk.textContent); tb.textContent = "Copied ✓"; };
    };
    d.append(tb, tk);
  }
  d.append(how);
  how.onclick = (ev) => ev.stopPropagation();
  d.onclick = () => select(i);
  d.dataset.i = i;
  $("chat").append(d);
  const qEl = d.previousElementSibling;  // keep the question and the answer line in view
  (qEl && qEl.classList.contains("msg-q") ? qEl : d).scrollIntoView({ block: "start" });
}
// Token comparison: what we sent against sending the original image (same estimate as the pill).
function tokenBars(inTok, pageTok, pill) {
  const box = document.createElement("div"); box.className = "tok";
  if (pageTok > 0) {
    const max = Math.max(inTok, pageTok, 1);
    const row = (label, v, cls) => `<div class="cmp-row"><span>${label}</span><div class="cbar"><i class="${cls}" ` +
      `style="width:0%" data-w="${(v / max) * 100}"></i></div><b>${v.toLocaleString()}</b></div>`;
    box.innerHTML = `<div class="vs">${row("Sent", inTok, "ours")}${row("Original image", pageTok, "base")}</div>`;
    requestAnimationFrame(() => requestAnimationFrame(() =>
      box.querySelectorAll("i[data-w]").forEach((el) => { el.style.width = `${Math.max(+el.dataset.w, inTok ? 1.5 : 0)}%`; })));
  }
  const foot = document.createElement("div"); foot.className = "tok-delta";
  pill.classList.add("pill-in");
  foot.append(pill);
  box.append(foot);
  return box;
}
// The path this answer took through the route, cheapest step first (what ran, what answered).
function pathSteps(data) {
  const r = data.result, route = r.route || [];
  const zooms = route.filter((st) => st.step === "zoom");
  const notes = route.map((st) => st.note || "").join(" | ");
  const px = (z) => { const m = /(\d+)x(\d+)px/.exec((z && z.note) || ""); return m ? `${m[1]}×${m[2]} px` : ""; };
  const steps = [];
  const ocrHit = data.source === "ocr";
  steps.push(["Read locally", ocrHit ? "answered · $0" : "OCR · $0", ocrHit ? "free" : "pass"]);
  if (data.answer_cache) steps.push(["Answer cache", "0 tokens", "free"]);
  else if (!ocrHit) {
    const anchor = zooms.find((z) => (z.target || "").startsWith("anchor:"));
    if (anchor) steps.push(["Layout crop", px(anchor) || "region", "hit"]);
    else if (zooms.length) steps.push([zooms[0].target === "full page" && zooms.length === 1 && !/small image|ladder|low-resolution/.test(notes)
      ? "Page" : "Small page", px(zooms[0]) || "image", "hit"]);
    if (/found in the OCR text|answer located by OCR/.test(notes)) steps.push(["OCR check", "✓ in OCR text", "free"]);
    else if (/ladder: answer not in the OCR text/.test(notes)) steps.push(["OCR check", "not in OCR text", "miss"]);
    if (!anchor && zooms.length > 1) steps.push(["Sharper page", px(zooms[zooms.length - 1]) || "image", "hit"]);
  }
  steps.push(r.abstained ? ["Human review", "flagged · ticket", "handoff"] : ["Answer", "+ evidence box", "ok"]);
  const box = document.createElement("div"); box.className = "steps";
  steps.forEach(([t, sub, cls], k) => {
    if (k) { const e = document.createElement("span"); e.className = "st-edge"; box.append(e); }
    const el = document.createElement("div"); el.className = `st ${cls}`;
    const b = document.createElement("b"); b.textContent = t;
    const sm = document.createElement("small"); sm.textContent = sub;
    el.append(b, sm); box.append(el);
  });
  return box;
}
function select(i) {
  active = i;
  document.querySelectorAll(".msg-a").forEach((el) => el.classList.toggle("active", +el.dataset.i === i));
  draw();
}

function inputTokens(r) {
  return (r.usage || []).reduce((a, u) => a + (u.input_image_tokens || 0) + (u.input_text_tokens || 0) +
    (u.cache_read_tokens || 0) + (u.cache_write_tokens || 0), 0);
}
function fmtTok(n) { return n >= 1e6 ? `${(n / 1e6).toFixed(1)}M` : n >= 1e3 ? `${Math.round(n / 1e3)}k` : `${Math.round(n)}`; }
function updateSaving() {
  $("saving").classList.toggle("idle", !sess.n);
  const pct = sess.full ? Math.round((1 - sess.ours / sess.full) * 100) : null;
  $("sv-pct").textContent = pct === null ? "–" : `${Math.abs(pct)}%`;
  $("sv-label").textContent = pct !== null && pct < 0 ? "more input tokens than sending the original images"
    : "fewer input tokens than sending the original images";
  $("sv-ours").textContent = sess.ours.toLocaleString();
  $("sv-full").textContent = sess.full.toLocaleString();
  const mx = Math.max(sess.ours, sess.full, 1);
  $("sv-bar-ours").style.width = `${Math.max((sess.ours / mx) * 100, sess.ours ? 1.5 : 0)}%`;
  $("sv-bar-full").style.width = `${(sess.full / mx) * 100}%`;
  $("sv-foot").textContent = sess.n ? `input tokens · ${sess.n} question${sess.n > 1 ? "s" : ""} · at this rate 1,000 ` +
    `questions ≈ ${fmtTok(sess.ours / sess.n * 1000)} instead of ${fmtTok(sess.full / sess.n * 1000)}` : "Ask a question to start the count.";
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
  // spotlight: dim everything the model did not see (the last region sent, or the OCR line for an OCR answer)
  const lit = zooms.length ? [zooms[zooms.length - 1].box]
    : (res.evidence_boxes || []).filter((e) => e.source === "ocr").map((e) => e.box);
  if (lit.length) {
    ctx.save(); ctx.beginPath(); ctx.rect(0, 0, W, H);
    lit.forEach((b) => ctx.rect(b[0] * W, b[1] * H, (b[2] - b[0]) * W, (b[3] - b[1]) * H));
    ctx.fillStyle = "rgba(15, 18, 40, 0.55)"; ctx.fill("evenodd"); ctx.restore();
  }
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
  { say: "A claim form. Printed fields are read by OCR on this computer: $0, no model.",
    pair: "eas-002", side: "a", q: "What is vehicle A's insurance policy number?" },
  { say: "Ticks need pixels. The form's layout picks driver B's tick column: the model sees only that crop.",
    q: "Which circumstance boxes did driver B tick? Answer with the box numbers." },
  { say: "Version B: one tick moved. The answer changes and the box moves with it.",
    side: "b", q: "Which circumstance boxes did driver B tick? Answer with the box numbers." },
  { say: "Not on the form: the app says so and flags it for review. Nothing invented.",
    q: "What is driver A's driving licence number?" },
  { say: "A different layout. A 10-line template reads it: printed fields by OCR again.",
    pair: "eas3b-003", side: "a", q: "What is vehicle A's insurance policy number?" },
  { say: "…and the template finds B's tick column here too.",
    q: "Which circumstance boxes did driver B tick? Answer with the box numbers." },
  { say: "The savings card: tokens sent against the original images. Now try your own photo." },
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
    body.append(resultsVisual());
    const all = document.createElement("details"); all.className = "res-all";
    const sm = document.createElement("summary"); sm.textContent = `Every approved result, with its limits and receipt (${d.claims.length})`;
    all.append(sm); body.append(all);
    const p = document.createElement("p"); p.className = "claims-about";
    p.textContent = "Every figure below comes from a committed run; the path under each one is its receipt in the repository.";
    all.append(p);
    for (const c of d.claims) {
      const card = document.createElement("div"); card.className = "claim";
      const h = document.createElement("div"); h.className = "claim-title"; h.textContent = c.title;
      const k = document.createElement("span"); k.className = "claim-kind"; k.textContent = c.kind || "";
      const t = document.createElement("p"); t.textContent = c.text;
      const l = document.createElement("p"); l.className = "claim-limits"; l.textContent = "Limits: " + (c.limits || "–");
      const src = document.createElement("code"); src.className = "claim-src"; src.textContent = c.source || "";
      h.append(" ", k); card.append(h, t, l, src); all.append(card);
    }
  } catch (e) { body.textContent = "Could not load the claims: " + e; }
};
$("drawer-close").onclick = () => { $("drawer").hidden = true; };

// Approved figures (README "What we measured", DEMO tokens table, andrew-review-final-cord / -214-216 / -ladder).
const RESULTS = [
  { lead: true, title: "Fresh receipt photos (held out)", sample: "248 questions · 60 CORD validation receipts · Haiku · one paired run",
    delta: "−65%", unit: "tokens per correct answer",
    rows: [["Evidence Zoom", 968, "ours"], ["Original photo", 2740, "base"]],
    foot: "188 vs 187 correct · 0 vs 1 wrong · all 60 unanswerable questions flagged for review by both" },
  { title: "Configured claim form (synthetic)", sample: "96 questions · Sonnet on both sides",
    unit: "tokens per correct answer", rows: [["Evidence Zoom", 774, "ours"], ["Cached whole page", 5696, "base"]],
    foot: "84 correct each, plus 12 correct deferrals · 48 questions answered by OCR alone" },
  { title: "Second configured layout (synthetic)", sample: "96 questions · Haiku",
    unit: "tokens per correct answer", rows: [["Evidence Zoom", 841, "ours"], ["Original page", 5946, "base"]],
    foot: "84 vs 81 correct · the template engine was tuned on this layout before the freeze" },
  { title: "DocVQA scans (public benchmark)", sample: "100 questions · Haiku · OCR-checked resolution ladder",
    unit: "tokens per correct answer", rows: [["Evidence Zoom", 1574, "ours"], ["Original page", 4587, "base"]],
    foot: "96 vs 96 correct (separately prompted page baseline) · ANLS 0.920 vs 0.931" },
];
const LIMITS = [
  { title: "Layouts we never configured (synthetic)", sample: "416 questions · Haiku",
    unit: "tokens per correct answer", rows: [["Evidence Zoom", 3110, "ours"], ["Plain smaller page", 2986, "alt"], ["Original page", 4894, "base"]],
    foot: "No region selection here: a plain downscaled page was slightly cheaper than our route." },
  { title: "Open models (Qwen 7B, earlier configuration)", sample: "248 receipt questions · local GPU",
    unit: "wrong answers (fewer is better)", rows: [["Evidence Zoom", 31, "ours"], ["Original photo", 14, "base"]],
    foot: "Routing gave more wrong answers, mostly missed review flags (72B: 13 vs 6)." },
];
function resCard(x) {
  const card = document.createElement("div"); card.className = "res" + (x.lead ? " lead" : "");
  const max = Math.max(...x.rows.map((r) => r[1]));
  card.innerHTML = `<div class="res-head"><div><b></b><div class="res-sample"></div></div>${x.delta ? `<span class="res-delta">${x.delta}</span>` : ""}</div>` +
    `<div class="vs">${x.rows.map(([l, v, c]) => `<div class="cmp-row"><span>${l}</span><div class="cbar"><i class="${c}" style="width:0%" ` +
    `data-w="${(v / max) * 100}"></i></div><b>${v.toLocaleString()}</b></div>`).join("")}</div><div class="res-foot"></div>`;
  card.querySelector(".res-head b").textContent = x.title;
  card.querySelector(".res-sample").textContent = `${x.sample} · ${x.unit}`;
  card.querySelector(".res-foot").textContent = x.foot;
  return card;
}
function resultsVisual() {
  const wrap = document.createElement("div");
  const s1 = document.createElement("div"); s1.className = "res-sec"; s1.textContent = "Ours vs sending the original image";
  wrap.append(s1, ...RESULTS.map(resCard));
  const s2 = document.createElement("div"); s2.className = "res-sec"; s2.textContent = "Where it does not help";
  wrap.append(s2, ...LIMITS.map(resCard));
  requestAnimationFrame(() => requestAnimationFrame(() =>
    wrap.querySelectorAll("i[data-w]").forEach((el) => { el.style.width = `${el.dataset.w}%`; })));
  return wrap;
}

// ---- "How it works": the route as a diagram, lit step by step; then the guided demo -----------------------
let howTimer = null;
function howPlay() {
  clearTimeout(howTimer);
  const parts = [...$("flow").children];  // node, edge, node, ...
  parts.forEach((el) => el.classList.remove("lit", "seen"));
  $("hm-ours").style.width = "0%";
  let k = 0;
  const stepFn = () => {
    if (k > 0) parts[k - 1].classList.replace("lit", "seen");
    if (k >= parts.length) { $("hm-ours").style.width = "35.3%"; return; }
    parts[k].classList.add("lit"); k += 1;
    howTimer = setTimeout(stepFn, parts[k - 1].classList.contains("edge") ? 220 : 650);
  };
  stepFn();
}
function howOpen() { $("how").hidden = false; howPlay(); }
function howClose() { clearTimeout(howTimer); $("how").hidden = true; }
$("how-btn").onclick = howOpen;
$("how-close").onclick = howClose;
$("how-play").onclick = howPlay;
$("how").onclick = (e) => { if (e.target === $("how")) howClose(); };
$("how-demo").onclick = () => { howClose(); $("tour-btn").onclick(); tourGo(); };
$("hero-more").onclick = () => $("claims-btn").onclick();
document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape") return;
  if (!$("how").hidden) howClose(); else if (!$("drawer").hidden) $("drawer").hidden = true;
});

init();
