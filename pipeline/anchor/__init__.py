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


def layout(spans: list[dict]) -> Optional[Layout]:
    head = _find(spans, lambda t, b: re.match(r"^12\s*[.,]?\s*circumstances", t, re.I) is not None)
    if len(head) != 1:
        return None
    top = head[0]["box"][3]
    sk = _find(spans, lambda t, b: re.match(r"^13\s*[.,]?\s*sketch", t, re.I) is not None)
    bottom = sk[0]["box"][1] if len(sk) == 1 else 1.0

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
    a = _find(spans, lambda t, b: t.upper() == "A" and hdr_band[0] <= b[1] <= hdr_band[1] + 0.01 and b[0] < 0.5)
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
    b_ = _find(spans, lambda t, b: t.upper() == "B" and hdr_band[0] <= b[1] <= hdr_band[1] + 0.01 and b[0] > 0.5)
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
    sketch = (sk[0]["box"][3] + 0.003, min(1.0, sk[0]["box"][3] + 0.22)) if len(sk) == 1 else None
    return Layout(rows, label_x0, x1s, cols, sketch)


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
        lo, hi = max(1, n - 1), min(17, n + 1)
        label = (lay.label_x0 - 0.008, min(0.5, lay.label_x1.get(n, lay.label_x0 + 0.25) + 0.01))
        return Selection([(lay.rows[lo][0] - pad, lay.rows[hi][1] + pad)], [col, label], "tick_row",
                         f"driver {side.upper()}'s tick boxes for circumstances {lo}-{hi}, next to their labels (same rows)")
    num = (lay.label_x0 - 0.008, lay.label_x0 + 0.035)
    return Selection([(lay.rows[1][0] - pad, lay.rows[17][1] + pad)], [col, num], "ticks",
                     f"driver {side.upper()}'s tick boxes next to the circumstance numbers 1-17 (same rows)")


def select(image: Image.Image, question: str) -> Optional[Selection]:
    spans, ms = ocr_spans(image)
    lay = layout(spans)
    sel = regions(question, lay) if lay else None
    if sel:
        sel.ocr_ms, sel.spans = ms, spans
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
    return zoom_answer(image, question, sel.rows, sel.cols, prior=res, model=model, look_for=sel.note,
                       target=f"anchor:{sel.kind}", call=call, name="anchor_crop")


def factory():
    """run_eval: --pipelines pipeline.anchor:factory   (model from EVAL_MODEL, e.g. local:Qwen/...)"""
    from eval.pipelines.compose import from_answer_fn

    return from_answer_fn(answer, "anchor_crop")


def factory_then_overview():
    """anchor crop, and the model-chosen overview -> zoom route when no anchor is found."""
    from eval.pipelines.compose import cascade, from_answer_fn
    from pipeline.visual import eval_pipeline

    return cascade(from_answer_fn(answer, "anchor_crop"), eval_pipeline(), "anchor_then_overview")
