"""Composition helpers: wrap app-style `answer(image, question)` functions and chain routes.

- from_answer_fn(fn, name)     : app/pipeline signature -> harness Pipeline (fills ids, never raises)
- cascade(first, then, name)   : run `first`; if its last route step is "fallback" (or it abstained without
                                 evidence), run `then` and merge route + usage, so the first stage's cost is
                                 always charged (006: charge the overview and routing call even when zoom fails).

Names usable in run_eval:
    cascade:<first>|<then>      e.g.  cascade:pipeline.ocr:answer|full_image_cached
    fn:<module>:<attr>          e.g.  fn:pipeline.ocr:answer
A part that is not a registered/parametrized harness name is resolved as fn:<module>:<attr>.
"""
from __future__ import annotations

import importlib
from typing import Callable

from PIL import Image

from ..schema import EvalItem, PipelineResult
from .baselines import Pipeline


def from_answer_fn(fn: Callable[[Image.Image, str], PipelineResult | dict], name: str) -> Pipeline:
    def run(item: EvalItem, img: Image.Image) -> PipelineResult:
        try:
            r = fn(img, item.question)
            r = PipelineResult.from_dict(r) if isinstance(r, dict) else r
        except Exception as e:
            r = PipelineResult(answer=None, abstained=True, error=f"{type(e).__name__}: {e}")
        r.question_id, r.image_id = item.question_id, item.image_id
        r.pipeline = r.pipeline or name
        return r
    return run


def needs_fallback(r: PipelineResult) -> bool:
    if r.route and r.route[-1].step == "fallback":
        return True
    return r.error is not None and r.error != "refusal"


def cascade(first: Pipeline, then: Pipeline, name: str) -> Pipeline:
    def run(item: EvalItem, img: Image.Image) -> PipelineResult:
        a = first(item, img)
        if not needs_fallback(a):
            a.pipeline = name
            return a
        b = then(item, img)
        offset = len(a.route)
        for u in b.usage:
            u.step_index += offset
        b.route = a.route + b.route
        b.usage = a.usage + b.usage
        b.pipeline = name
        if a.error and not b.error:
            b.error = f"first stage: {a.error}"
        return b
    return run


def resolve_fn(spec: str) -> Pipeline:
    mod, _, attr = spec.partition(":")
    return from_answer_fn(getattr(importlib.import_module(mod), attr), spec)
