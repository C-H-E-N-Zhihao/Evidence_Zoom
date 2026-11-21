const $ = (id) => document.getElementById(id);
const img = $("img"), canvas = $("overlay"), ctx = canvas.getContext("2d");
const GRID = 4;
let image = null;           // {image_id, width, height, url}
let answers = [];           // [{result, baseline}]
let active = -1;
let totals = { ours: 0, cached: 0, full: 0 };

const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const usd = (x) => `$${x.toFixed(x < 0.01 ? 4 : 3)}`;

async function loadImage(resp) {
  image = await resp.json();
  if (!resp.ok) { alert(image.detail || "upload failed"); image = null; return; }
  img.src = image.url;
  img.style.display = "block";
  $("empty").style.display = "none";
  $("q").disabled = $("send").disabled = false;
  answers = []; active = -1; totals = { ours: 0, cached: 0, full: 0 };
  $("chat").innerHTML = "";
  updateMeter();
}

$("file").onchange = async (e) => {
  const f = e.target.files[0]; if (!f) return;
  const fd = new FormData(); fd.append("file", f);
  loadImage(await fetch("/api/images", { method: "POST", body: fd }));
};
$("sample").onclick = async () => loadImage(await fetch("/api/images/sample", { method: "POST" }));
$("showGrid").onchange = draw;
img.onload = draw;
window.onresize = draw;

document.querySelectorAll("#suggest button").forEach((b) =>
  b.onclick = () => { if (image) { $("q").value = b.textContent; $("ask").requestSubmit(); } });

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
    $("pipeline").textContent = `pipeline: ${data.pipeline}`;
    answers.push(data);
    const ours = data.result.usage.reduce((s, u) => s + (u.cost_usd || 0), 0);
    totals.ours += ours; totals.cached += data.baseline.cached_usd; totals.full += data.baseline.uncached_usd;
    addA(data, answers.length - 1, ours);
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
  const { result, baseline } = data;
  const d = document.createElement("div"); d.className = "msg-a";
  const ans = document.createElement("div"); ans.className = "ans";
  ans.textContent = result.abstained ? "Cannot answer from the available evidence." : result.answer;
  const route = document.createElement("div"); route.className = "route";
  result.route.forEach((s, k) => {
    if (k) route.insertAdjacentHTML("beforeend", '<span class="arrow">→</span>');
    const c = document.createElement("span"); c.className = `chip ${s.step}`;
    c.textContent = s.target ? `${s.step} ${s.target}` : s.step; c.title = s.note || "";
    route.append(c);
  });
  const imgTok = result.usage.reduce((s, u) => s + (u.input_image_tokens || 0), 0);
  const save = baseline.uncached_usd > 0 ? (1 - ours / baseline.uncached_usd) * 100 : 0;
  const cost = document.createElement("div"); cost.className = "cost";
  cost.innerHTML = `${usd(ours)} · ${imgTok} img tok vs full ${baseline.image_tokens} ` +
    `· <span class="save">${save >= 0 ? "−" : "+"}${Math.abs(save).toFixed(0)}%</span>`;
  d.append(ans, route, cost);
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
  $("meter-foot").textContent = n ? `${n} question${n > 1 ? "s" : ""} on this image · ` +
    `${((1 - totals.ours / totals.full) * 100).toFixed(0)}% cheaper than full image, ` +
    `${((1 - totals.ours / totals.cached) * 100).toFixed(0)}% vs cached` : "0 questions";
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
  const zoomed = res ? res.route.filter((s) => s.step === "zoom").map((s) => s.target) : [];

  if ($("showGrid").checked) {
    ctx.strokeStyle = "rgba(100,116,139,.35)"; ctx.lineWidth = 1;
    ctx.font = "600 12px ui-monospace, monospace";
    for (let c = 0; c < GRID; c++) for (let rr = 0; rr < GRID; rr++) {
      const x = c * W / GRID, y = rr * H / GRID;
      ctx.strokeRect(x, y, W / GRID, H / GRID);
      const name = "ABCDEFGH"[c] + (rr + 1);
      ctx.fillStyle = zoomed.includes(name) ? css("--cell") : "rgba(100,116,139,.7)";
      ctx.fillText(name, x + 5, y + 15);
    }
  }
  if (!res) return;
  // dim everything except the zoomed cells
  const cells = res.route.filter((s) => s.step === "zoom" && s.box);
  if (cells.length) {
    ctx.fillStyle = "rgba(0,0,0,.18)"; ctx.beginPath(); ctx.rect(0, 0, W, H);
    cells.forEach(({ box: b }) => ctx.rect(b[2] * W, b[1] * H, (b[0] - b[2]) * W, (b[3] - b[1]) * H));
    ctx.fill("evenodd");
    ctx.setLineDash([6, 4]); ctx.lineWidth = 2; ctx.strokeStyle = css("--cell");
    cells.forEach(({ box: b }) => ctx.strokeRect(b[0] * W, b[1] * H, (b[2] - b[0]) * W, (b[3] - b[1]) * H));
    ctx.setLineDash([]);
  }
  res.evidence_boxes.forEach((e) => {
    const [x0, y0, x1, y1] = e.box;
    ctx.lineWidth = 3; ctx.strokeStyle = e.source === "ocr" ? css("--ocr") : css("--zoom");
    ctx.strokeRect(x0 * W, y0 * H, (x1 - x0) * W, (y1 - y0) * H);
  });
}
