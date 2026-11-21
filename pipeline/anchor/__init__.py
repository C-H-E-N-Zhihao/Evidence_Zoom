"""OCR-anchored region selection: pick the crop from the form's own layout, no model call (owner: claude-andrew-b).

Message 037 / REPORT_local_qwen7b_visual.md: a 7B VLM is 42% on the full page, 67% on the gold crop, and
cannot choose the region itself. Here the OCR spans (rows "N. ...", column headers, section headings) locate
the evidence for the visual questions of the accident statement:

    "which boxes did driver X tick"   -> rows 1..17 x [row numbers, X's tick column]   (row-aligned mosaic)
    "did driver X tick (circumstance) N" -> rows N-1..N+1 x [X's tick column, row N's label]
    "... in the sketch ..."           -> the panel under "13. SKETCH"

    select(image, question) -> Selection | None      (None: anchors not found or question not covered)
    pipeline: anchor_crop  ->  python -m eval.run_eval --pipelines pipeline.anchor:factory  (EVAL_MODEL picks the model)

The crop is built with pipeline.visual.View (same stitching and box mapping as the zoom route).
"""
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field
from typing import Optional

from PIL import Image

from eval.schema import PipelineResult, RouteStep, Usage
from pipeline.visual import View

Span = tuple[float, float]
ROW_RE = re.compile(r"^\s*(\d{1,2})\s*[.,]\s*\S")
SECTION_RE = re.compile(r"^\s*1[3-9]\s*[.,]\s*[A-Z]{3,}")  # later section headings ("13. SKETCH …"), uppercase
MIN_ROWS = 12  # of 17: fewer recognised rows -> do not trust the layout


@dataclass
class Layout:
    rows: dict[int, Span]  # circumstance number -> (y0, y1)
    label_x0: float  # left edge of the "N." labels
    label_x1: dict[int, float]  # right edge of each label text
    cols: dict[str, Span]  # "a"/"b" -> tick-column (x0, x1)
    sketch: Optional[Span]  # (y0, y1) of the sketch panel


@dataclass
class Selection:
    rows: list[Span]
    cols: list[Span]
    kind: str  # "ticks" | "tick_row" | "sketch"
    note: str  # one line told to the model about what the crop shows
    ocr_ms: float = 0.0
    spans: list = field(default_factory=list, repr=False)
    image: Optional[Image.Image] = field(default=None, repr=False)  # page the regions refer to (deskewed if angle)
    angle: float = 0.0  # degrees the page was rotated (PIL convention, counter-clockwise) before selection


# ---- OCR ----------------------------------------------------------------------------------------
def ocr_spans(image: Image.Image) -> tuple[list[dict], float]:
    """OCR spans via pipeline.ocr.recognize_page (shared page cache with the OCR route), and this call's time."""
    from pipeline.ocr import recognize_page
    from pipeline.router import ensure_ocr_bin

    if ensure_ocr_bin() is None:
        raise RuntimeError("OCR helper unavailable")
    t = time.perf_counter()
    spans, _reused = recognize_page(image)
    return spans, (time.perf_counter() - t) * 1000


# ---- layout ----------------------------------------------------------------------------------------
def _find(spans, pred):
    return [s for s in spans if s["confidence"] >= 0.5 and pred(s["text"].strip(), s["box"])]


def layout(spans: list[dict], image: Optional[Image.Image] = None) -> Optional[Layout]:
    head = _find(spans, lambda t, b: re.match(r"^12\s*[.,]?\s*circumstances", t, re.I) is not None)
    if len(head) != 1:
        return None
    top = head[0]["box"][3]
    sk = _find(spans, lambda t, b: re.match(r"^13\s*[.,]?\s*sketch", t, re.I) is not None)
    # Rows run from the circumstances heading down to the next section heading BELOW it (the sketch may come
    # before or after the circumstances), else to the page bottom.
    below = [s["box"][1] for s in _find(spans, lambda t, b: b[1] > top + 0.01 and SECTION_RE.match(t) is not None
                                         and not ROW_RE.match(t[:4] + " x"))]
    below += [sk[0]["box"][1]] if len(sk) == 1 and sk[0]["box"][1] > top else []
    bottom = min(below) if below else 1.0

    rows, x0s, x1s = {}, [], {}
    for s in _find(spans, lambda t, b: top < b[1] < bottom and b[0] < 0.5):
        m = ROW_RE.match(s["text"])
        if m and 1 <= (n := int(m.group(1))) <= 17 and n not in rows:
            rows[n] = (s["box"][1], s["box"][3])
            x0s.append(s["box"][0])
            x1s[n] = s["box"][2]
    if len(rows) < MIN_ROWS:
        return None
    rows = _fill_rows(rows)
    label_x0 = sorted(x0s)[len(x0s) // 2]
    y_first, y_last = rows[1][0], rows[17][1]

    cols = {}
    hdr_band = (top, y_first)
    def _hdr(key):
        return lambda t, b: re.sub(r"\s+", "", t.upper()) in (key, "VEHICLE" + key) and hdr_band[0] <= b[1] <= hdr_band[1] + 0.01
    a = [s for s in _find(spans, _hdr("A")) if s["box"][0] < 0.5]
    if len(a) == 1:
        c = (a[0]["box"][0] + a[0]["box"][2]) / 2
        cols["a"] = (c - 0.02, c + 0.02)
    if "a" not in cols:  # low resolution: no "A" header, but A's tick boxes are read as "•"/"V"/... left of the labels
        frag = [s["box"] for s in spans if (b := s["box"])[2] < label_x0 - 0.005 and b[0] > 0.01
                and y_first - 0.02 <= b[1] <= y_last + 0.02 and (b[2] - b[0]) < 0.06]
        centers = sorted((b[0] + b[2]) / 2 for b in frag)
        if centers and centers[-1] - centers[0] < 0.02:
            c = centers[len(centers) // 2]
            cols["a"] = (c - 0.02, c + 0.02)
    b_ = [s for s in _find(spans, _hdr("B")) if s["box"][0] > 0.5]
    if len(b_) == 1:
        c = (b_[0]["box"][0] + b_[0]["box"][2]) / 2
        cols["b"] = (c - 0.02, c + 0.02)
    else:
        # The B tick boxes are often read as junk ("•000000•0...", "ПК"), one tall span or fragments, often at
        # low confidence. Their boxes still mark the column: use geometry only, any span right of x=0.8 inside
        # the table rows, and require the fragments to agree on x.
        frag = [s["box"] for s in spans if (b := s["box"])[0] > 0.8 and b[2] < 0.99
                and y_first - 0.02 <= b[1] <= y_last + 0.02 and (b[2] - b[0]) < 0.06]
        centers = sorted((b[0] + b[2]) / 2 for b in frag)
        if centers and centers[-1] - centers[0] < 0.02:
            c = centers[len(centers) // 2]
            cols["b"] = (c - 0.02, c + 0.02)
    if image is not None:  # last resort: find the column of box outlines in the pixels
        for side, (xa, xb) in (("a", (0.0, label_x0 - 0.005)), ("b", (0.6, 1.0))):
            if side not in cols and (c := _box_column(image, (y_first, y_last), (xa, xb))) is not None:
                cols[side] = (c - 0.02, c + 0.02)
    sketch = None
    if len(sk) == 1:
        s0 = sk[0]["box"][3] + 0.003
        nxt = [h["box"][1] for h in head if h["box"][1] > s0]  # e.g. the circumstances heading below the sketch
        sketch = (s0, min(1.0, s0 + 0.22, *(n - 0.005 for n in nxt)))
    return Layout(rows, label_x0, x1s, cols, sketch)


def _box_column(image: Image.Image, band: Span, xrange: Span) -> Optional[float]:
    """Centre x of a column of square box outlines: the two vertical edges show up as a pair of pixel columns
    that are dark over most of the table band (0.4-0.95 of its height), 1.2-3.5% of the page width apart."""
    import numpy as np

    g = np.asarray(image.convert("L"))
    h, w = g.shape
    y0, y1 = int(band[0] * h), int(band[1] * h)
    x0, x1 = int(xrange[0] * w), int(xrange[1] * w)
    if y1 - y0 < 20 or x1 - x0 < 10:
        return None
    prof = (g[y0:y1, x0:x1] < 128).mean(0)
    xs = [x0 + i for i in np.where((prof > 0.4) & (prof < 0.95))[0]]
    edges = []  # merge adjacent pixel columns into edges
    for x in xs:
        if edges and x - edges[-1][1] <= 2:
            edges[-1][1] = x
        else:
            edges.append([x, x])
    centers = [(a + b) / 2 for a, b in edges]
    pairs = [(c1, c2) for i, c1 in enumerate(centers) for c2 in centers[i + 1:] if 0.012 * w <= c2 - c1 <= 0.035 * w]
    if len(pairs) != 1:
        return None
    return (pairs[0][0] + pairs[0][1]) / 2 / w


def _fill_rows(rows: dict[int, Span]) -> dict[int, Span]:
    """Interpolate missing row numbers from their neighbours (rows are evenly spaced on the form)."""
    known = sorted(rows)
    out = dict(rows)
    for n in range(1, 18):
        if n in out:
            continue
        lo = max([k for k in known if k < n], default=None)
        hi = min([k for k in known if k > n], default=None)
        if lo is not None and hi is not None:
            f = (n - lo) / (hi - lo)
            out[n] = tuple(rows[lo][i] + f * (rows[hi][i] - rows[lo][i]) for i in range(2))
        else:
            ref, k2 = (lo, known[known.index(lo) - 1]) if hi is None else (hi, known[known.index(hi) + 1])
            pitch = (rows[ref][0] - rows[k2][0]) / (ref - k2)
            out[n] = (rows[ref][0] + (n - ref) * pitch, rows[ref][1] + (n - ref) * pitch)
    return out


# ---- question -> regions ----------------------------------------------------------------------------
def regions(question: str, lay: Layout) -> Optional[Selection]:
    q = question.lower()
    pad = 0.006
    if "sketch" in q:
        if lay.sketch is None:
            return None
        return Selection([lay.sketch], [(0.03, 0.97)], "sketch", "the sketch panel of the form (section 13)")
    who = re.search(r"driver ([ab])\b|vehicle ([ab])\b", q)
    side = (who.group(1) or who.group(2)) if who else None
    if side is None or side not in lay.cols or "tick" not in q:
        return None
    col = lay.cols[side]
    m = re.search(r"circumstance (\d{1,2})\b|box (\d{1,2})\b", q)
    if m:  # did X tick N
        n = int(m.group(1) or m.group(2))
        if n not in lay.rows:
            return None
        ctx = int(os.environ.get("ANCHOR_CONTEXT_ROWS", "1"))  # rows shown above/below row N
        lo, hi = max(1, n - ctx), min(17, n + ctx)
        label = (lay.label_x0 - 0.008, min(0.5, lay.label_x1.get(n, lay.label_x0 + 0.25) + 0.01))
        return Selection([(lay.rows[lo][0] - pad, lay.rows[hi][1] + pad)], [col, label], "tick_row",
                         f"driver {side.upper()}'s tick boxes for circumstances {lo}-{hi}, next to their labels (same rows); "
                         f"look at the box on the row labelled {n}: a mark inside means ticked, an empty box means not ticked")
    num = (lay.label_x0 - 0.008, lay.label_x0 + 0.035)
    return Selection([(lay.rows[1][0] - pad, lay.rows[17][1] + pad)], [col, num], "ticks",
                     f"driver {side.upper()}'s tick boxes next to the circumstance numbers 1-17 (same rows); "
                     "a mark inside a box means ticked, an empty box means not ticked")


MIN_DESKEW_DEG, MAX_DESKEW_DEG = 0.7, 10.0


def tilt_deg(spans: list[dict], size: tuple[int, int]) -> Optional[float]:
    """Page tilt from the two 'VEHICLE A' / 'VEHICLE B' headers (same signal as pipeline.ocr's alignment).
    Returned in PIL's rotate() convention: rotating the page by this angle makes the headers level."""
    import math

    from pipeline.ocr import header_pairs

    pairs = header_pairs(spans)  # same-height pairs, top first (layouts may repeat the headers)
    if not pairs:
        return None
    a, b = pairs[0]
    (xa, ya), (xb, yb) = [((q[0] + q[2]) / 2 * size[0], (q[1] + q[3]) / 2 * size[1]) for q in (a, b)]
    if xb <= xa:
        return None
    return math.degrees(math.atan2(yb - ya, xb - xa))  # y grows downwards: positive = right side lower


def unrotate_box(box: list[float], angle: float, size: tuple[int, int]) -> list[float]:
    """Box on the deskewed page (rotated by `angle` about the centre, same size) -> box on the original page."""
    import math

    w, h = size
    cx, cy = w / 2, h / 2
    a = math.radians(-angle)  # the page was rotated counter-clockwise by `angle`; rotate back by -angle
    pts = []
    for x, y in ((box[0], box[1]), (box[2], box[1]), (box[0], box[3]), (box[2], box[3])):
        dx, dy = x * w - cx, y * h - cy
        ox = cx + dx * math.cos(a) + dy * math.sin(a)
        oy = cy - dx * math.sin(a) + dy * math.cos(a)
        pts.append((ox / w, oy / h))
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return [round(max(0.0, min(xs)), 4), round(max(0.0, min(ys)), 4),
            round(min(1.0, max(xs)), 4), round(min(1.0, max(ys)), 4)]


def select(image: Image.Image, question: str, deskew: bool = True) -> Optional[Selection]:
    spans, ms = ocr_spans(image)
    page, angle = image, 0.0
    if deskew:
        t = tilt_deg(spans, image.size)
        if t is not None and MIN_DESKEW_DEG <= abs(t) <= MAX_DESKEW_DEG:
            angle = t
            page = image.rotate(angle, resample=Image.BICUBIC, expand=False, fillcolor=(255, 255, 255))
            spans, ms2 = ocr_spans(page)
            ms += ms2
    lay = layout(spans, page)
    if lay is None:  # built-in rules do not read this layout: try a declarative template (pipeline/templates)
        from pipeline import templates
        lay = templates.layout(spans, page)
        if lay is None and deskew and not angle and os.environ.get("ANCHOR_TEMPLATE_DESKEW") == "1":  # off by default (partial crops, msg 102)
            t = templates.tilt_deg(spans, image.size)
            if t is not None and MIN_DESKEW_DEG <= abs(t) <= MAX_DESKEW_DEG:
                page2 = image.rotate(t, resample=Image.BICUBIC, expand=False, fillcolor=(255, 255, 255))
                spans2, ms2 = ocr_spans(page2)
                lay = templates.layout(spans2, page2, col_half=0.03)
                if lay is not None:
                    page, angle, spans, ms = page2, t, spans2, ms + ms2
    sel = regions(question, lay) if lay else None
    if sel:
        sel.ocr_ms, sel.spans, sel.image, sel.angle = ms, spans, page, angle
    return sel


# ---- harness / app pipeline ------------------------------------------------------------------------
def answer(image: Image.Image, question: str, prior: Optional[PipelineResult] = None,
           model: Optional[str] = None, call=None) -> PipelineResult:
    """OCR anchors -> one zoom call via pipeline.visual.zoom_answer (same prompt/mapping as the model-chosen zoom).
    No anchor -> a 'fallback' step, so a cascade or the router can continue to the overview."""
    from pipeline.visual import DEFAULT_MODEL, zoom_answer

    model = model or os.environ.get("EVAL_MODEL") or DEFAULT_MODEL
    res = prior if prior is not None else PipelineResult(answer=None, abstained=True)
    try:
        sel = select(image, question)
    except Exception as e:
        sel, res.error = None, f"anchor: {type(e).__name__}: {e}"
    if sel is None:
        res.pipeline = res.pipeline or "anchor_crop"
        res.route.append(RouteStep("fallback", target="overview", note="no OCR anchor for this question"))
        return res
    res.usage.append(Usage(len(res.route), "local", "Apple Vision OCR (anchor)", latency_ms=sel.ocr_ms))
    n0 = len(res.route)
    out = zoom_answer(sel.image, question, sel.rows, sel.cols, prior=res, model=model, look_for=sel.note,
                      target=f"anchor:{sel.kind}" + (f" deskew {sel.angle:+.1f}deg" if sel.angle else ""),
                      call=call, name="anchor_crop")
    if sel.angle:  # boxes refer to the deskewed page: map them back to the original image
        for e in out.evidence_boxes:
            e.box = unrotate_box(e.box, sel.angle, image.size)
        for st in out.route[n0:]:
            if st.box:
                st.box = unrotate_box(st.box, sel.angle, image.size)
    return out


def factory():
    """run_eval: --pipelines pipeline.anchor:factory   (model from EVAL_MODEL, e.g. local:Qwen/...)"""
    from eval.pipelines.compose import from_answer_fn

    return from_answer_fn(answer, "anchor_crop")


def factory_then_overview():
    """anchor crop, and the model-chosen overview -> zoom route when no anchor is found."""
    from eval.pipelines.compose import cascade, from_answer_fn
    from pipeline.visual import eval_pipeline

    return cascade(from_answer_fn(answer, "anchor_crop"), eval_pipeline(), "anchor_then_overview")


# ---- pixel tick check: a model-free second opinion on tick questions ----------------------------------------
# On a configured layout the anchor knows where each tick box is. Ink inside a box (outline excluded) says whether
# it is ticked. Exploratory: correct on 96/96 tick questions of the four synthetic accident layouts at full scan
# resolution (clean, JPEG q40, 2 and 5 degree tilt), but wrong at 1024 px and on simulated phone photos, so it only
# runs when the page's long side is >= TICK_CHECK_MIN_PX and otherwise says it is unavailable (message 142).
TICK_CHECK_MIN_PX = 1500


def _ink_per_row(page, lay, side, shrink=0.28):
    import numpy as np

    g = np.asarray(page.convert("L"), dtype=np.float32)
    h_img, w_img = g.shape
    x0, x1 = lay.cols[side]
    ks = sorted(lay.rows)
    pitch = (lay.rows[ks[-1]][0] - lay.rows[ks[0]][0]) / max(1, ks[-1] - ks[0])
    out = {}
    for n, (y0, y1) in lay.rows.items():
        c = (y0 + y1) / 2  # cell = row centre +- 0.55 pitch, so the whole box is inside even if the text is short
        cell = g[int((c - 0.55 * pitch) * h_img):int((c + 0.55 * pitch) * h_img), int(x0 * w_img):int(x1 * w_img)]
        if cell.size == 0:
            continue
        dark = cell < 180
        ys, xs = np.where(dark.mean(1) > 0.35)[0], np.where(dark.mean(0) > 0.35)[0]
        if len(ys) >= 2 and len(xs) >= 2:
            by0, by1, bx0, bx1 = ys.min(), ys.max(), xs.min(), xs.max()
        else:
            by0, by1, bx0, bx1 = 0, cell.shape[0] - 1, 0, cell.shape[1] - 1
        bh, bw = by1 - by0, bx1 - bx0
        inner = cell[by0 + int(bh * shrink):by1 - int(bh * shrink) + 1, bx0 + int(bw * shrink):bx1 - int(bw * shrink) + 1]
        out[n] = float((inner < 180).mean()) if inner.size else 0.0
    return out


def tick_check(image, question: str) -> dict:
    """{'available': bool, 'reason': str, 'kind': 'ticks'|'tick_row', 'side': 'a'|'b', 'ticked': [rows],
    'row': n (tick_row only), 'answer': str}. Never raises; declines with a reason instead."""
    try:
        sel = select(image, question)
    except Exception as e:  # OCR helper missing etc.
        return {"available": False, "reason": f"no OCR layout ({type(e).__name__})"}
    if sel is None or sel.kind not in ("ticks", "tick_row"):
        return {"available": False, "reason": "not a tick question on a configured layout"}
    page = sel.image
    if max(page.size) < TICK_CHECK_MIN_PX:
        return {"available": False, "reason": f"page below {TICK_CHECK_MIN_PX} px: pixel check not reliable at this resolution"}
    spans, _ = ocr_spans(page)
    lay = layout(spans, page)
    if lay is None:
        from pipeline import templates
        lay = templates.layout(spans, page)
    q = question.lower()
    who = re.search(r"driver ([ab])\b|vehicle ([ab])\b", q)
    side = (who.group(1) or who.group(2)) if who else None
    if lay is None or side not in lay.cols:
        return {"available": False, "reason": "tick column not found"}
    ink = _ink_per_row(page, lay, side)
    vals = sorted(ink.values())
    thr = max(0.08, vals[len(vals) // 2] * 3 + 0.04)
    ticked = sorted(n for n, v in ink.items() if v > thr)
    out = {"available": True, "reason": "", "kind": sel.kind, "side": side, "ticked": ticked}
    if sel.kind == "tick_row":
        m = re.search(r"circumstance (\d{1,2})\b|box (\d{1,2})\b", q)
        n = int(m.group(1) or m.group(2)) if m else None
        out["row"] = n
        out["answer"] = "yes" if n in ticked else "no"
    else:
        out["answer"] = ", ".join(map(str, ticked)) if ticked else "none"
    return out

