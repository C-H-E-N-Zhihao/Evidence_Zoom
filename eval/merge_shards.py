"""Merge the run JSONs of a sharded evaluation (scripts/shard_eval.sh) into one run JSON, re-scored over all items.

    python -m eval.merge_shards --items eval/data/<set>/items.jsonl --runs OUT/shard*/run_*.json --out OUT/merged.json

Per pipeline: results from every shard are joined to the ORIGINAL item file by question_id, then summarize(),
cost_curve() and pair_follow_rate() are recomputed on the union, so the numbers are those of one run over the set.
Shard-level facts are kept, not hidden: spent_usd is summed, `aborted` lists each shard that aborted, `complete` is
True only if every item of the set has exactly one result, and duplicates or unknown question_ids are reported.
Meta keeps each shard's provenance (commit, pipeline tree, freeze tag, dirty flags, image digest) under `shards`.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .metrics import cost_curve, summarize
from .run_eval import load_items
from .schema import PipelineResult


def merge(items_path: str, run_paths: list[str]) -> dict:
    from .reliance import pair_follow_rate

    items = load_items(Path(items_path))
    by_qid = {it.question_id: it for it in items}
    runs = [json.loads(Path(p).read_text()) for p in run_paths]
    pipes: dict[str, dict] = {}
    for p, run in zip(run_paths, runs):
        for name, rep in run["report"].items():
            agg = pipes.setdefault(name, {"results": [], "aborted": [], "degraded": 0, "shards": 0})
            agg["results"] += rep.get("results", [])
            agg["degraded"] += rep.get("degraded", 0) or 0
            agg["shards"] += 1
            if rep.get("aborted"):
                agg["aborted"].append(f"{p}: {rep['aborted']}")
    report = {}
    for name, agg in pipes.items():
        seen, pairs, dup, unknown = set(), [], [], []
        for d in agg["results"]:
            r = PipelineResult.from_dict(d)
            q = r.question_id
            if q not in by_qid:
                unknown.append(q)
                continue
            if q in seen:
                dup.append(q)
                continue
            seen.add(q)
            pairs.append((by_qid[q], r))
        order = {it.question_id: i for i, it in enumerate(items)}  # dataset order, so cost_curve groups as one run
        pairs.sort(key=lambda p: order[p[0].question_id])
        report[name] = {
            "summary": summarize(pairs),
            "cost_curve": cost_curve(pairs),
            "pair_follow_rate": pair_follow_rate(pairs),
            "degraded": agg["degraded"],
            "aborted": agg["aborted"] or None,
            "complete": len(seen) == len(items) and not dup and not unknown,
            "missing": sorted(set(by_qid) - seen),
            "duplicates": dup,
            "unknown_question_ids": unknown,
            "n_shards": agg["shards"],
            "results": [r.to_dict() for _, r in pairs],
        }
    metas = [r.get("meta", {}) for r in runs]
    keys = ("commit", "pipeline_tree", "pipeline_dirty", "eval_dirty", "freeze_tag", "pipeline_equals_freeze",
            "images_digest", "degrade", "time", "spent_usd", "budget_hit")
    meta = {"merged_from": run_paths, "items": items_path, "n_items": len(items),
            "pipelines": sorted(pipes), "spent_usd": sum(m.get("spent_usd", 0.0) for m in metas),
            "budget_hit": any(m.get("budget_hit") for m in metas),
            "same_code_all_shards": len({(m.get("commit"), m.get("pipeline_tree"), m.get("pipeline_dirty"))
                                         for m in metas}) == 1,
            "shards": [{k: m.get(k) for k in keys} for m in metas]}
    return {"meta": meta, "report": report}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", required=True, help="the ORIGINAL (unsharded) items.jsonl")
    ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = merge(a.items, a.runs)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, indent=2))
    print(f"wrote {a.out}  (spent ${out['meta']['spent_usd']:.4f}, same code: {out['meta']['same_code_all_shards']})")
    for p, rep in out["report"].items():
        s = rep["summary"]["all"]
        print(f"{p:>18} n={s['n']} acc={s['accuracy']} complete={rep['complete']} missing={len(rep['missing'])} "
              f"dup={len(rep['duplicates'])} aborted={bool(rep['aborted'])}")


if __name__ == "__main__":
    main()
