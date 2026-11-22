"""Re-typesetting: OCR the page locally, redraw the text lines as a small clean image that keeps the 2D layout,
send that instead of the photo.   eval: --pipelines pipeline.retype:factory   (env RETYPE_FONT=16, RETYPE_W=800)"""
from __future__ import annotations

import os
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from eval.schema import PipelineResult, RouteStep, Usage

SYSTEM = (
    "The image is NOT the original document: it is a re-typeset rendering of the document's OCR text, with each text "
    "line placed at its original relative position so rows and columns of tables stay aligned (empty vertical space "
    "removed). Answer the question from it. Copy the text exactly as printed, answer briefly. Reply with JSON only: "
    '{"answer": "<short answer>", "abstain": false}; if the rendering does not contain the answer, '
    '{"answer": null, "abstain": true}.'
)


def _font(size):
    for p in ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Courier New.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass
    return ImageFont.load_default()


def retype(lines: list[dict], font_px: int = 16, width: int = 800) -> Image.Image:
    f = _font(font_px)
    d0 = ImageDraw.Draw(Image.new("RGB", (4, 4)))
    # group into rows by vertical centre
    sp = sorted(lines, key=lambda s: (s["box"][1] + s["box"][3]) / 2)
    rows: list[list[dict]] = []
    for s in sp:
        cy = (s["box"][1] + s["box"][3]) / 2
        h = max(0.004, s["box"][3] - s["box"][1])
        if rows:
            r = rows[-1]
            rcy = sum((t["box"][1] + t["box"][3]) / 2 for t in r) / len(r)
            if abs(cy - rcy) < 0.5 * h:
                r.append(s)
                continue
        rows.append([s])
    x_lo = min(s["box"][0] for s in lines)
    x_hi = max(s["box"][2] for s in lines)
    span = max(1e-3, x_hi - x_lo)
    pad, lh = 6, int(font_px * 1.25)
    placed: list[tuple[int, int, str]] = []
    maxw = 0
    y = pad
    prev_cy, prev_h = None, None
    for r in rows:
        r.sort(key=lambda s: s["box"][0])
        cy = sum((t["box"][1] + t["box"][3]) / 2 for t in r) / len(r)
        h = sum(t["box"][3] - t["box"][1] for t in r) / len(r)
        if prev_cy is not None and (cy - prev_cy) > 2.2 * max(h, prev_h):
            y += lh // 2  # keep a hint of a big gap, drop the rest
        x_end = 0
        for s in r:
            x = int(pad + (s["box"][0] - x_lo) / span * width)
            x = max(x, x_end + (int(font_px * 0.6) if x_end else 0))
            t = s["text"].strip()
            placed.append((x, y, t))
            x_end = x + int(d0.textlength(t, font=f))
        maxw = max(maxw, x_end)
        y += lh
        prev_cy, prev_h = cy, h
    img = Image.new("RGB", (maxw + pad, y + pad), "white")
    d = ImageDraw.Draw(img)
    for x, yy, t in placed:
        d.text((x, yy), t, font=f, fill="black")
    return img


def answer(image, question: str, prior: Optional[PipelineResult] = None, model: Optional[str] = None,
           call=None) -> PipelineResult:
    import time

    from eval.backends import get
    from pipeline.general import _lines
    from pipeline.ocr import recognize_page
    from pipeline.visual import DEFAULT_MODEL, parse

    model = model or os.environ.get("EVAL_MODEL") or DEFAULT_MODEL
    res = prior if prior is not None else PipelineResult(answer=None, abstained=True)
    res.pipeline = (res.pipeline + "+" if res.pipeline else "") + "retype"
    t0 = time.perf_counter()
    spans, _ = recognize_page(image)
    lines = _lines(spans)
    res.route.append(RouteStep("ocr", note=f"{len(lines)} OCR lines"))
    res.usage.append(Usage(len(res.route) - 1, "local", "Apple Vision OCR", latency_ms=(time.perf_counter() - t0) * 1000))
    if not lines:
        res.error, res.abstained = "no OCR text", True
        return res
    img = retype(lines, int(os.environ.get("RETYPE_FONT", "16")), int(os.environ.get("RETYPE_W", "800")))
    if os.environ.get("RETYPE_SAVE"):
        img.save(os.path.join(os.environ["RETYPE_SAVE"], f"{abs(hash(question)) % 10**8}.png"))
    res.route.append(RouteStep("zoom", target="retyped", note=f"{img.width}x{img.height}px"))
    be, _ = get(model)
    try:
        reply, usage, stop = be.call([be.image_block(img), {"type": "text", "text": f"Question: {question}"}],
                                     step_index=len(res.route) - 1, system=SYSTEM, model=model,
                                     images_px=[[img.width, img.height]])
    except Exception as e:
        res.error, res.abstained = f"{type(e).__name__}: {e}", True
        return res
    res.usage.append(usage)
    dd = parse(reply)
    ans = dd.get("answer")
    ab = stop == "refusal" or bool(dd.get("abstain")) or ans is None
    res.answer, res.abstained = (None if ab else str(ans)), ab
    res.route.append(RouteStep("abstain" if ab else "answer"))
    return res


def factory():
    from eval.pipelines.compose import from_answer_fn

    return from_answer_fn(answer, "retype")
