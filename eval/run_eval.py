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
from .pipelines.baselines import REGISTRY
from .schema import EvalItem, PipelineResult


def load_items(path: Path) -> list[EvalItem]:
    items = [EvalItem(**json.loads(l)) for l in path.read_text().splitlines() if l.strip()]
    for it in items:
        it.image_path = str((path.parent / it.image_path).resolve())
    return items


def get_pipeline(name: str):
    if name in REGISTRY:
        return REGISTRY[name]()
    mod, _, fn = name.partition(":")
    return getattr(importlib.import_module(mod), fn)()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def main() -> None:
    from .reliance import pair_follow_rate  # local import: reliance imports this module
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", required=True)
    ap.add_argument("--pipelines", nargs="+", default=["mock"])
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--max-cost", type=float, default=1.0, help="USD cap for this invocation")
    ap.add_argument("--out", default="eval/results")
    a = ap.parse_args()

    items = load_items(Path(a.items))[: a.limit]
    by_img: dict[str, list[EvalItem]] = defaultdict(list)
    for it in items:
        by_img[it.image_id].append(it)

    spent, report = 0.0, {}
    for pname in a.pipelines:
        pipe = get_pipeline(pname)
        pairs: list[tuple[EvalItem, PipelineResult]] = []
        for img_id, its in by_img.items():
            img = Image.open(its[0].image_path).convert("RGB")
            for it in its:
                if spent >= a.max_cost:
                    print(f"[stop] max cost ${a.max_cost:.2f} reached")
                    break
                r = pipe(it, img)
                spent += r.total_cost()
                pairs.append((it, r))
                print(f"{pname:>18} {it.question_id:>10} ok={r.answer!r:.40} cost=${r.total_cost():.4f} err={r.error}")
        report[pname] = {
            "summary": summarize(pairs),
            "cost_curve": cost_curve(pairs),
            "pair_follow_rate": pair_follow_rate(pairs),
            "results": [r.to_dict() for _, r in pairs],
        }

    meta = {"commit": git_commit(), "items": a.items, "n_items": len(items), "pipelines": a.pipelines,
            "spent_usd": spent, "time": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    out = Path(a.out) / f"run_{time.strftime('%Y%m%d-%H%M%S')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"meta": meta, "report": report}, indent=2))
    print(f"\nwrote {out}  (spent ${spent:.4f})")
    for p, rep in report.items():
        s = rep["summary"]["all"]
        print(f"{p:>18} acc={s['accuracy']} hit={s['evidence_hit@0.3']} cost/q=${s['cost_usd_mean']:.4f}")


if __name__ == "__main__":
    main()
