"""Score a patch-grid heatmap against gold evidence boxes (message 180: phrase -> location head, transfer test).

A head outputs one score per cell of an R x C grid laid over the whole image (row-major, row 0 at the top). Gold boxes
are normalized [x0, y0, x1, y1] on the same image, as in EvalItem.evidence_boxes. Pure functions, stdlib only.

    from eval.grid_coverage import score_item, summarize_grid
    s = score_item(scores_16x16, item.evidence_boxes, k=16)   # one item
    summarize_grid([s, ...])                                   # means plus the random baselines to compare against

Metrics per item. With several gold boxes, "the box" means the union of their cells, fixed before scoring:
- `centre_in_topk`: some gold box centre falls in one of the k highest-scoring cells. Random rate with m distinct
  centre cells: 1 - C(N-m, k) / C(N, k) (= k/N for one box).
- `box_cells_in_topk`: share of the top-k cells that overlap the box. Random rate = share of grid cells that
  overlap it (reported per item as `box_cells_rate`), so small boxes are not penalised relative to big ones.
- `mass_in_box`: share of non-negative score mass on cells overlapping the box (scores clipped at 0, no softmax).
- `argmax_hit`: the single best cell overlaps the box (the pointing-hit analogue on documents).
Compare each mean with its random rate as a ratio of means (summarize_grid gives both).
"""
from __future__ import annotations

from math import comb
from statistics import mean


def _cells_overlapping(box: list[float], rows: int, cols: int) -> set[int]:
    x0, y0, x1, y1 = (min(max(v, 0.0), 1.0) for v in box)
    out = set()
    for r in range(rows):
        if (r + 1) / rows <= y0 or r / rows >= y1:
            continue
        for c in range(cols):
            if (c + 1) / cols <= x0 or c / cols >= x1:
                continue
            out.add(r * cols + c)
    return out


def _cell_of(x: float, y: float, rows: int, cols: int) -> int:
    r = min(int(min(max(y, 0.0), 1.0) * rows), rows - 1)
    c = min(int(min(max(x, 0.0), 1.0) * cols), cols - 1)
    return r * cols + c


def score_item(scores: list[list[float]] | list[float], gold_boxes: list[list[float]], k: int = 16,
               rows: int | None = None, cols: int | None = None) -> dict | None:
    """Metrics for one heatmap. `scores` is a nested R x C list, or a flat list with rows/cols given (square if
    omitted). Returns None when the item has no gold box. Ties at the k-th score are broken by cell index."""
    if not gold_boxes:
        return None
    if scores and isinstance(scores[0], (list, tuple)):
        rows, cols = len(scores), len(scores[0])
        flat = [float(v) for row in scores for v in row]
    else:
        flat = [float(v) for v in scores]
        if rows is None or cols is None:
            side = int(round(len(flat) ** 0.5))
            rows, cols = side, side
    n = rows * cols
    if len(flat) != n:
        raise ValueError(f"{len(flat)} scores for a {rows}x{cols} grid")
    k = max(1, min(k, n))
    order = sorted(range(n), key=lambda i: (-flat[i], i))
    top = set(order[:k])
    pos = [max(v, 0.0) for v in flat]
    total = sum(pos)
    # Fixed before scoring (codex-guanyu, grid-null): overlap metrics use the UNION of all gold boxes' cells, and the
    # centre metric accepts any of the m distinct gold centre cells, so the random rates below are exact.
    cells: set[int] = set()
    centres: set[int] = set()
    for b in gold_boxes:
        cells |= _cells_overlapping(b, rows, cols)
        centres.add(_cell_of((b[0] + b[2]) / 2, (b[1] + b[3]) / 2, rows, cols))
    m = len(centres)
    return {
        "centre_in_topk": bool(top & centres),
        # P(k uniform cells without replacement hit at least one of m centres) = 1 - C(N-m, k) / C(N, k)
        "random_centre_rate": 1.0 - (comb(n - m, k) / comb(n, k)),
        "box_cells_in_topk": len(top & cells) / k,
        "box_cells_rate": len(cells) / n,  # expected box_cells_in_topk, mass_in_box and argmax_hit under uniform
        "mass_in_box": (sum(pos[i] for i in cells) / total) if total > 0 else 0.0,
        "argmax_hit": order[0] in cells,
        "k": k, "grid": [rows, cols], "n_centre_cells": m,
    }


def summarize_grid(per_item: list[dict | None]) -> dict:
    """Means over items with a gold box, each next to its random-baseline rate."""
    s = [x for x in per_item if x is not None]
    if not s:
        return {"n": 0}
    return {
        "n": len(s),
        "centre_in_topk": mean(x["centre_in_topk"] for x in s),
        "random_centre_rate": mean(x["random_centre_rate"] for x in s),
        "box_cells_in_topk": mean(x["box_cells_in_topk"] for x in s),
        "random_box_cells_rate": mean(x["box_cells_rate"] for x in s),
        "mass_in_box": mean(x["mass_in_box"] for x in s),
        "argmax_hit": mean(x["argmax_hit"] for x in s),
        "random_argmax_rate": mean(x["box_cells_rate"] for x in s),
    }
