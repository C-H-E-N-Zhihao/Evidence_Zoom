"""Offline unit checks for eval/ ($0, no key, no OCR helper needed).

    python -m eval.selftest

Covers what the mock run does not: answer matching edge cases, IoU, abstention scoring, pricing (incl. local and
cache), cascade merging, the degraded/abort guard, name@model / cascade name parsing, the pair follow rate,
the cost curve, report rendering and gold-crop geometry. Exits non-zero on the first failing group.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from PIL import Image

from .metrics import answer_correct, cost_curve, evidence_iou, iou, summarize
from .pricing import cost_usd
from .schema import EvalItem, EvidenceBox, PipelineResult, RouteStep, Usage

FAILS: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  {'ok ' if cond else 'FAIL'} {name}{'' if cond else '  ' + detail}")
    if not cond:
        FAILS.append(name)


def item(ans="B", ok=True, boxes=None, et="visual", acc=None, qid="q", img="i", pair=None) -> EvalItem:
    return EvalItem(question_id=qid, image_id=img, image_path="", question="?", answer=ans, answerable=ok,
                    evidence_type=et, evidence_boxes=boxes if boxes is not None else [[0.1, 0.1, 0.3, 0.3]],
                    accepted_answers=acc or [], pair_id=pair)


def res(ans="B", abst=False, boxes=None, usage=None, route=None, err=None) -> PipelineResult:
    return PipelineResult(answer=ans, abstained=abst, evidence_boxes=[EvidenceBox(box=b) for b in (boxes or [])],
                          usage=usage or [], route=route or [], error=err)


def t_metrics() -> None:
    print("metrics")
    check("exact match, case/punct", answer_correct(item("HM-7731"), res("hm 7731.")))
    check("word inside sentence", answer_correct(item("B"), res("Vehicle B was hit")))
    check("no substring false hit", not answer_correct(item("8"), res("18")))
    check("accepted variant", answer_correct(item("10, 15", acc=["10 and 15"]), res("10 and 15")))
    check("abstain on answerable is wrong", not answer_correct(item("B"), res(None, abst=True)))
    check("abstain on unanswerable is right", answer_correct(item(None, ok=False, boxes=[]), res(None, abst=True)))
    check("answer on unanswerable is wrong", not answer_correct(item(None, ok=False, boxes=[]), res("123")))
    check("iou identical", abs(iou([0, 0, 1, 1], [0, 0, 1, 1]) - 1) < 1e-9)
    check("iou disjoint", iou([0, 0, .1, .1], [.5, .5, .6, .6]) == 0)
    check("iou half", abs(iou([0, 0, 1, 1], [0, 0, .5, 1]) - .5) < 1e-9)
    check("evidence none when no gold", evidence_iou(item(boxes=[]), res(boxes=[[0, 0, 1, 1]])) is None)
    check("evidence 0 when no prediction", evidence_iou(item(), res()) == 0.0)
    from .metrics import zoom_coverage

    g = item(boxes=[[0.1, 0.1, 0.3, 0.3]])
    check("zoom coverage full", zoom_coverage(g, res(route=[RouteStep("zoom", box=[0, 0, .5, .5])])) == 1.0)
    check("zoom coverage none", zoom_coverage(g, res(route=[RouteStep("zoom", box=[.6, .6, .9, .9])])) == 0.0)
    check("zoom coverage half",
          abs(zoom_coverage(g, res(route=[RouteStep("zoom", box=[0.1, 0.1, 0.2, 0.3])])) - 0.5) < 1e-9)
    check("no zoom -> None", zoom_coverage(g, res(route=[RouteStep("overview")])) is None)
    s = summarize([(item(et="text"), res()), (item(et="visual"), res("A"))])
    check("summary groups", s["all"]["n"] == 2 and s["text"]["accuracy"] == 1 and s["visual"]["accuracy"] == 0)


def t_pricing() -> None:
    print("pricing")
    u = Usage(0, "anthropic", "claude-opus-5-5", input_text_tokens=1_000_000)
    check("opus input $4/M", abs(cost_usd(u) - 4.0) < 1e-9)
    u = Usage(0, "anthropic", "claude-opus-5-5", cache_read_tokens=1_000_000, cache_write_tokens=1_000_000)
    check("opus cache read $0.20 + write 1.25x", abs(cost_usd(u) - (0.20 + 5.0)) < 1e-9)
    u = Usage(0, "local", "Apple Vision OCR", latency_ms=600)
    check("local is $0 and not estimated", cost_usd(u) == 0 and not u.estimated)
    import os

    g = Usage(0, "local", "Qwen", latency_ms=3_600_000, device="gpu")
    check("local GPU $0 by default", cost_usd(g) == 0)
    os.environ["EVAL_GPU_USD_PER_HOUR"] = "2.0"
    try:
        g = Usage(0, "local", "Qwen", latency_ms=1_800_000, device="gpu")
        c = Usage(0, "local", "OCR", latency_ms=1_800_000, device="cpu")
        check("GPU priced at assumed rate, marked estimated", abs(cost_usd(g) - 1.0) < 1e-9 and g.estimated)
        check("CPU-local stays $0 under a GPU rate", cost_usd(c) == 0)
    finally:
        del os.environ["EVAL_GPU_USD_PER_HOUR"]
    from .backends.openrouter_backend import _prepare, image_block as or_image

    part = or_image(Image.new("RGB", (4, 4)), cache=True)
    on, off = _prepare([part], True)[0], _prepare([part], False)[0]
    check("openrouter cache mark -> cache_control only when enabled",
          on.get("cache_control") == {"type": "ephemeral"} and "cache_control" not in off
          and "_cache" not in on and "_cache" not in off)
    u = Usage(0, "openrouter", "unknown/model", input_text_tokens=10)
    check("unknown API model flagged estimated", cost_usd(u) == 0 and u.estimated)


def t_compose_and_guard() -> None:
    print("compose / guard / names")
    from .pipelines.compose import cascade
    from .run_eval import degraded, get_pipeline

    ocr_exit = lambda it, im: res("X", usage=[Usage(0, "local", "ocr")], route=[RouteStep("ocr"), RouteStep("answer")])
    ocr_fb = lambda it, im: res(None, abst=True, usage=[Usage(0, "local", "ocr", latency_ms=5)],
                                route=[RouteStep("ocr"), RouteStep("fallback", note="Visual inspection required")])
    vis = lambda it, im: res("Y", usage=[Usage(0, "fake", "m", cost_usd=0.01), Usage(1, "fake", "m", cost_usd=0.02)],
                             route=[RouteStep("overview"), RouteStep("zoom")])
    im = Image.new("RGB", (10, 10))
    r = cascade(ocr_exit, vis, "c")(item(), im)
    check("cascade stops at OCR exit", r.answer == "X" and len(r.usage) == 1)
    r = cascade(ocr_fb, vis, "c")(item(), im)
    check("cascade merges route and usage", r.answer == "Y" and len(r.route) == 4 and len(r.usage) == 3)
    check("cascade offsets step_index", [u.step_index for u in r.usage] == [0, 2, 3])
    check("cascade keeps first-stage cost", abs(r.total_cost() - 0.03) < 1e-9)
    check("normal fallback is not degraded", degraded(ocr_fb(None, None)) is None)
    check("skip-OCR ablation is not degraded",
          degraded(res(route=[RouteStep("fallback", note="OCR skipped")])) is None)
    check("missing helper file (Errno 2) is degraded",
          degraded(res(route=[RouteStep("fallback", note="[Errno 2] No such file or directory: 'evidence-ocr'")]))
          is not None)
    check("missing helper is degraded",
          degraded(res(route=[RouteStep("fallback", note="OCR helper unavailable (see stderr)")])) is not None)
    check("error is degraded, refusal is not",
          degraded(res(err="RuntimeError: x")) is not None and degraded(res(err="refusal")) is None)
    check("registry name", callable(get_pipeline("mock")))
    check("parametrized name", callable(get_pipeline("gold_crop_px:256")))
    check("name@model", callable(get_pipeline("full_image_cached@or:some/model")))
    check("cascade name", callable(get_pipeline("cascade:mock|mock")))
    check("nested cascade name", callable(get_pipeline("cascade:mock|cascade:mock|mock")))
    try:
        import scipy  # noqa: F401  (checkbox_pixels needs numpy + scipy)

        cb = get_pipeline("checkbox_pixels")
        r = cb(item(qid="x"), Image.new("RGB", (800, 1000), "white"))
        check("checkbox_pixels falls back on a blank page",
              r.route[-1].step == "fallback" and r.usage[0].provider == "local" and degraded(r) is None)
    except ImportError:
        print("  skip checkbox_pixels (scipy not installed)")


def t_pairs_curve_report() -> None:
    print("pairs / cost curve / report")
    from .reliance import pair_follow_rate
    from . import report

    a, b = item("8", qid="a", img="ia", pair="p"), item("7", qid="b", img="ib", pair="p")
    check("pair follow 1 when both right", pair_follow_rate([(a, res("8")), (b, res("7"))]) == 1.0)
    check("pair follow 0 when answer ignores edit", pair_follow_rate([(a, res("8")), (b, res("8"))]) == 0.0)
    u = lambda c: [Usage(0, "x", "m", cost_usd=c)]
    curve = cost_curve([(item(img="p1"), res(usage=u(1))), (item(img="p1"), res(usage=u(2))),
                        (item(img="p2"), res(usage=u(4)))])
    check("cost curve cumulative mean", curve[0]["mean_cum_cost_usd"] == 2.5 and curve[1]["mean_cum_cost_usd"] == 3)
    pairs = [(item(et="text"), res())]
    run = {"meta": {"time": "t", "commit": "c", "items": "x", "spent_usd": 0, "degrade": "phone_photo",
                    "geometric_degrade": True},
           "report": {"p": {"summary": summarize(pairs), "pair_follow_rate": None, "aborted": "boom",
                            "complete": False, "degraded": 3}}}
    from .plot_frontier import pareto, short

    check("pareto keeps cheap and accurate, drops dominated",
          pareto([(1, .4), (2, .7), (3, .6), (0.5, .4)]) == {1, 3})
    check("short label", short("gold_crop_px:384@local:Qwen/Qwen2.5-VL-7B-Instruct") == "gold_crop 384 (7B)")
    from .plot_frontier import served_models

    rep = {"results": [{"usage": [{"provider": "local", "model": "Apple Vision OCR (anchor)"},
                                  {"provider": "local", "model": "Qwen/Qwen2.5-VL-72B-Instruct-AWQ", "device": "gpu"}]},
                       {"usage": [{"provider": "local", "model": "Qwen/Qwen2.5-VL-7B-Instruct"}]}]}
    check("served models from usage (OCR excluded, old runs without device)", served_models(rep) == "72B+7B")
    md = report.table(run)
    check("report renders rows", "| `p` | all |" in md)
    check("report flags aborted run", "not a clean measurement" in md)
    check("report flags geometric degradation", "Geometric degradation" in md)
    two = [(item(et="text"), res()), (item(et="text"), res())]
    run2 = {"meta": {"time": "t", "commit": "c", "items": "x", "spent_usd": 0},
            "report": {"full_image_cached@or:x": {"summary": summarize(two), "complete": True}}}
    check("report flags 'cached' run with no cache reads", "no cache reads were billed" in report.table(run2))
    run2["meta"].update(pipeline_tree="abc123", freeze_tag="freeze-x", pipeline_equals_freeze=False, pipeline_dirty=True)
    md2 = report.table(run2)
    check("report flags code that is not the freeze", "≠ frozen tag" in md2 and "uncommitted changes in pipeline/" in md2)
    from .run_eval import code_provenance

    check("code_provenance never raises and returns a dict", isinstance(code_provenance(), dict))


def t_geometry() -> None:
    print("gold-crop geometry")
    from .pipelines.baselines import _gold_window, _map_box

    img = Image.new("RGB", (1000, 2000))
    it = item(boxes=[[0.4, 0.4, 0.45, 0.42]])
    w = _gold_window(it, img, 200)
    check("window has requested pixel size", round((w[2] - w[0]) * 1000) == 200 and round((w[3] - w[1]) * 2000) == 200)
    check("window contains gold", w[0] <= .4 and w[2] >= .45 and w[1] <= .4 and w[3] >= .42)
    edge = _gold_window(item(boxes=[[0.98, 0.99, 1.0, 1.0]]), img, 200)
    check("window clipped inside image", edge[0] >= 0 and edge[2] <= 1 and edge[1] >= 0 and edge[3] <= 1)
    big = _gold_window(item(boxes=[[0.1, 0.1, 0.9, 0.2]]), img, 100)
    check("window grows to cover large evidence", big[0] <= .1 and big[2] >= .9)
    from .pipelines.baselines import normalize_box

    shown = Image.new("RGB", (400, 200))
    check("pixel box normalized", normalize_box([100, 50, 200, 100], shown) == [0.25, 0.25, 0.5, 0.5])
    check("normalized box unchanged", normalize_box([0.1, 0.2, 0.3, 0.4], shown) == [0.1, 0.2, 0.3, 0.4])
    mb = _map_box([0, 0, 1, 1], (.2, .3, .4, .5))
    check("box maps back from crop", all(abs(x - y) < 1e-9 for x, y in zip(mb, [.2, .3, .4, .5])))
    mb = _map_box([.5, .5, 1, 1], (.2, .3, .4, .5))
    check("box maps back (half)", all(abs(x - y) < 1e-9 for x, y in zip(mb, [.3, .4, .4, .5])))


def t_run_eval_mock() -> None:
    print("run_eval end to end (mock, temp dir)")
    import subprocess

    with tempfile.TemporaryDirectory() as d:
        Image.new("RGB", (100, 100), "white").save(Path(d) / "p.png")
        rows = [dict(question_id=f"q{i}", image_id="p", image_path="p.png", question="?", answer=str(i),
                     evidence_boxes=[[0.1, 0.1, 0.2, 0.2]]) for i in range(3)]
        (Path(d) / "items.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
        out = Path(d) / "out"
        p = subprocess.run([sys.executable, "-m", "eval.run_eval", "--items", str(Path(d) / "items.jsonl"),
                            "--pipelines", "mock", "--out", str(out)], capture_output=True, text=True)
        files = list(out.glob("run_*.json"))
        check("run_eval exits 0", p.returncode == 0, p.stderr[-300:])
        if files:
            rep = json.loads(files[0].read_text())["report"]["mock"]
            check("mock accuracy 1 and complete", rep["summary"]["all"]["accuracy"] == 1 and rep["complete"])


def main() -> None:
    for t in (t_metrics, t_pricing, t_compose_and_guard, t_pairs_curve_report, t_geometry, t_run_eval_mock):
        try:
            t()
        except Exception as e:  # a crash in a group is a failure of that group
            check(f"{t.__name__} crashed", False, f"{type(e).__name__}: {e}")
    print(f"\n{'ALL EVAL CHECKS PASSED' if not FAILS else f'{len(FAILS)} FAILED: ' + ', '.join(FAILS)}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
