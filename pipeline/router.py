"""Evidence Zoom router: OCR first, visual path on fallback (message 006).

    answer(image, question) -> eval.schema.PipelineResult

Stages (contracts from messages 010 and 012):
    pipeline.ocr.answer(image, question)                       -> PipelineResult   (andrew-ocr)
    pipeline.visual.answer(image, question, prior=None)        -> PipelineResult   (claude-zhihao)

OCR exits when its last route step is not "fallback". Otherwise the OCR result is passed to the
visual stage as `prior`; the visual stage appends to its route and usage, so the OCR cost and latency
are always charged. A stage that is missing or raises is recorded in `route`/`error`, never swallowed:
- OCR unavailable (e.g. not macOS) -> go straight to the visual stage, with a note in the route.
- visual unavailable                -> abstain with the OCR trace and an error.

Eval harness:  python -m eval.run_eval --items ... --pipelines pipeline.router:factory
App:           PIPELINE=pipeline.router uvicorn app.server:app
Env: ROUTER_SKIP_OCR=1 disables the OCR stage (ablation: visual path alone).
"""
from __future__ import annotations

import importlib
import os

from eval.schema import PipelineResult, RouteStep

NAME = "router@v1"


def _stage(module: str):
    try:
        return importlib.import_module(module).answer, None
    except Exception as e:  # ImportError, or a stage that fails at import time
        return None, f"{module} unavailable: {type(e).__name__}: {e}"


def _is_fallback(r: PipelineResult) -> bool:
    if r.route and r.route[-1].step == "fallback":
        return True
    return r.error is not None and r.error != "refusal"


def answer(image, question: str) -> PipelineResult:
    prior: PipelineResult | None = None
    notes: list[str] = []

    if os.environ.get("ROUTER_SKIP_OCR") != "1":
        ocr, err = _stage("pipeline.ocr")
        if ocr is None:
            notes.append(err)
        else:
            try:
                prior = ocr(image, question)
            except Exception as e:
                notes.append(f"pipeline.ocr raised {type(e).__name__}: {e}")
            else:
                if not _is_fallback(prior):
                    prior.pipeline = NAME
                    return prior

    if prior is None:
        prior = PipelineResult(None, abstained=True, pipeline=NAME)
        prior.route.append(RouteStep("fallback", target="overview", note="; ".join(notes) or "OCR skipped"))

    visual, err = _stage("pipeline.visual")
    if visual is None:
        prior.answer, prior.abstained = None, True
        prior.error = "; ".join(filter(None, [prior.error, *notes, err]))
        prior.pipeline = NAME
        return prior
    try:
        result = visual(image, question, prior=prior)
    except Exception as e:
        prior.answer, prior.abstained = None, True
        prior.error = "; ".join(filter(None, [prior.error, *notes, f"pipeline.visual raised {type(e).__name__}: {e}"]))
        prior.pipeline = NAME
        return prior
    result.pipeline = NAME
    return result


def factory():
    """run_eval entry point: `--pipelines pipeline.router:factory`."""
    from eval.pipelines.compose import from_answer_fn

    return from_answer_fn(answer, NAME)
