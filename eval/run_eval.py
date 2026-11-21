"""Run pipelines over a labelled set and write one results JSON per run.

    python -m eval.run_eval --items eval/data/<set>/items.jsonl --pipelines mock full_image gold_crop \
        [--limit 5] [--max-cost 1.00] [--out eval/results]

External pipelines: --pipelines my.module:factory  (factory() -> callable(item, image) -> PipelineResult).
Questions about one image run consecutively, so cached pipelines see realistic cache hits.
A hard --max-cost stops the run once the cumulative spend of this invocation reaches it.
"""
from __future__ import annotations

import argparse
import importlib
import json
import subprocess
import time
from collections import defaultdict
from pathlib import Path

from PIL import Image

from .metrics import cost_curve, summarize
from .pipelines.baselines import REGISTRY, parse_name
from .schema import EvalItem, PipelineResult


def load_items(path: Path) -> list[EvalItem]:
    items = [EvalItem(**json.loads(l)) for l in path.read_text().splitlines() if l.strip()]
    for it in items:
        it.image_path = str((path.parent / it.image_path).resolve())
    return items


def get_pipeline(name: str):
    """Harness name | parametrized name | name@model | cascade:<a>|<b> | fn:<module>:<attr> | <module>:<factory>."""
    from .pipelines.compose import cascade, resolve_fn

    if name.startswith("cascade:"):
        first, _, then = name[len("cascade:"):].partition("|")
        return cascade(_part(first), _part(then), name)
    if name.startswith("fn:"):
        return resolve_fn(name[3:])
    base, _, model = name.partition("@")
    if model:
        return with_model(base, model)
    if name in REGISTRY:
        return REGISTRY[name]()
    if (p := parse_name(name)) is not None:
        return p
    mod, _, fn = name.partition(":")
    return getattr(importlib.import_module(mod), fn)()


def _part(spec: str):
    """Cascade member: a harness name if it resolves, else an app-style answer function module:attr."""
    from .pipelines.compose import resolve_fn

    if spec.startswith(("cascade:", "fn:")):  # nested chains: cascade:a|cascade:b|c
        return get_pipeline(spec)
    base = spec.partition("@")[0]
    if base in REGISTRY or parse_name(base) is not None:
        return get_pipeline(spec)
    if spec.rpartition(":")[2].startswith("factory"):  # module:factory* -> a harness pipeline factory
        return get_pipeline(spec)
    return resolve_fn(spec)


def with_model(base: str, model: str):
    """`full_image@claude-haiku-5-5`, `gold_crop_px:384@claude-sonnet-5-5`, ...: same control, other model."""
    from .pipelines import baselines as b

    parts = base.split(":")
    table = {
        "full_image": lambda: b.full_image(cache=False, model=model),
        "full_image_cached": lambda: b.full_image(cache=True, model=model),
        "gold_crop": lambda: b.gold_crop(0.05, model=model),
        "gold_crop_tight": lambda: b.gold_crop(0.0, model=model),
        "lowres": lambda: b.lowres(int(parts[1]), model=model),
        "gold_crop_px": lambda: b.gold_crop_px(int(parts[1]), model=model),
        "overview_gold": lambda: b.overview_plus_gold_crop(int(parts[1]), int(parts[2]), model=model),
    }
    p = _rename(table[parts[0]](), f"{base}@{model}")
    return p


def _rename(pipe, name: str):
    def run(item, img):
        r = pipe(item, img)
        r.pipeline = name
        return r
    return run


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


# Matched against fallback notes. Normal OCR fallbacks ("Visual inspection required") and the intended
# ROUTER_SKIP_OCR ablation ("OCR skipped") do not match.
_DEGRADED_MARKERS = ("unavailable", "raised", "not found", "credentials")


def degraded(r: PipelineResult) -> str | None:
    """Why a result should not count as a clean measurement, or None.

    Errors (except refusals) and stages that silently fell back because a component was missing (e.g. the OCR
    helper not built: the router then sends every item to the paid visual path, message 019).
    """
    if r.error and r.error != "refusal":
        return r.error[:80]
    for s in r.route:
        if s.step == "fallback" and s.note and any(m in s.note.lower() for m in _DEGRADED_MARKERS):
            return f"fallback: {s.note[:80]}"
    return None


def _degradation(name: str):
    if name == "clean":
        return lambda im: im
    from bench.ocr_robustness import DEGRADATIONS  # claude-andrew-b's bench, reused so both measure the same inputs

    if name not in DEGRADATIONS:
        raise SystemExit(f"unknown --degrade {name!r}; choose from {sorted(DEGRADATIONS)}")
    return DEGRADATIONS[name]


def main() -> None:
    from .reliance import pair_follow_rate  # local import: reliance imports this module
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", required=True)
    ap.add_argument("--pipelines", nargs="+", default=["mock"])
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--max-cost", type=float, default=1.0, help="USD cap for this invocation")
    ap.add_argument("--out", default="eval/results")
    ap.add_argument("--max-error-rate", type=float, default=0.2,
                    help="abort a pipeline when more than this fraction of its results errored or degraded")
    ap.add_argument("--warmup", type=int, default=8, help="results before the error-rate check applies")
    ap.add_argument("--degrade", default="clean",
                    help="input degradation from bench/ocr_robustness.py DEGRADATIONS (e.g. phone_photo, scale_1024, "
                         "jpeg_q40). Geometric ones (rotate_*, perspective_*, phone_photo) move the content, so gold "
                         "boxes, evidence metrics and gold_crop controls are approximate under them.")
    a = ap.parse_args()
    degrade_fn = _degradation(a.degrade)

    items = load_items(Path(a.items))[: a.limit]
    by_img: dict[str, list[EvalItem]] = defaultdict(list)
    for it in items:
        by_img[it.image_id].append(it)

    spent, report, budget_hit = 0.0, {}, False
    for pname in a.pipelines:
        if budget_hit:
            break
        pipe = get_pipeline(pname)
        pairs: list[tuple[EvalItem, PipelineResult]] = []
        n_bad, aborted = 0, None
        for img_id, its in by_img.items():
            img = degrade_fn(Image.open(its[0].image_path).convert("RGB"))
            for it in its:
                if spent >= a.max_cost:
                    print(f"[stop] max cost ${a.max_cost:.2f} reached")
                    budget_hit = True
                    break
                r = pipe(it, img)
                spent += r.total_cost()
                pairs.append((it, r))
                bad = degraded(r)
                n_bad += bool(bad)
                print(f"{pname:>18} {it.question_id:>10} ok={r.answer!r:.40} cost=${r.total_cost():.4f} "
                      f"err={r.error}{' DEGRADED: ' + bad if bad else ''}")
                if len(pairs) >= a.warmup and n_bad / len(pairs) > a.max_error_rate:
                    aborted = (f"{n_bad}/{len(pairs)} results errored or degraded (> {a.max_error_rate:.0%}); "
                               "stopped so a broken stage does not produce a misleading cost number")
                    print(f"[abort {pname}] {aborted}")
                    break
            if budget_hit or aborted:
                break
        report[pname] = {
            "summary": summarize(pairs),
            "cost_curve": cost_curve(pairs),
            "pair_follow_rate": pair_follow_rate(pairs),
            "degraded": n_bad,
            "aborted": aborted,
            "complete": len(pairs) == len(items),
            "results": [r.to_dict() for _, r in pairs],
        }

    meta = {"commit": git_commit(), "items": a.items, "n_items": len(items), "pipelines": a.pipelines,
            "spent_usd": spent, "budget_hit": budget_hit, "max_error_rate": a.max_error_rate,
            "degrade": a.degrade, "geometric_degrade": a.degrade.startswith(("rotate", "perspective", "phone")),
            "time": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    out = Path(a.out) / f"run_{time.strftime('%Y%m%d-%H%M%S')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"meta": meta, "report": report}, indent=2))
    print(f"\nwrote {out}  (spent ${spent:.4f})")
    for p, rep in report.items():
        s = rep["summary"]["all"]
        print(f"{p:>18} acc={s['accuracy']} hit={s['evidence_hit@0.3']} cost/q=${s['cost_usd_mean']:.4f}")


if __name__ == "__main__":
    main()
