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
     ROUTER_ANCHOR=0 removes the OCR-anchored crop stage (pipeline.anchor) between OCR and the overview
     (default on, except when an overview-only replay/test oracle is installed).
     ROUTER_FALLBACK=page|overview: what runs when OCR and the anchor decline (default page; overview under oracles).
     ROUTER_REQUIRE_OCR=1 raises if the OCR helper is unavailable (use for paid runs: without it the
     OCR-answerable questions silently go to the paid visual path).

OCR helper: if EVIDENCE_OCR_BIN is unset and `evidence-ocr` is not on PATH, the router compiles
pipeline/ocr/recognize.swift once (macOS + swiftc) into ~/.cache/evidence-zoom/ and sets EVIDENCE_OCR_BIN.
"""
from __future__ import annotations

import importlib
import os
import shutil
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

from eval.schema import PipelineResult, RouteStep

NAME = "router@v2"  # v2 (message 062): full-page fallback by default; v1 = freeze-anchor-ocr-v1


@lru_cache(maxsize=1)
def ensure_ocr_bin() -> str | None:
    """Return a path to the OCR helper, building it if needed; None (with a reason on stderr) if impossible."""
    env = os.environ.get("EVIDENCE_OCR_BIN")
    if env:
        if Path(env).is_file():
            return env
        print(f"[router] EVIDENCE_OCR_BIN={env} does not exist", file=sys.stderr)
        return None
    if found := shutil.which("evidence-ocr"):
        return found
    src = Path(__file__).parent / "ocr" / "recognize.swift"
    out = Path.home() / ".cache" / "evidence-zoom" / "evidence-ocr"
    if out.is_file() and out.stat().st_mtime >= src.stat().st_mtime:
        os.environ["EVIDENCE_OCR_BIN"] = str(out)
        return str(out)
    if sys.platform != "darwin" or not shutil.which("swiftc") or not src.is_file():
        print("[router] OCR helper unavailable (needs macOS + swiftc); OCR stage skipped", file=sys.stderr)
        return None
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(["swiftc", "-O", str(src), "-o", str(out)], check=True, capture_output=True, timeout=300)
    except (OSError, subprocess.SubprocessError) as e:
        print(f"[router] building OCR helper failed: {e}", file=sys.stderr)
        return None
    os.environ["EVIDENCE_OCR_BIN"] = str(out)
    return str(out)


def _stage(module: str):
    try:
        return importlib.import_module(module).answer, None
    except Exception as e:  # ImportError, or a stage that fails at import time
        return None, f"{module} unavailable: {type(e).__name__}: {e}"


def _is_fallback(r: PipelineResult) -> bool:
    if r.route and r.route[-1].step == "fallback":
        return True
    return r.error is not None and r.error != "refusal"


def answer(image, question: str, anchor: bool | None = None, fallback: str | None = None) -> PipelineResult:
    """anchor: also try the OCR-anchored crop (pipeline.anchor) first; default from ROUTER_ANCHOR (see below).
    fallback: what runs when OCR and the anchor decline: "page" (one call on the whole page, default since
    message 062: on an unseen layout the model-chosen overview zoom halves accuracy and invents missing fields)
    or "overview" (overview -> model-chosen zoom, the v1 behaviour). Default from ROUTER_FALLBACK."""
    if anchor is None:
        # Default ON for real models (message 052: the anchor crop is the measured winner). Exception: a test
        # oracle installed in pipeline.visual.CALL_OVERRIDE that only models the overview route (no
        # `direct_zoom` attribute) keeps the v1 route. The fixture replay (demo, selftest, scorecard) declares
        # direct_zoom, so it follows the shipped route.
        vis = sys.modules.get("pipeline.visual")
        ov = getattr(vis, "CALL_OVERRIDE", None) if vis is not None else None
        oracle = ov is not None and not getattr(ov, "direct_zoom", False)  # direct-zoom replays follow the product
        default = "0" if oracle else "1"
        anchor = os.environ.get("ROUTER_ANCHOR", default) == "1"
    if fallback is None:
        # Same exception as the anchor: the replay/test oracles model the overview route.
        vis = sys.modules.get("pipeline.visual")
        ov = getattr(vis, "CALL_OVERRIDE", None) if vis is not None else None
        oracle = ov is not None and not getattr(ov, "direct_zoom", False)  # direct-zoom replays follow the product
        default_fb = "overview" if oracle else "page"
        fallback = os.environ.get("ROUTER_FALLBACK", default_fb)
    if fallback not in ("page", "overview"):
        raise ValueError(f"ROUTER_FALLBACK must be 'page' or 'overview', not {fallback!r}")
    prior: PipelineResult | None = None
    notes: list[str] = []

    if os.environ.get("ROUTER_SKIP_OCR") != "1":
        ocr, err = _stage("pipeline.ocr")
        if ocr is not None and ensure_ocr_bin() is None:
            if os.environ.get("ROUTER_REQUIRE_OCR") == "1":
                raise RuntimeError("ROUTER_REQUIRE_OCR=1 but the OCR helper is unavailable")
            ocr, err = None, "OCR helper unavailable (see stderr)"
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

    if anchor:  # OCR answer -> anchor crop (one zoom call, region from the layout) -> overview
        anc, err = _stage("pipeline.anchor")
        if anc is None:
            notes.append(err)
        else:
            try:
                prior = anc(image, question, prior=prior)
            except Exception as e:
                notes.append(f"pipeline.anchor raised {type(e).__name__}: {e}")
            else:
                if not _is_fallback(prior):
                    prior.pipeline = NAME
                    return prior

    visual, err = _stage("pipeline.visual")
    if visual is None:
        prior.answer, prior.abstained = None, True
        prior.error = "; ".join(filter(None, [prior.error, *notes, err]))
        prior.pipeline = NAME
        return prior
    try:
        if fallback == "page":  # one call on the whole page, same prompt/mapping as a zoom (pipeline.visual.zoom_answer)
            from pipeline import visual as _vis

            prior.route.append(RouteStep("fallback", target="page", note="no OCR answer or anchor: full page"))
            model = os.environ.get("EVAL_MODEL") or getattr(_vis, "DEFAULT_MODEL", None)  # read at call time
            if os.environ.get("ROUTER_PAGE_CROP", "1") == "1":
                # the page as one image, cropped to the OCR text area and downscaled (pipeline.general._page_call:
                # 1024 px long side for normal pages, short side >= 768 px; realdocs resolution frontier, approved)
                from pipeline import general as _gen

                lines = []
                try:
                    from pipeline.ocr import recognize_page

                    lines = _gen._lines(recognize_page(image)[0])
                except Exception:
                    pass
                result = _gen._page_call(image, question, prior, model or _vis.DEFAULT_MODEL, None, lines, "the whole page")
            else:
                result = _vis.zoom_answer(image, question, [(0.0, 1.0)], [(0.0, 1.0)], prior=prior,
                                          look_for="the whole page", target="full page", name="page_fallback",
                                          **({"model": model} if model else {}))
        else:
            result = visual(image, question, prior=prior)
    except Exception as e:
        prior.answer, prior.abstained = None, True
        prior.error = "; ".join(filter(None, [prior.error, *notes, f"pipeline.visual raised {type(e).__name__}: {e}"]))
        prior.pipeline = NAME
        return prior
    result.pipeline = NAME
    return result


def factory_v1():
    """run_eval: `pipeline.router:factory_v1`: OCR -> anchor -> overview zoom (the frozen-tag behaviour)."""
    from eval.pipelines.compose import from_answer_fn

    return from_answer_fn(lambda image, question: answer(image, question, anchor=True, fallback="overview"),
                          "router@v1")


def factory_no_anchor():
    """run_eval: `--pipelines pipeline.router:factory_no_anchor` (OCR -> overview, the pre-052 route)."""
    from eval.pipelines.compose import from_answer_fn

    return from_answer_fn(lambda image, question: answer(image, question, anchor=False), NAME + "-anchor")


def factory_anchor():
    """run_eval: `--pipelines pipeline.router:factory_anchor` (OCR -> anchor crop -> overview; = factory by default)."""
    from eval.pipelines.compose import from_answer_fn

    return from_answer_fn(lambda image, question: answer(image, question, anchor=True), NAME + "+anchor")


def factory():
    """run_eval entry point: `--pipelines pipeline.router:factory`."""
    from eval.pipelines.compose import from_answer_fn

    return from_answer_fn(answer, NAME)
