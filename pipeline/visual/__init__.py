"""Visual path: low-res overview with a labelled grid -> zoom into original pixels -> grounded answer.

    from pipeline.visual import answer
    result = answer(pil_image, question, prior=ocr_fallback_result)   # -> eval.schema.PipelineResult

Each step is a *fresh* single-turn call: the overview image is never re-sent with the crop. The
overview call passes a short `look_for` note to the zoom call instead. Grid cells are labelled
R<row>C<col> (not A1/B3: "A"/"B" are vehicle names and 1-17 are box numbers on the accident form).

Config (keyword args or eval factories below):
  overview_side   long side of the overview in px (default 512)
  grid            overview grid (rows, cols), default (8, 6); cells may be non-adjacent -> row-aligned mosaic
  max_zooms       zoom budget; with budget left, a crop carries a 2x2 sub-grid so the model can zoom again
  overview_model / zoom_model   may differ ("cheap overview, strong zoom", message 010)
  max_crop_side   a crop larger than this (long side) is downscaled and the note says so
  call            fake backend for tests (anthropic_backend.call signature); otherwise each step's backend
                  is chosen from its model string by eval.backends.get

Eval harness:  python -m eval.run_eval --items ... --pipelines pipeline.visual:factory
"""
from __future__ import annotations

import json
import os
import re
from typing import Callable, Optional

from PIL import Image, ImageDraw, ImageFont

from eval.schema import EvalItem, EvidenceBox, PipelineResult, RouteStep

Region = tuple[float, float, float, float]  # normalized on the ORIGINAL image

# Model strings follow eval/backends: "claude-…" (Anthropic), "or:<id>" (OpenRouter), "local:<id>" (vLLM on RCP).
DEFAULT_MODEL = os.environ.get("EVAL_MODEL", "claude-opus-5-5")
CALL_OVERRIDE: Optional[Callable] = None  # tests only: replaces the backend when `call` is not given
VIEW_SINK: Optional[Callable] = None      # app: called as VIEW_SINK(step, image_sent) for display

_FORMAT = (
    'Reply with ONE JSON object and nothing else, either\n'
    '{"action": "answer", "answer": string or null, "abstain": boolean, "box": [x0, y0, x1, y1] or null}\n'
    'or\n'
    '{"action": "zoom", "cells": ["R1C2", ...], "look_for": "what to inspect, in a few words"}\n'
    "box is the region of THIS image that supports the answer, normalized 0-1, origin top-left. "
    "Set abstain to true (answer null) if the image cannot contain the answer. Keep answers short."
)

SYSTEM_OVERVIEW = (
    "You see a DOWNSCALED overview of a document or photo with a faint grid. Row labels R1, R2, ... "
    "are in the left margin and column labels C1, C2, ... in the top margin; cell R<row>C<col> is "
    "where they cross. Answer the question only if the "
    "evidence is clearly legible in this overview. If it depends on small text, checkboxes, ticks or "
    "fine detail, do not guess: request a zoom on the few cells that contain all of the needed "
    "evidence. Cells need not be adjacent: to read a small mark AND the label on the same row far "
    "away, list both the mark cells and the label cells; they are stitched together row-aligned. " + _FORMAT
)

SYSTEM_OVERVIEW_FORCE = (
    "You see a DOWNSCALED overview of a document or photo with a faint grid. Row labels R1, R2, ... "
    "are in the left margin and column labels C1, C2, ... in the top margin; cell R<row>C<col> is "
    "where they cross. The overview is too small to read details reliably, so do NOT answer yet: choose "
    "the few cells that contain all of the evidence needed for the question. Cells need not be adjacent: "
    "to read a small mark AND its label on the same row far away, list both. "
    'Reply with ONE JSON object and nothing else: {"action": "zoom", "cells": ["R1C2", ...], '
    '"look_for": "what to inspect, in a few words"}'
)

SYSTEM_ZOOM = (
    "You see a FULL-RESOLUTION crop of part of a document or photo, chosen because it should contain "
    "the evidence for the question. {grid_note}" + _FORMAT
)
_GRID_NOTE = ("A faint 2x2 grid is drawn on it (row labels R1-R2 in the left margin, column labels C1-C2 "
              "in the top margin); if the evidence is still too small you may zoom "
              "once more on 1-2 adjacent cells. ")
_NO_GRID_NOTE = 'Zooming is no longer possible: you must use action "answer" (abstain if unsure). '
_MOSAIC_NOTE = ("Grey separator lines join non-adjacent parts of the page; parts in the same row band are "
                "row-aligned, so a mark and a label at the same height belong to the same row. ")

_CELL = re.compile(r"R(\d+)\s*C(\d+)", re.I)


# ---------------------------------------------------------------------------------------- drawing
def _font(size: int):
    for name in ("/System/Library/Fonts/Helvetica.ttc", "/System/Library/Fonts/Supplemental/Arial.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def draw_grid(img: Image.Image, rows: int, cols: int) -> Image.Image:
    """img with faint grid lines and the labels in a MARGIN (R1..Rn on the left, C1..Cm on top), so no
    label covers content. A cell is named R<row>C<col>. The margin is not part of any coordinate:
    callers map boxes on the un-padded view."""
    w, h = img.size
    f = _font(max(10, min(16, min(w / cols, h / rows) // 3)))
    ml, mt = int(f.size * 2.4), int(f.size * 1.5)
    out = Image.new("RGB", (w + ml, h + mt), "white")
    out.paste(img.convert("RGB"), (ml, mt))
    d = ImageDraw.Draw(out, "RGBA")
    for i in range(1, cols):
        x = ml + w * i / cols
        d.line([(x, mt), (x, mt + h)], fill=(220, 0, 120, 110), width=1)
    for i in range(1, rows):
        y = mt + h * i / rows
        d.line([(ml, y), (ml + w, y)], fill=(220, 0, 120, 110), width=1)
    for c in range(cols):
        label = f"C{c + 1}"
        cx = ml + w * (c + 0.5) / cols
        d.text((cx - d.textlength(label, font=f) / 2, 1), label, fill=(200, 0, 110), font=f)
    for r in range(rows):
        label = f"R{r + 1}"
        cy = mt + h * (r + 0.5) / rows
        d.text((2, cy - f.size / 2), label, fill=(200, 0, 110), font=f)
    out.info["pad"] = (ml, mt, w, h)
    return out


def normalize_box(box: list[float], shown: Image.Image) -> list[float]:
    """Some models (e.g. Qwen2.5-VL) answer in absolute pixels of the image they saw, not 0-1.
    Treat a box with any coordinate > 1.5 as pixels of `shown` and normalize it."""
    if max(box) <= 1.5:
        return box
    W, H = shown.size
    return [box[0] / W, box[1] / H, box[2] / W, box[3] / H]


def unpad_box(box: list[float], shown: Image.Image) -> list[float]:
    """Box normalized on a draw_grid() image (margins included) -> normalized on the un-padded view."""
    if "pad" not in shown.info:
        return box
    ml, mt, w, h = shown.info["pad"]
    W, H = shown.size
    return [(box[0] * W - ml) / w, (box[1] * H - mt) / h, (box[2] * W - ml) / w, (box[3] * H - mt) / h]


def _resize_long(img: Image.Image, side: int) -> Image.Image:
    s = min(1.0, side / max(img.size))
    return img if s == 1.0 else img.resize((max(1, round(img.width * s)), max(1, round(img.height * s))),
                                           Image.LANCZOS)


# ---------------------------------------------------------------------------------------- geometry
# A View is a set of row bands x column bands of the ORIGINAL image (normalized spans), stitched in
# order with thin separators. A contiguous zoom is the 1 x 1 case; selecting e.g. the label column and
# the tick column over the same rows gives a row-aligned mosaic that keeps the row labels next to the
# ticks without paying for everything in between.
Span = tuple[float, float]
SEP_PX = 6


def _merge(spans: list[Span], eps: float = 1e-6) -> list[Span]:
    out: list[list[float]] = []
    for a, b in sorted(spans):
        if out and a <= out[-1][1] + eps:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [(a, b) for a, b in out]


class Axis:
    """1-D piecewise map between stitched-image coordinates and original-image coordinates."""

    def __init__(self, spans: list[Span], orig_px: int, scale: float = 1.0):
        self.spans = _merge(spans)
        self.lens = [max(1, round((b - a) * orig_px * scale)) for a, b in self.spans]
        self.total = sum(self.lens) + SEP_PX * (len(self.spans) - 1)

    def offsets(self) -> list[int]:
        out, o = [], 0
        for n in self.lens:
            out.append(o)
            o += n + SEP_PX
        return out

    def to_orig(self, s0: float, s1: float) -> list[Span]:
        """Stitched interval (normalized to the stitched length) -> original intervals, one per band hit."""
        p0, p1 = sorted((s0 * self.total, s1 * self.total))
        res = []
        for (a, b), off, n in zip(self.spans, self.offsets(), self.lens):
            lo, hi = max(p0, off), min(p1, off + n)
            if hi > lo:
                res.append((a + (lo - off) / n * (b - a), a + (hi - off) / n * (b - a)))
        return res


class View:
    def __init__(self, img: Image.Image, rows: list[Span], cols: list[Span], max_side: int = 1568):
        native = Axis(cols, img.width), Axis(rows, img.height)
        scale = min(1.0, max_side / max(native[0].total, native[1].total))
        self.scale = scale
        self.x, self.y = Axis(cols, img.width, scale), Axis(rows, img.height, scale)
        self.image = Image.new("RGB", (self.x.total, self.y.total), (150, 150, 150))
        for (ya, yb), oy, ny in zip(self.y.spans, self.y.offsets(), self.y.lens):
            for (xa, xb), ox, nx in zip(self.x.spans, self.x.offsets(), self.x.lens):
                piece = img.crop((round(xa * img.width), round(ya * img.height),
                                  round(xb * img.width), round(yb * img.height)))
                self.image.paste(piece.resize((nx, ny), Image.LANCZOS) if piece.size != (nx, ny) else piece,
                                 (ox, oy))

    @property
    def bounds(self) -> Region:
        return (self.x.spans[0][0], self.y.spans[0][0], self.x.spans[-1][1], self.y.spans[-1][1])

    @property
    def mosaic(self) -> bool:
        return len(self.x.spans) > 1 or len(self.y.spans) > 1

    def boxes_to_orig(self, box: list[float]) -> list[list[float]]:
        b = [min(1.0, max(0.0, float(v))) for v in box]
        return [[round(x0, 4), round(y0, 4), round(x1, 4), round(y1, 4)]
                for y0, y1 in self.y.to_orig(b[1], b[3]) for x0, x1 in self.x.to_orig(b[0], b[2])]

    def select(self, cells: list[str], rows: int, cols: int):
        """Cells of a rows x cols grid drawn over THIS view -> (row spans, col spans) in original coords."""
        rc = [(int(m.group(1)), int(m.group(2))) for c in cells if (m := _CELL.search(str(c)))]
        rc = [(r, c) for r, c in rc if 1 <= r <= rows and 1 <= c <= cols]
        if not rc:
            return None
        ys = [sp for r in {r for r, _ in rc} for sp in self.y.to_orig((r - 1) / rows, r / rows)]
        xs = [sp for c in {c for _, c in rc} for sp in self.x.to_orig((c - 1) / cols, c / cols)]
        return (_merge(ys), _merge(xs)) if ys and xs else None


def cells_region(cells: list[str], n: int, parent: Region = (0.0, 0.0, 1.0, 1.0)) -> Optional[Region]:
    """Bounding box of the named cells of an n x n grid over `parent` (kept for callers/tests)."""
    rc = [(int(m.group(1)), int(m.group(2))) for c in cells if (m := _CELL.search(str(c)))]
    rc = [(r, c) for r, c in rc if 1 <= r <= n and 1 <= c <= n]
    if not rc:
        return None
    r0, r1 = min(r for r, _ in rc) - 1, max(r for r, _ in rc)
    c0, c1 = min(c for _, c in rc) - 1, max(c for _, c in rc)
    px0, py0, px1, py1 = parent
    pw, ph = px1 - px0, py1 - py0
    return (px0 + pw * c0 / n, py0 + ph * r0 / n, px0 + pw * c1 / n, py0 + ph * r1 / n)


def parse(text: str) -> dict:
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return {"action": "answer", "answer": (text or "").strip() or None, "abstain": not (text or "").strip()}
    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError:
        return {"action": "answer", "answer": text.strip() or None, "abstain": False}
    if not isinstance(d, dict):
        return {"action": "answer", "answer": str(d), "abstain": False}
    return d


def _valid_box(b) -> bool:
    return isinstance(b, list) and len(b) == 4 and all(isinstance(v, (int, float)) for v in b) \
        and b[2] > b[0] and b[3] > b[1]


# ---------------------------------------------------------------------------------------- pipeline
def answer(
    image: Image.Image,
    question: str,
    prior: Optional[PipelineResult] = None,
    *,
    overview_side: int = 512,
    grid: tuple[int, int] = (8, 6),
    sub_grid: tuple[int, int] = (2, 2),
    max_zooms: int = 1,
    overview_model: str = DEFAULT_MODEL,
    zoom_model: str = DEFAULT_MODEL,
    max_crop_side: int = 1568,
    force_zoom: bool = False,
    call: Optional[Callable] = None,
    name: Optional[str] = None,
) -> PipelineResult:
    injected = call or CALL_OVERRIDE  # tests: one fake for every step, Anthropic-style image blocks

    def backend(model: str):
        if injected is not None:
            from eval.backends.anthropic_backend import image_block
            return image_block, injected, model
        from eval.backends import get
        be, bare = get(model)
        return be.image_block, be.call, model

    img = image.convert("RGB")
    res = prior if prior is not None else PipelineResult(answer=None)
    res.pipeline = (f"{prior.pipeline}+" if prior is not None and prior.pipeline else "") + (
        name or f"visual_ov{overview_side}_g{grid[0]}x{grid[1]}_z{max_zooms}")
    res.answer, res.abstained = None, False

    def ask(view_img: Image.Image, system: str, text: str, model: str, step: str, target, box, note=""):
        res.route.append(RouteStep(step=step, target=target, box=[round(v, 4) for v in box],
                                   note=f"{view_img.width}x{view_img.height}px to {model}{note}"))
        if VIEW_SINK is not None:
            VIEW_SINK(step, view_img)
        try:
            image_block, call_fn, model_arg = backend(model)
            reply, usage, stop = call_fn([image_block(view_img), {"type": "text", "text": text}],
                                         step_index=len(res.route) - 1, system=system, model=model_arg,
                                         images_px=[[view_img.width, view_img.height]])
        except Exception as e:  # a failed call is a result, not an exception
            res.error = f"{type(e).__name__}: {e}"
            return None
        res.usage.append(usage)
        if stop == "refusal":
            res.error = "refusal"
            return None
        return parse(reply)

    def finish(d: dict, view: Optional[View], source: str, shown: Image.Image) -> PipelineResult:
        ans = d.get("answer")
        abstain = bool(d.get("abstain")) or ans is None
        res.answer, res.abstained = (None if abstain else str(ans)), abstain
        boxes = []
        if _valid_box(d.get("box")) and not abstain:
            boxes = view.boxes_to_orig(unpad_box(normalize_box(d["box"], shown), shown))
        res.route.append(RouteStep(step="abstain" if abstain else "answer", box=boxes[0] if boxes else None))
        res.evidence_boxes += [EvidenceBox(box=b, source=source) for b in boxes]
        return res

    def give_up(note: str) -> PipelineResult:
        res.answer, res.abstained = None, True
        res.route.append(RouteStep(step="abstain", note=note))
        return res

    # 1. overview (the whole image, downscaled, with the labelled grid)
    rows, cols = grid
    ov_view = View(img, [(0.0, 1.0)], [(0.0, 1.0)], max_side=overview_side)
    shown = draw_grid(ov_view.image, rows, cols)
    d = ask(shown, SYSTEM_OVERVIEW_FORCE if force_zoom else SYSTEM_OVERVIEW, question, overview_model,
            "overview", None, ov_view.bounds)
    if d is None:
        return give_up("overview call failed")
    view, look_for = ov_view, ""
    for level in range(max_zooms + 1):
        if d.get("action") != "zoom":
            return finish(d, view, "overview" if level == 0 else "zoom", shown)
        if level == max_zooms:
            return give_up("zoom requested after the zoom budget was spent")
        cells = d.get("cells") or ([d["cell"]] if d.get("cell") else [])
        cells = cells if isinstance(cells, list) else [cells]
        sel = view.select(cells, rows, cols)
        if sel is None:
            return give_up(f"unparseable zoom target {cells!r}")
        view = View(img, sel[0], sel[1], max_side=max_crop_side)
        look_for = str(d.get("look_for") or look_for)
        can_zoom = level + 1 < max_zooms
        rows, cols = sub_grid
        shown = draw_grid(view.image, rows, cols) if can_zoom else view.image
        system = SYSTEM_ZOOM.replace("{grid_note}", (_GRID_NOTE if can_zoom else _NO_GRID_NOTE)
                                     + (_MOSAIC_NOTE if view.mosaic else ""))
        text = f"Question: {question}\nWhat to inspect: {look_for or 'the evidence for the question'}"
        note = (" mosaic" if view.mosaic else "") + (" downscaled" if view.scale < 1 else "")
        d = ask(shown, system, text, zoom_model, "zoom", ",".join(map(str, cells)), view.bounds, note)
        if d is None:
            return give_up("zoom call failed")
    return finish(d, view, "zoom", shown)


def zoom_answer(
    image: Image.Image,
    question: str,
    row_spans: list[Span],
    col_spans: list[Span],
    prior: Optional[PipelineResult] = None,
    *,
    model: str = DEFAULT_MODEL,
    max_crop_side: int = 1568,
    look_for: str = "",
    target: str = "selected regions",
    call: Optional[Callable] = None,
    name: str = "zoom_answer",
) -> PipelineResult:
    """One zoom call on regions chosen by someone else (e.g. an OCR-anchored selector), no overview.

    row_spans / col_spans: normalized [(y0, y1), ...] / [(x0, x1), ...] on the ORIGINAL image. Several spans
    give the same row-aligned mosaic as a model-chosen selection. The route gets a "zoom" step whose box is
    the bounding box of the selection (score it with eval.metrics.zoom_coverage), then answer/abstain.
    """
    injected = call or CALL_OVERRIDE
    if injected is not None:
        from eval.backends.anthropic_backend import image_block
        call_fn = injected
    else:
        from eval.backends import get
        be, _ = get(model)
        image_block, call_fn = be.image_block, be.call
    res = prior if prior is not None else PipelineResult(answer=None)
    res.pipeline = (f"{prior.pipeline}+" if prior is not None and prior.pipeline else "") + name
    view = View(image.convert("RGB"), row_spans, col_spans, max_side=max_crop_side)
    system = SYSTEM_ZOOM.replace("{grid_note}", _NO_GRID_NOTE + (_MOSAIC_NOTE if view.mosaic else ""))
    text = f"Question: {question}\nWhat to inspect: {look_for or 'the evidence for the question'}"
    res.route.append(RouteStep(step="zoom", target=target, box=[round(v, 4) for v in view.bounds],
                               note=f"{view.image.width}x{view.image.height}px to {model}"
                                    + (" mosaic" if view.mosaic else "")))
    if VIEW_SINK is not None:
        VIEW_SINK("zoom", view.image)
    try:
        # A replay oracle that can answer a direct zoom (no overview first) declares `direct_zoom`; it gets the
        # view's spans so it can place its gold box in the crop. Real backends never receive this argument.
        extra = {"view_spans": (view.y.spans, view.x.spans)} if getattr(call_fn, "direct_zoom", False) else {}
        reply, usage, stop = call_fn([image_block(view.image), {"type": "text", "text": text}],
                                     step_index=len(res.route) - 1, system=system, model=model,
                                     images_px=[[view.image.width, view.image.height]], **extra)
    except Exception as e:
        res.error, res.answer, res.abstained = f"{type(e).__name__}: {e}", None, True
        res.route.append(RouteStep(step="abstain", note="zoom call failed"))
        return res
    res.usage.append(usage)
    d = parse(reply)
    ans = d.get("answer")
    abstain = stop == "refusal" or bool(d.get("abstain")) or ans is None or d.get("action") == "zoom"
    res.answer, res.abstained = (None if abstain else str(ans)), abstain
    boxes = view.boxes_to_orig(normalize_box(d["box"], view.image)) if _valid_box(d.get("box")) and not abstain else []
    res.route.append(RouteStep(step="abstain" if abstain else "answer", box=boxes[0] if boxes else None))
    res.evidence_boxes += [EvidenceBox(box=b, source="zoom") for b in boxes]
    return res


# ---------------------------------------------------------------------------------------- eval factories
def eval_pipeline(**cfg):
    """(item, image) -> PipelineResult, for eval/run_eval.py."""
    def run(item: EvalItem, img: Image.Image) -> PipelineResult:
        r = answer(img, item.question, **cfg)
        r.question_id, r.image_id = item.question_id, item.image_id
        return r
    return run


def factory():                      # opus overview + opus zoom, 1 zoom
    return eval_pipeline()


def factory_cheap_overview():       # haiku overview, opus zoom (message 010 hypothesis)
    return eval_pipeline(overview_model="claude-haiku-5-5", name="visual_haikuov_opuszoom")


def factory_force_zoom():          # overview may only choose cells (for models that never zoom)
    return eval_pipeline(force_zoom=True, name="visual_force_zoom")


def factory_split():                # E2: VISUAL_OVERVIEW_MODEL picks cells, VISUAL_ZOOM_MODEL reads the crop
    ov, zm = os.environ["VISUAL_OVERVIEW_MODEL"], os.environ["VISUAL_ZOOM_MODEL"]
    short = lambda m: m.split("/")[-1]
    return eval_pipeline(overview_model=ov, zoom_model=zm, force_zoom=os.environ.get("VISUAL_FORCE_ZOOM") == "1",
                         name=f"visual_ov[{short(ov)}]_zoom[{short(zm)}]"
                              + ("_force" if os.environ.get("VISUAL_FORCE_ZOOM") == "1" else ""))


def factory_two_zooms():
    return eval_pipeline(max_zooms=2, name="visual_ov512_g8x6_z2")
