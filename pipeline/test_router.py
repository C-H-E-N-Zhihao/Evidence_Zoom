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
    import os
    os.environ["ROUTER_FALLBACK"] = "overview"  # checks 1-13 cover the overview path; page fallback checked at the end
    real_ensure = router.ensure_ocr_bin
    router.ensure_ocr_bin = lambda: "stub"
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
    del os.environ["ROUTER_SKIP_OCR"]

    # helper missing: OCR skipped with a note, visual still answers; ROUTER_REQUIRE_OCR=1 raises
    router.ensure_ocr_bin = lambda: None
    _install("pipeline.ocr", _ocr_exit); _install("pipeline.visual", _visual)
    r = router.answer(None, "q")
    assert "OCR helper unavailable" in r.route[0].note and r.answer == "10, 16"
    os.environ["ROUTER_REQUIRE_OCR"] = "1"
    try:
        router.answer(None, "q"); raise AssertionError("expected RuntimeError")
    except RuntimeError:
        pass
    del os.environ["ROUTER_REQUIRE_OCR"]

    # anchor stage (ROUTER_ANCHOR / anchor=True): answers -> no overview; falls back -> overview continues
    router.ensure_ocr_bin = lambda: "stub"

    def _anchor_hit(image, question, prior=None):
        prior.route += [RouteStep("zoom", target="anchor:ticks"), RouteStep("answer")]
        prior.answer, prior.abstained = "8", False
        return prior

    def _anchor_miss(image, question, prior=None):
        prior.route.append(RouteStep("fallback", target="overview", note="no OCR anchor"))
        return prior

    _install("pipeline.ocr", _ocr_fallback); _install("pipeline.visual", _visual); _install("pipeline.anchor", _anchor_hit)
    r = router.answer(None, "q", anchor=True)
    assert [s.step for s in r.route] == ["ocr", "fallback", "zoom", "answer"] and r.answer == "8", r.route
    r = router.answer(None, "q")  # default on: anchor used
    assert r.answer == "8", r.route
    os.environ["DEMO_REPLAY"] = "1"  # demo replay: default off
    r = router.answer(None, "q")
    assert r.answer == "10, 16", r.route
    del os.environ["DEMO_REPLAY"]
    r = router.answer(None, "q", anchor=False)
    assert r.answer == "10, 16", r.route
    _install("pipeline.anchor", _anchor_miss)
    r = router.answer(None, "q", anchor=True)
    assert [s.step for s in r.route] == ["ocr", "fallback", "fallback", "overview", "zoom", "answer"], r.route

    # page fallback (router@v2 default): OCR and anchor decline -> one zoom_answer call on the whole page
    del os.environ["ROUTER_FALLBACK"]
    calls = []

    def _zoom_answer(image, question, rows, cols, prior=None, **kw):
        calls.append((rows, cols, kw.get("target")))
        prior.route += [RouteStep("zoom", target=kw.get("target")), RouteStep("answer")]
        prior.answer, prior.abstained = "page answer", False
        return prior

    vis = types.ModuleType("pipeline.visual"); vis.answer = _visual; vis.zoom_answer = _zoom_answer
    sys.modules["pipeline.visual"] = vis
    r = router.answer(None, "q")  # anchor miss (installed above) -> page
    assert r.answer == "page answer" and calls[-1][:2] == ([(0.0, 1.0)], [(0.0, 1.0)]), (r.route, calls)
    assert [s.step for s in r.route][-3:] == ["fallback", "zoom", "answer"] and r.route[-3].target == "page"
    r = router.answer(None, "q", fallback="overview")
    assert r.answer == "10, 16"
    vis.CALL_OVERRIDE = object()  # an oracle installed -> overview (and no anchor) by default
    r = router.answer(None, "q")
    assert r.answer == "10, 16" and "anchor" not in str(r.route), r.route
    sys.modules.pop("pipeline.anchor", None)
    router.ensure_ocr_bin = real_ensure; _clear()
    print("router: 16 checks passed")


if __name__ == "__main__":
    run()
