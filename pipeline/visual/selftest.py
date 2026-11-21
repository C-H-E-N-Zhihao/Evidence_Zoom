"""Offline self-test of the visual path with an ORACLE fake backend (no API key, $0).

The oracle requests a zoom on exactly the grid cells covering the gold evidence and answers with
the gold answer and the gold box expressed in crop coordinates. If the geometry (grid -> cells ->
crop -> box mapping) is right, evidence IoU against gold must be ~1 and accuracy 1.0.
Token counts are ESTIMATES (~w*h/750); costs are priced with eval/pricing.py.

    python -m pipeline.visual.selftest [--items eval/data/accident_statement/items.jsonl] [--save-views DIR]
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from PIL import Image

from eval.metrics import cost_curve, summarize
from eval.pricing import cost_usd
from eval.run_eval import load_items
from eval.schema import EvalItem, Usage

from . import Axis, answer


def _cells_covering(box, rows, cols):
    """Cells of the overview grid that overlap `box` (original coords; the overview covers the page)."""
    c0, c1 = max(1, math.floor(box[0] * cols) + 1), min(cols, math.ceil(box[2] * cols))
    r0, r1 = max(1, math.floor(box[1] * rows) + 1), min(rows, math.ceil(box[3] * rows))
    return {(r, c) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)}


def _to_view(v: float, spans: list, px: int) -> float:
    """Original coord -> stitched coord (normalized), mirroring pipeline.visual.Axis."""
    axis = Axis(spans, px)
    for (a, b), off, n in zip(axis.spans, axis.offsets(), axis.lens):
        if a - 1e-9 <= v <= b + 1e-9:
            return (off + (v - a) / (b - a) * n) / axis.total
    return 0.0


def oracle(item: EvalItem, size: tuple[int, int], grid=(8, 6), save_views: Path | None = None):
    """Selects every overview cell touching ANY gold box (non-adjacent -> mosaic), answers with gold."""
    rows, cols = grid
    state = {"calls": 0, "sel": None}

    def call(content, *, step_index, system, model, images_px, **_):
        w, h = images_px[0]
        state["calls"] += 1
        if save_views is not None:
            import base64, io
            data = base64.b64decode(content[0]["source"]["data"])
            Image.open(io.BytesIO(data)).save(save_views / f"{item.question_id}_{state['calls']}.png")
        u = Usage(step_index, "fake", model, input_text_tokens=len(system) // 4 + 40,
                  input_image_tokens=max(1, round(w * h / 750)), output_tokens=40,
                  estimated=True, image_px=images_px, note="oracle fake backend")
        u.cost_usd = cost_usd(u)
        if not item.evidence_boxes:  # unanswerable: abstain from the overview
            return json.dumps({"action": "answer", "answer": None, "abstain": True}), u, "end_turn"
        if state["calls"] == 1:
            rc = set().union(*(_cells_covering(b, rows, cols) for b in item.evidence_boxes))
            state["sel"] = ({r for r, _ in rc}, {c for _, c in rc})
            cells = [f"R{r}C{c}" for r, c in sorted(rc)]
            return json.dumps({"action": "zoom", "cells": cells, "look_for": "gold evidence"}), u, "end_turn"
        rs, cs = state["sel"]
        yspans = [((r - 1) / rows, r / rows) for r in rs]
        xspans = [((c - 1) / cols, c / cols) for c in cs]
        g = item.evidence_boxes[0]
        vb = [_to_view(g[0], xspans, size[0]), _to_view(g[1], yspans, size[1]),
              _to_view(g[2], xspans, size[0]), _to_view(g[3], yspans, size[1])]
        return json.dumps({"action": "answer", "answer": item.answer, "abstain": False, "box": vb}), u, "end_turn"

    return call


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
