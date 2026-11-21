"""Stub-based checks for pipeline/router.py (no OCR binary, no API).  Run: python -m pipeline.test_router"""
import sys
import types

from eval.schema import EvidenceBox, PipelineResult, RouteStep, Usage
from pipeline import router


def _install(name, fn):
    mod = types.ModuleType(name)
    mod.answer = fn
    sys.modules[name] = mod


def _ocr_exit(image, question):
    r = PipelineResult("AS-1", pipeline="ocr")
    r.route = [RouteStep("ocr"), RouteStep("answer", box=[0, 0, .1, .1])]
    r.evidence_boxes = [EvidenceBox([0, 0, .1, .1], source="ocr")]
    r.usage = [Usage(0, "local", "vision", latency_ms=600)]
    return r


def _ocr_fallback(image, question):
    r = PipelineResult(None, abstained=True, pipeline="ocr")
    r.route = [RouteStep("ocr"), RouteStep("fallback", target="overview")]
    r.usage = [Usage(0, "local", "vision", latency_ms=600)]
    return r


def _visual(image, question, prior=None):
    r = prior or PipelineResult(None)
    off = len(r.route)
    r.route += [RouteStep("overview"), RouteStep("zoom", target="B3"), RouteStep("answer")]
    r.usage += [Usage(off, "anthropic", "m", cost_usd=.002), Usage(off + 1, "anthropic", "m", cost_usd=.003)]
    r.answer, r.abstained = "10, 16", False
    return r


def _boom(*a, **k):
    raise RuntimeError("boom")


def _clear():
    for m in ("pipeline.ocr", "pipeline.visual"):
        sys.modules.pop(m, None)


def run():
    _install("pipeline.ocr", _ocr_exit); _install("pipeline.visual", _boom)
    r = router.answer(None, "q")
    assert r.answer == "AS-1" and [s.step for s in r.route] == ["ocr", "answer"] and r.pipeline == router.NAME

    _install("pipeline.ocr", _ocr_fallback); _install("pipeline.visual", _visual)
    r = router.answer(None, "q")
    assert [s.step for s in r.route] == ["ocr", "fallback", "overview", "zoom", "answer"], r.route
    assert len(r.usage) == 3 and r.usage[0].provider == "local" and abs(r.total_cost() - .005) < 1e-9
    assert r.answer == "10, 16" and r.error is None

    _install("pipeline.ocr", _boom)
    r = router.answer(None, "q")
    assert r.route[0].step == "fallback" and "boom" in r.route[0].note and r.answer == "10, 16"

    _install("pipeline.ocr", _ocr_fallback); _install("pipeline.visual", _boom)
    r = router.answer(None, "q")
    assert r.abstained and "boom" in r.error and r.usage[0].provider == "local"

    _clear(); sys.modules["pipeline.ocr"] = None; sys.modules["pipeline.visual"] = None  # force ImportError
    r = router.answer(None, "q")
    assert r.abstained and "pipeline.ocr unavailable" in r.error and "pipeline.visual unavailable" in r.error

    import os
    os.environ["ROUTER_SKIP_OCR"] = "1"; _install("pipeline.ocr", _boom); _install("pipeline.visual", _visual)
    r = router.answer(None, "q")
    assert r.route[0].note == "OCR skipped" and r.answer == "10, 16"
    del os.environ["ROUTER_SKIP_OCR"]; _clear()
    print("router: 6 checks passed")


if __name__ == "__main__":
    run()
