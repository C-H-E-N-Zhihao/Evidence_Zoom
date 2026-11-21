"""Offline self-test of the visual path with an ORACLE fake backend (no API key, $0).

The oracle requests a zoom on exactly the grid cells covering the gold evidence and answers with
the gold answer and the gold box expressed in crop coordinates. If the geometry (grid -> cells ->
crop -> box mapping) is right, evidence IoU against gold must be ~1 and accuracy 1.0.
Token counts are ESTIMATES (~w*h/750); costs are priced with eval/pricing.py.

    python -m pipeline.visual.selftest [--items eval/data/accident_statement/items.jsonl] [--save-views DIR]
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

from eval.metrics import cost_curve, summarize
from eval.run_eval import load_items
from eval.schema import EvalItem

from . import answer, replay


def oracle(item: EvalItem, size, grid=(8, 6), save_views: Path | None = None):
    def dump(content, n):
        if save_views is not None:
            import base64, io
            data = base64.b64decode(content[0]["source"]["data"])
            Image.open(io.BytesIO(data)).save(save_views / f"{item.question_id}_{n}.png")
    return replay.oracle(item, size, grid, on_call=dump)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", default="eval/data/accident_statement/items.jsonl")
    ap.add_argument("--save-views", default=None, help="dir to dump the images actually sent")
    ap.add_argument("--router", action="store_true",
                    help="run pipeline.router (real OCR first, oracle visual on fallback)")
    a = ap.parse_args()
    sv = Path(a.save_views) if a.save_views else None
    if sv:
        sv.mkdir(parents=True, exist_ok=True)
    pairs, cache = [], {}
    for it in load_items(Path(a.items)):
        img = cache.setdefault(it.image_path, Image.open(it.image_path).convert("RGB"))
        if a.router:
            import pipeline.router as router
            import pipeline.visual as visual
            visual.CALL_OVERRIDE = oracle(it, img.size, save_views=sv)
            r = router.answer(img, it.question)
        else:
            r = answer(img, it.question, call=oracle(it, img.size, save_views=sv), name="visual_oracle")
        r.question_id, r.image_id = it.question_id, it.image_id
        pairs.append((it, r))
    s = summarize(pairs)
    for k in ("all", "text", "layout", "visual"):
        if k in s:
            g = s[k]
            print(f"{k:>7} n={g.get('n')} acc={g.get('accuracy')} hit@0.3={g.get('evidence_hit@0.3')} "
                  f"iou={g.get('evidence_iou_mean')} cost/q=${g.get('cost_usd_mean', 0):.5f} (estimated)")
    by_q: dict[str, list] = {}
    for it, r in pairs:
        for u in r.usage[1:]:
            by_q.setdefault(it.question_id.split("-")[-1], []).append(u.input_image_tokens)
    from app.costs import image_tokens
    full = image_tokens(1700, 2200)
    print(f"zoom image tokens by question (median; full image ~{full}):",
          {q: sorted(v)[len(v) // 2] for q, v in sorted(by_q.items())})
    if a.router:
        exits = sum(1 for _, r in pairs if r.route and r.route[0].step == "ocr" and len(r.usage) == 1)
        print(f"OCR exits: {exits}/{len(pairs)}; errors: {sum(r.error is not None for _, r in pairs)}")
    print("cost curve (estimated):", cost_curve(pairs)[:4] if cost_curve(pairs) else None)


if __name__ == "__main__":
    main()
