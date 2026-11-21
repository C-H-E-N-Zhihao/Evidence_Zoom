"""Control conditions owned by the harness (see 004/006).

- full_image        : whole image every question; `cache=True` marks the image for prompt caching so repeated
                      questions on one image are billed as cache reads (the fair baseline from 007 §2).
- lowres            : fixed low-resolution overview only (long side `long_side`).
- gold_crop         : human/synthetic gold evidence box cropped from the ORIGINAL pixels at native size, plus
                      `pad` context margin. Upper bound for any zoom policy at its crop size.

All share one prompt and one answer format so differences come from the visual input only.
A pipeline is any callable (item, image) -> PipelineResult; `ocr` and the router live in pipeline/.
"""
from __future__ import annotations

import json
import re
from typing import Callable, Optional

from PIL import Image

from ..backends import anthropic_backend as ab
from ..schema import EvalItem, EvidenceBox, PipelineResult, RouteStep

Pipeline = Callable[[EvalItem, Image.Image], PipelineResult]

SYSTEM = (
    "You answer questions about an image of a document or scene. "
    "Reply with one JSON object and nothing else: "
    '{"answer": string or null, "abstain": boolean, "box": [x0, y0, x1, y1] or null}. '
    "box is the region of THIS image that supports the answer, normalized 0-1, origin top-left. "
    "If the image does not contain enough evidence, set abstain to true and answer to null. Keep answers short."
)


def parse_reply(text: str) -> tuple[Optional[str], bool, Optional[list[float]]]:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return (text.strip() or None), False, None
    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError:
        return text.strip() or None, False, None
    box = d.get("box")
    if not (isinstance(box, list) and len(box) == 4 and all(isinstance(v, (int, float)) for v in box)):
        box = None
    ans = d.get("answer")
    return (None if ans is None else str(ans)), bool(d.get("abstain", False)), box


def _map_box(box: list[float], region: tuple[float, float, float, float]) -> list[float]:
    """Map a box normalized to a crop back to the original image. region = crop box, normalized."""
    rx0, ry0, rx1, ry1 = region
    w, h = rx1 - rx0, ry1 - ry0
    return [rx0 + box[0] * w, ry0 + box[1] * h, rx0 + box[2] * w, ry0 + box[3] * h]


def _ask(
    item: EvalItem,
    img: Image.Image,
    *,
    name: str,
    step: str,
    region: tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0),
    cache: bool = False,
    model: str = ab.DEFAULT_MODEL,
) -> PipelineResult:
    res = PipelineResult(answer=None, pipeline=name, question_id=item.question_id, image_id=item.image_id)
    res.route.append(RouteStep(step=step, box=list(region), note=f"{img.width}x{img.height}px"))
    content = [ab.image_block(img, cache=cache), {"type": "text", "text": item.question}]
    try:
        text, usage, stop = ab.call(content, step_index=0, system=SYSTEM, model=model,
                                    images_px=[[img.width, img.height]])
    except Exception as e:  # recorded, not raised: a failed call is a result
        res.error = f"{type(e).__name__}: {e}"
        return res
    res.usage.append(usage)
    if stop == "refusal":
        res.abstained, res.error = True, "refusal"
        return res
    ans, abstain, box = parse_reply(text)
    res.answer, res.abstained = (None, True) if abstain else (ans, ans is None)
    res.route.append(RouteStep(step="abstain" if res.abstained else "answer"))
    if box:
        res.evidence_boxes.append(EvidenceBox(box=_map_box(box, region), source="model_box"))
    return res


def full_image(cache: bool = False, model: str = ab.DEFAULT_MODEL) -> Pipeline:
    name = f"full_image{'_cached' if cache else ''}"
    return lambda item, img: _ask(item, img, name=name, step="overview", cache=cache, model=model)


def lowres(long_side: int = 512, model: str = ab.DEFAULT_MODEL) -> Pipeline:
    def run(item: EvalItem, img: Image.Image) -> PipelineResult:
        s = min(1.0, long_side / max(img.size))
        small = img.resize((max(1, round(img.width * s)), max(1, round(img.height * s))), Image.LANCZOS)
        return _ask(item, small, name=f"lowres{long_side}", step="overview", model=model)
    return run


def gold_crop(pad: float = 0.05, model: str = ab.DEFAULT_MODEL) -> Pipeline:
    """Union of gold boxes + `pad` (fraction of image size) on each side, native pixels, no resizing."""
    def run(item: EvalItem, img: Image.Image) -> PipelineResult:
        if not item.evidence_boxes:  # unanswerable items have no gold box: fall back to the full image
            return _ask(item, img, name=f"gold_crop_p{pad}", step="fallback", model=model)
        x0 = max(0.0, min(b[0] for b in item.evidence_boxes) - pad)
        y0 = max(0.0, min(b[1] for b in item.evidence_boxes) - pad)
        x1 = min(1.0, max(b[2] for b in item.evidence_boxes) + pad)
        y1 = min(1.0, max(b[3] for b in item.evidence_boxes) + pad)
        crop = img.crop((round(x0 * img.width), round(y0 * img.height), round(x1 * img.width), round(y1 * img.height)))
        return _ask(item, crop, name=f"gold_crop_p{pad}", step="zoom", region=(x0, y0, x1, y1), model=model)
    return run


def mock(item: EvalItem, img: Image.Image) -> PipelineResult:
    """No API call: returns the gold answer and box. For testing the harness and the app end to end."""
    return PipelineResult(
        answer=item.answer, abstained=not item.answerable, pipeline="mock",
        question_id=item.question_id, image_id=item.image_id,
        evidence_boxes=[EvidenceBox(box=b, source="gold_crop") for b in item.evidence_boxes],
        route=[RouteStep(step="answer", note="mock")],
    )


def as_app_answer(pipe: Pipeline) -> Callable[[Image.Image, str], dict]:
    """Adapter to app/'s `answer(image, question) -> dict` signature (app/mock_pipeline.py)."""
    def answer(image: Image.Image, question: str) -> dict:
        item = EvalItem(question_id="live", image_id="live", image_path="", question=question, answer=None)
        return pipe(item, image).to_dict()
    return answer


REGISTRY: dict[str, Callable[[], Pipeline]] = {
    "mock": lambda: mock,
    "full_image": lambda: full_image(cache=False),
    "full_image_cached": lambda: full_image(cache=True),
    "lowres512": lambda: lowres(512),
    "lowres256": lambda: lowres(256),
    "gold_crop": lambda: gold_crop(0.05),
    "gold_crop_tight": lambda: gold_crop(0.0),
}
