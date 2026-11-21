"""General vision assistant route: OCR text first, pixels only when needed (owner: claude-andrew-b, message 145).

For any image (homework, worksheets, textbook pages, receipts, forms we did not configure):

1. **OCR** the page locally (Apple Vision, $0), number its lines.
2. **Text call:** send only the numbered OCR lines (no image) to the model. It answers from text and cites the line
   ids it used (their OCR boxes become the evidence), or says it needs the image (a diagram, a tick or circle,
   handwriting OCR missed, colour, position) and names the lines nearest to what must be looked at.
3. **Pixel call (only if asked for):** crop a band around the named lines (full width, from just above the first
   line to well below the last, because diagrams and marks usually sit next to or below their text), or send the
   whole page if no line was named. One `pipeline.visual.zoom_answer` call, same box mapping as the claims route.

    answer(image, question, prior=None, model=None, call=None) -> eval.schema.PipelineResult
    eval:  --pipelines pipeline.general:factory
"""
from __future__ import annotations

import json
import os
from typing import Optional

from eval.schema import EvidenceBox, PipelineResult, RouteStep, Usage

MAX_LINES = 220
BAND_ABOVE, BAND_BELOW = 0.30, 0.30  # crop band around the named lines (page fractions). Drawings sit above their
# labels (axis labels, legends, keys) as often as below their question text: homework_v2 held-out, 8264c05.

SYSTEM_TEXT = (
    "You answer questions about an image using ONLY its OCR text, given as numbered lines [L1], [L2], ... in reading "
    "order. If the lines contain what is needed, answer and cite the ids of the lines you used (at most 6). Put only "
    "the short answer in \"answer\" (a number, word or short phrase); for tutoring questions (solve, explain, check my "
    "work) add a short step-by-step explanation in \"explanation\" (at most 60 words). If the answer depends on "
    "something OCR cannot capture, do not guess: ask for the image and list the ids of the lines nearest to what must "
    "be looked at. That includes: a drawing, diagram, map, graph, chart or picture; which cell of a table is empty or "
    "where things sit in a table or grid; a tick, cross, circle, highlight, sticker, line or arrow (OCR often reads a "
    "tick as V or a cross as X: never decide marks from OCR characters); handwriting that is missing or garbled; "
    "colour; position. Abstain only when the page clearly does not contain that kind of information at all. "
    "Reply with JSON only, one of:\n"
    '{"answer": "...", "explanation": "... (optional)", "lines": [ids]}\n'
    '{"need_image": true, "lines": [ids], "look_for": "what to inspect, in a few words"}\n'
    '{"abstain": true}'
)


def _lines(spans: list[dict]) -> list[dict]:
    """OCR spans in reading order (top to bottom, then left to right), confident ones only."""
    sp = [s for s in spans if s.get("confidence", 0) >= 0.3 and s.get("text", "").strip()]
    sp.sort(key=lambda s: (round((s["box"][1] + s["box"][3]) / 2, 2), s["box"][0]))
    return sp[:MAX_LINES]


def _parse(text: str) -> dict:
    """JSON reply; if it was cut off by the output limit, salvage its fields instead of showing raw JSON."""
    import re

    from pipeline.visual import parse

    d = parse(text)
    ans = d.get("answer")
    if isinstance(ans, str) and ans.lstrip().startswith("{"):
        out: dict = {}
        if re.search(r'"need_image"\s*:\s*true', text):
            out["need_image"] = True
        elif re.search(r'"abstain"\s*:\s*true', text):
            out["abstain"] = True
        m = re.search(r'"answer"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
        if m and not out:
            out["answer"] = json.loads(f'"{m.group(1)}"')
        m = re.search(r'"look_for"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
        if m:
            out["look_for"] = json.loads(f'"{m.group(1)}"')
        m = re.search(r'"lines"\s*:\s*\[([0-9,\sL"]*)', text)
        if m:
            out["lines"] = re.findall(r"\d+", m.group(1))
        return out or {"abstain": True}
    return d


def _band(boxes: list[list[float]]) -> tuple[float, float]:
    y0 = max(0.0, min(b[1] for b in boxes) - BAND_ABOVE)
    y1 = min(1.0, max(b[3] for b in boxes) + BAND_BELOW)
    return y0, y1


def answer(image, question: str, prior: Optional[PipelineResult] = None, model: Optional[str] = None,
           call=None, text_step: bool = True) -> PipelineResult:
    """text_step=False skips the OCR-text call and sends the whole page: for small models that do not reliably ask
    for pixels when text is not enough (Qwen2.5-VL-7B: REPORT_homework_v3_qwen7b.md). OCR still runs (boxes, $0)."""
    from pipeline.ocr import recognize_page
    from pipeline.router import ensure_ocr_bin
    from pipeline.visual import CALL_OVERRIDE, DEFAULT_MODEL, zoom_answer

    model = model or os.environ.get("EVAL_MODEL") or DEFAULT_MODEL
    res = prior if prior is not None else PipelineResult(answer=None, abstained=True)
    res.pipeline = (res.pipeline + "+" if res.pipeline else "") + "general"

    # 1. OCR (local)
    import time

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

    look_for, named = "", None
    if lines and not text_step:
        res.route.append(RouteStep("fallback", target="image", note="small model: whole page (text step off)"))
        return zoom_answer(image, question, [(0.0, 1.0)], [(0.0, 1.0)], prior=res, model=model,
                           look_for="the evidence for the question", target="full page", call=call, name="page")
    if lines:
        # 2. text-only call
        text = "\n".join(f"[L{i + 1}] {s['text'].strip()}" for i, s in enumerate(lines))
        injected = call or CALL_OVERRIDE
        if injected is not None:
            call_fn = injected
        else:
            from eval.backends import get

            be, _ = get(model)
            call_fn = be.call
        res.route.append(RouteStep("native_text", target="OCR text only", note=f"{len(lines)} lines to {model}"))
        try:
            reply, usage, stop = call_fn([{"type": "text", "text": f"OCR lines:\n{text}\n\nQuestion: {question}"}],
                                         step_index=len(res.route) - 1, system=SYSTEM_TEXT, model=model, images_px=[])
        except Exception as e:
            res.error, res.answer, res.abstained = f"{type(e).__name__}: {e}", None, True
            res.route.append(RouteStep("abstain", note="text call failed"))
            return res
        res.usage.append(usage)
        d = _parse(reply)
        ids = [int(str(x).lstrip("Ll")) for x in (d.get("lines") or []) if str(x).lstrip("Ll").isdigit()]
        cited = [lines[i - 1] for i in ids if 1 <= i <= len(lines)]
        if d.get("abstain"):
            res.answer, res.abstained = None, True
            res.route.append(RouteStep("abstain", note="not in the OCR text, and no image needed"))
            return res
        if not d.get("need_image") and d.get("answer") not in (None, ""):
            res.answer, res.abstained = str(d["answer"]), False
            if d.get("explanation"):
                res.route[-1].note = (res.route[-1].note or "") + f" | explanation: {str(d['explanation'])[:600]}"
            for s in cited:
                res.evidence_boxes.append(EvidenceBox([round(v, 4) for v in s["box"]], source="ocr",
                                                      label=s["text"].strip()[:60]))
            res.route.append(RouteStep("answer", note=f"from OCR text, lines {ids}" if ids else "from OCR text"))
            return res
        look_for = str(d.get("look_for") or "")
        named = [s["box"] for s in cited] or None

    # 3. pixels: a band around the named lines, or the whole page
    if named:
        y0, y1 = _band(named)
        rows, target = [(y0, y1)], "near cited lines"
    else:
        rows, target = [(0.0, 1.0)], "full page"
    res.route.append(RouteStep("fallback", target="image", note=f"needs pixels: {look_for or 'not readable from OCR text'}"))
    res = zoom_answer(image, question, rows, [(0.0, 1.0)], prior=res, model=model,
                      look_for=look_for or "the evidence for the question", target=target, call=call,
                      name="pixels")
    # 4. the band was not enough: one more look, at the whole page (a band can miss a drawing far from its labels)
    if res.abstained and not res.error and rows != [(0.0, 1.0)]:
        res.route.append(RouteStep("fallback", target="image", note="band crop was not enough; one look at the whole page"))
        res = zoom_answer(image, question, [(0.0, 1.0)], [(0.0, 1.0)], prior=res, model=model,
                          look_for=look_for or "the evidence for the question", target="full page", call=call,
                          name="page")
    return res


def factory():
    """run_eval: --pipelines pipeline.general:factory   (model from EVAL_MODEL)"""
    from eval.pipelines.compose import from_answer_fn

    return from_answer_fn(answer, "general")
