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


def _ensure_ocr_helper() -> None:
    """Calling pipeline.ocr directly (not via the router) skipped the router's helper build, so the first OCR call
    of a run failed with "No such file or directory: 'evidence-ocr'" and that item silently went to the model
    (model_scale/e2e, eas-001a-q1). Build or locate the helper up front; with ROUTER_REQUIRE_OCR=1, fail the run."""
    import os
    import sys

    try:
        from pipeline.router import ensure_ocr_bin
    except Exception as e:  # router not importable: nothing to build with
        print(f"[eval] cannot prepare OCR helper: {e}", file=sys.stderr)
        return
    if ensure_ocr_bin() is None:
        msg = "OCR helper unavailable before the run (needs macOS + swiftc, or EVIDENCE_OCR_BIN)"
        if os.environ.get("ROUTER_REQUIRE_OCR") == "1":
            raise SystemExit(f"[eval] {msg}; ROUTER_REQUIRE_OCR=1, refusing to run")
        print(f"[eval] WARNING: {msg}; OCR-stage items will fall back", file=sys.stderr)


def resolve_fn(spec: str) -> Pipeline:
    mod, _, attr = spec.partition(":")
    if mod == "pipeline.ocr" or mod.startswith("pipeline.ocr."):
        _ensure_ocr_helper()
    return from_answer_fn(getattr(importlib.import_module(mod), attr), spec)
