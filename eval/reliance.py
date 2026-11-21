"""Reliance tests (004 day two): does the answer actually depend on the region it cites?

For each item and a base pipeline's result (its cited box, else the gold box):
  - only_cited    : image with everything outside the cited box greyed out -> answer should survive
  - remove_cited  : cited box greyed out                                  -> answer should change / abstain
  - remove_random : a size-matched box elsewhere greyed out (seeded)       -> answer should survive
Counterfactual value swaps use dataset pairs (`pair_id`): same form, different tick/value; scored by
running any pipeline on both members and checking the answer follows the edit.

    python -m eval.reliance --items eval/data/<set>/items.jsonl --pipeline full_image --limit 10 --max-cost 0.5

Caveat (004): masking artifacts and duplicated evidence elsewhere in the page complicate interpretation; report
per evidence type and inspect samples, do not rely on the aggregate alone.
"""
from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

from PIL import Image, ImageDraw

from .metrics import answer_correct, norm
from .run_eval import get_pipeline, load_items
from .schema import Box, EvalItem, PipelineResult

GREY = (128, 128, 128)


def _px(box: Box, img: Image.Image) -> tuple[int, int, int, int]:
    return (round(box[0] * img.width), round(box[1] * img.height), round(box[2] * img.width), round(box[3] * img.height))


def mask_inside(img: Image.Image, box: Box) -> Image.Image:
    out = img.copy()
    ImageDraw.Draw(out).rectangle(_px(box, img), fill=GREY)
    return out


def mask_outside(img: Image.Image, box: Box) -> Image.Image:
    out = Image.new("RGB", img.size, GREY)
    p = _px(box, img)
    out.paste(img.crop(p), p[:2])
    return out


def random_box_like(box: Box, rng: random.Random, avoid: Box, tries: int = 50) -> Box:
    """Same width/height, placed elsewhere, overlapping `avoid` as little as possible."""
    w, h = box[2] - box[0], box[3] - box[1]
    best, best_ov = None, 2.0
    for _ in range(tries):
        x0, y0 = rng.uniform(0, max(0.0, 1 - w)), rng.uniform(0, max(0.0, 1 - h))
        cand = [x0, y0, x0 + w, y0 + h]
        ix = max(0.0, min(cand[2], avoid[2]) - max(cand[0], avoid[0]))
        iy = max(0.0, min(cand[3], avoid[3]) - max(cand[1], avoid[1]))
        ov = ix * iy / max(w * h, 1e-9)
        if ov < best_ov:
            best, best_ov = cand, ov
        if ov == 0:
            break
    return best


def same_answer(a: PipelineResult, b: PipelineResult) -> bool:
    if a.abstained or b.abstained or a.answer is None or b.answer is None:
        return a.abstained == b.abstained
    return norm(a.answer) == norm(b.answer)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", required=True)
    ap.add_argument("--pipeline", default="full_image")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--max-cost", type=float, default=0.5)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default="eval/results")
    a = ap.parse_args()

    rng = random.Random(a.seed)
    pipe = get_pipeline(a.pipeline)
    items = [it for it in load_items(Path(a.items)) if it.answerable][: a.limit]
    spent, rows = 0.0, []
    for it in items:
        if spent >= a.max_cost:
            print(f"[stop] max cost ${a.max_cost:.2f} reached")
            break
        img = Image.open(it.image_path).convert("RGB")
        base = pipe(it, img)
        cited = base.evidence_boxes[0].box if base.evidence_boxes else (it.evidence_boxes[0] if it.evidence_boxes else None)
        if cited is None:
            continue
        rnd = random_box_like(cited, rng, avoid=cited)
        variants = {
            "only_cited": pipe(it, mask_outside(img, cited)),
            "remove_cited": pipe(it, mask_inside(img, cited)),
            "remove_random": pipe(it, mask_inside(img, rnd)),
        }
        spent += base.total_cost() + sum(v.total_cost() for v in variants.values())
        row = {
            "question_id": it.question_id, "evidence_type": it.evidence_type, "cited_box": cited,
            "cited_from": "model" if base.evidence_boxes else "gold", "random_box": rnd,
            "base_correct": answer_correct(it, base), "base_answer": base.answer,
        }
        for k, v in variants.items():
            row[f"{k}_answer"] = v.answer
            row[f"{k}_same_as_base"] = same_answer(base, v)
            row[f"{k}_correct"] = answer_correct(it, v)
        rows.append(row)
        print(f"{it.question_id}: base={base.answer!r:.30} only={row['only_cited_same_as_base']} "
              f"rm_cited_changed={not row['remove_cited_same_as_base']} rm_rand_same={row['remove_random_same_as_base']}")

    def rate(key: str, want: bool) -> float | None:
        vals = [r[key] == want for r in rows if r["base_correct"]]
        return sum(vals) / len(vals) if vals else None

    summary = {
        "n": len(rows),
        "n_base_correct": sum(r["base_correct"] for r in rows),
        "sufficiency_only_cited_kept": rate("only_cited_same_as_base", True),
        "necessity_remove_cited_changed": rate("remove_cited_same_as_base", False),
        "control_remove_random_kept": rate("remove_random_same_as_base", True),
    }
    out = Path(a.out) / f"reliance_{a.pipeline}_{time.strftime('%Y%m%d-%H%M%S')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"pipeline": a.pipeline, "seed": a.seed, "spent_usd": spent,
                               "summary": summary, "rows": rows}, indent=2))
    print(json.dumps(summary, indent=2), f"\nwrote {out} (spent ${spent:.4f})")


def pair_follow_rate(pairs: list[tuple[EvalItem, PipelineResult]]) -> float | None:
    """Value-swap test from counterfactual pairs: within each pair_id, items with different gold answers should
    get different predicted answers, each correct. Returns the fraction of pairs where both are correct."""
    by_pair: dict[str, list] = {}
    for it, r in pairs:
        if it.pair_id:
            by_pair.setdefault(it.pair_id, []).append((it, r))
    ok = [all(answer_correct(i, r) for i, r in ps) for ps in by_pair.values()
          if len(ps) >= 2 and len({norm(i.answer or "") for i, _ in ps}) > 1]
    return sum(ok) / len(ok) if ok else None


if __name__ == "__main__":
    main()
