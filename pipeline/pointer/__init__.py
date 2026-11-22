"""Pointer -> zoom -> escalate route (development).

1. OCR the page (local). 2. POINTER proposes a region likely to hold the answer:
   POINTER_SOURCE=qwen : local Qwen2.5-VL-7B (Ollama) on a low-res text-area crop, asked for a bounding box ($0);
   POINTER_SOURCE=file : 16x16 score grids from the JSON in POINTER_REGIONS ({question_id: [256 floats]}), top-k cells.
3. ZOOM: crop the region (padded 25%) and ask the reader model. 4. Accept only if the answer is printed in the OCR
text; otherwise fall back to the page ladder (pipeline.general._page_call with GENERAL_LADDER=1).

    answer(image, question, prior=None, model=None) -> PipelineResult
    eval:  --pipelines pipeline.pointer:factory
"""
from __future__ import annotations

import json
import os
import re
import time
from typing import Optional

from eval.schema import PipelineResult, RouteStep, Usage

POINTER_MODEL = os.environ.get("POINTER_MODEL", "local:qwen2.5vl:7b")
POINTER_SIDE = int(os.environ.get("POINTER_SIDE", "768"))
QWEN_AREA = float(os.environ.get("QWEN_AREA", "830000"))
PAD, TOPK, GRID = 0.25, 12, 16
MIN_SHORT_CROP = 512
_GRIDS: Optional[dict] = None
_BOXES: Optional[dict] = None
CURRENT_QID: Optional[str] = None  # set by the factory wrapper so the file source can look up the grid

LINE_TOPK, LINE_PAD = int(os.environ.get("POINTER_LINES", "3")), 1.5

PROMPT = ("Find where the answer to this question is printed on the image: {q}\n"
          "Output the bounding box of the text that holds the answer (and its label) as JSON.")


def _file_box(qid):
    global _GRIDS
    if _GRIDS is None:
        _GRIDS = json.load(open(os.environ["POINTER_REGIONS"]))
    g = _GRIDS.get(qid)
    if not g or len(g) != GRID * GRID:
        return None
    top = sorted(range(len(g)), key=lambda i: -g[i])[:TOPK]
    rs, cs = [i // GRID for i in top], [i % GRID for i in top]
    return [min(cs) / GRID, min(rs) / GRID, (max(cs) + 1) / GRID, (max(rs) + 1) / GRID]


def _qwen_box(image, question, rows, cols, res):
    from eval.backends import get

    cw = (cols[0][1] - cols[0][0]) * image.width; ch = (rows[0][1] - rows[0][0]) * image.height
    crop = image.convert("RGB").crop((round(cols[0][0] * image.width), round(rows[0][0] * image.height),
                                      round(cols[0][1] * image.width), round(rows[0][1] * image.height)))
    s = min(1.0, POINTER_SIDE / max(crop.size))
    crop = crop.resize((max(28, round(crop.width * s)), max(28, round(crop.height * s))))
    be, _ = get(POINTER_MODEL)
    reply, usage, _ = be.call([be.image_block(crop), {"type": "text", "text": PROMPT.format(q=question)}],
                              step_index=len(res.route) - 1, model=POINTER_MODEL, images_px=[list(crop.size)],
                              max_tokens=120)
    res.usage.append(usage)
    m = re.search(r"\[\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*\]", reply)
    if not m:
        return None, reply
    b = [float(v) for v in m.groups()]
    if max(b) > 1.5:
        # Measured: Ollama re-scales every image to ~QWEN_AREA pixels (same coordinates for 768 and 1024 px inputs), and
        # Qwen2.5-VL answers in pixels of that internal image, not of the one we sent. Rebuild its size from the aspect.
        k = (QWEN_AREA / (crop.width * crop.height)) ** 0.5
        iw, ih = crop.width * k, crop.height * k
        b = [b[0] / iw, b[1] / ih, b[2] / iw, b[3] / ih]
    b = [min(1.0, max(0.0, v)) for v in b]
    if b[2] - b[0] < 0.01 or b[3] - b[1] < 0.005:
        return None, reply
    return b, reply


def answer(image, question: str, prior: Optional[PipelineResult] = None, model: Optional[str] = None,
           qid: Optional[str] = None) -> PipelineResult:
    from pipeline.general import _content_spans, _in_ocr, _lines, _page_call
    from pipeline.ocr import recognize_page
    from pipeline.router import ensure_ocr_bin
    from pipeline.visual import DEFAULT_MODEL, zoom_answer

    model = model or os.environ.get("EVAL_MODEL") or DEFAULT_MODEL
    res = prior if prior is not None else PipelineResult(answer=None, abstained=True)
    res.pipeline = (res.pipeline + "+" if res.pipeline else "") + "pointer"
    t0 = time.perf_counter()
    lines: list[dict] = []
    try:
        if ensure_ocr_bin() is None:
            raise RuntimeError("OCR helper unavailable")
        spans, _ = recognize_page(image)
        lines = _lines(spans)
        note = f"{len(lines)} OCR lines"
    except Exception as e:
        note = f"OCR unavailable ({type(e).__name__}); whole page"
    res.route.append(RouteStep("ocr", note=note))
    res.usage.append(Usage(len(res.route) - 1, "local", "Apple Vision OCR", latency_ms=(time.perf_counter() - t0) * 1000))
    rows, cols = _content_spans(image, lines)

    # 2. pointer
    src = os.environ.get("POINTER_SOURCE", "qwen")
    t1 = time.perf_counter()
    box, raw = None, ""
    try:
        if src == "file":
            fb = _file_box(qid or CURRENT_QID)
            if fb:
                box = fb
        elif src == "boxfile":  # precomputed boxes, e.g. from the GRPO-finetuned 7B pointer (message 229)
            global _BOXES
            if _BOXES is None:
                _BOXES = json.load(open(os.environ["POINTER_BOXES"]))
            b = _BOXES.get(qid or CURRENT_QID)
            if b and len(b) == 4 and b[2] > b[0] and b[3] > b[1]:
                box = [max(0.0, float(b[0])), max(0.0, float(b[1])), min(1.0, float(b[2])), min(1.0, float(b[3]))]
        else:
            res.route.append(RouteStep("pointer", target=POINTER_MODEL, note="asking for a bounding box"))
            box, raw = _qwen_box(image, question, rows, cols, res)
            res.route.pop()
    except Exception as e:
        raw = f"{type(e).__name__}: {e}"
    ms = (time.perf_counter() - t1) * 1000
    if src in ("file", "boxfile"):
        res.usage.append(Usage(len(res.route) - 1, "local", "pointer grid", latency_ms=ms))
    ptr_note = f"pointer {src} {ms:.0f}ms box={[round(v, 3) for v in box] if box else None}"
    res.route.append(RouteStep("pointer", target=src, box=None, note=ptr_note + ("" if box else f" | no box: {raw[:80]}")))

    # 3a. line mode (message 224): the head's heat ranks the OCR lines; crop whole lines (full text width), so the
    # crop never cuts through digits. Grids from run.py infer cover the WHOLE image (resized to 448x448).
    if src == "file" and os.environ.get("POINTER_MODE") == "lines" and lines:
        g = _GRIDS.get(qid or CURRENT_QID) if _GRIDS else None
        if g and len(g) == GRID * GRID:
            def heat(b):
                c0, c1 = int(b[0] * GRID), min(GRID - 1, int(b[2] * GRID))
                r0, r1 = int(b[1] * GRID), min(GRID - 1, int(b[3] * GRID))
                cells = [g[r * GRID + c] for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)]
                return max(cells) if cells else -1e9
            ranked = sorted(lines, key=lambda s: -heat(s["box"]))[:LINE_TOPK]
            lh = max(0.008, sum(s["box"][3] - s["box"][1] for s in ranked) / len(ranked))
            spans = sorted((max(0.0, s["box"][1] - LINE_PAD * lh), min(1.0, s["box"][3] + LINE_PAD * lh)) for s in ranked)
            band = [list(spans[0])]
            for a_, b_ in spans[1:]:
                if a_ <= band[-1][1]:
                    band[-1][1] = max(band[-1][1], b_)
                else:
                    band.append([a_, b_])
            res.route.append(RouteStep("pointer", target="lines", note=f"head ranks OCR lines: {[s['text'][:20] for s in ranked]}"))
            res = zoom_answer(image, question, [tuple(b) for b in band], cols, prior=res, model=model,
                              target="pointer lines", name="pointer", max_crop_side=1568)
            if not res.error and not res.abstained and len(re.sub(r'[^A-Za-z0-9]', '', res.answer or '')) >= 2 \
                    and _in_ocr(res.answer, lines):
                res.route.append(RouteStep("answer", note="pointer-lines answer found in the OCR text: accepted"))
                return res
            if res.error:
                return res
            res.route.append(RouteStep("fallback", target="image", note="pointer lines: answer not verified; page ladder"))
            box = None
    # 3. zoom on the (padded) region, mapped back to the full image
    if box:
        # file grids cover the whole image; Qwen boxes are relative to the text-area crop it was shown
        X0, X1, Y0, Y1 = (0.0, 1.0, 0.0, 1.0) if src in ("file", "boxfile") else (cols[0][0], cols[0][1], rows[0][0], rows[0][1])
        bw, bh = box[2] - box[0], box[3] - box[1]
        x0, x1 = max(0.0, box[0] - PAD * bw), min(1.0, box[2] + PAD * bw)
        y0, y1 = max(0.0, box[1] - PAD * bh), min(1.0, box[3] + PAD * bh)
        fx = [(X0 + x0 * (X1 - X0), X0 + x1 * (X1 - X0))]
        fy = [(Y0 + y0 * (Y1 - Y0), Y0 + y1 * (Y1 - Y0))]
        cw_, ch_ = (fx[0][1] - fx[0][0]) * image.width, (fy[0][1] - fy[0][0]) * image.height
        lo, hi = max(1.0, min(cw_, ch_)), max(cw_, ch_)
        side = int(min(hi, 1600, max(768, hi * MIN_SHORT_CROP / lo)))
        crop = image.convert("RGB").crop((round(fx[0][0] * image.width), round(fy[0][0] * image.height),
                                          round(fx[0][1] * image.width), round(fy[0][1] * image.height)))
        up = min(4.0, MIN_SHORT_CROP / max(1.0, min(crop.size)))
        if up > 1.0:  # View never upscales: enlarge the crop so its short side reaches ~512 px
            crop = crop.resize((round(crop.width * up), round(crop.height * up)))
            side = max(side, max(crop.size))
        res = zoom_answer(crop, question, [(0.0, 1.0)], [(0.0, 1.0)], prior=res, model=model, target="pointer region",
                          name="pointer", max_crop_side=side)
        if res.error:
            return res
        if not res.abstained and len(re.sub(r'[^A-Za-z0-9]', '', res.answer or '')) >= 2 and _in_ocr(res.answer, lines):
            res.route.append(RouteStep("answer", note="pointer-region answer found in the OCR text: accepted"))
            return res
        res.route.append(RouteStep("fallback", target="image", note="pointer region: answer not verified; page ladder"))
    else:
        res.route.append(RouteStep("fallback", target="image", note="no pointer region; page ladder"))

    # 4. escalate
    old = os.environ.get("GENERAL_LADDER")
    os.environ["GENERAL_LADDER"] = "1"
    try:
        return _page_call(image, question, res, model, None, lines)
    finally:
        if old is None:
            os.environ.pop("GENERAL_LADDER", None)
        else:
            os.environ["GENERAL_LADDER"] = old


def factory():
    """run_eval: --pipelines pipeline.pointer:factory   (reader from EVAL_MODEL)"""
    from eval.pipelines.compose import from_answer_fn

    def run(item, img):
        global CURRENT_QID
        CURRENT_QID = item.question_id
        return inner(item, img)

    inner = from_answer_fn(lambda img, q: answer(img, q, qid=CURRENT_QID), "pointer")
    return run
