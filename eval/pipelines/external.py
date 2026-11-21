"""Harness adapters for teammates' components that are not PipelineResult-shaped (code stays in their files).

- checkbox_pixels: andrew-ocr's classical checkbox reader (experiments/checkbox_pixels.py). Model-free, $0,
  local latency recorded. Answers only "which boxes did driver X tick" and "did driver X tick N"; otherwise, or
  when the detector rejects the page, it ends with a `fallback` step, so it can sit inside a cascade:

      "cascade:fn:pipeline.ocr:answer|cascade:checkbox_pixels|pipeline.visual:factory"

  Evidence: the tick column region is not returned by the detector, so no evidence box is emitted (evidence hit
  is not measurable for this stage; report it as such).
"""
from __future__ import annotations

import time

from PIL import Image

from ..schema import EvalItem, PipelineResult, RouteStep, Usage


def checkbox_pixels(max_side: int = 1200):
    from experiments.checkbox_pixels import answer, read_columns

    cache: dict[int, object] = {}  # same page object -> detector output (mirrors the OCR page index)

    def run(item: EvalItem, img: Image.Image) -> PipelineResult:
        t0 = time.perf_counter()
        key = id(img)
        reused = key in cache
        if not reused:
            cache.clear()
            cache[key] = read_columns(img, max_side=max_side)
        cols = cache[key]
        ans = answer(cols, item.question)
        ms = (time.perf_counter() - t0) * 1000
        r = PipelineResult(answer=None, abstained=True, pipeline=f"checkbox_pixels{max_side}",
                           question_id=item.question_id, image_id=item.image_id)
        r.usage.append(Usage(0, "local", "checkbox_pixels", latency_ms=ms,
                             note="page reused" if reused else "page detected"))
        r.route.append(RouteStep("index", note="classical checkbox detector"))
        if ans is None:
            why = "detector rejected page" if cols is None else "question not supported"
            r.route.append(RouteStep("fallback", target="overview", note=f"Visual inspection required ({why})"))
        else:
            r.answer, r.abstained = ans, False
            r.route.append(RouteStep("answer", note="pixel ink test, no model"))
        return r

    return run
