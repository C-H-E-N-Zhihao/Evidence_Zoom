"""Fixture REPLAY backend for the visual path: NOT a model.

Given a gold-labelled EvalItem, it plays the role of the vision model: the overview step asks to zoom
on exactly the grid cells covering the gold evidence (non-adjacent cells -> row-aligned mosaic), and
the zoom step answers with the gold answer and the gold box in crop coordinates. Everything the
pipeline does around it (overview rendering, cell selection, mosaic crop, box mapping back to the
page) is the real code path.

Used by the offline self-test and by the app's key-free rehearsal (DEMO_REPLAY=1). Every Usage record
it emits has provider="replay" and a note saying so. Token counts are ESTIMATES (~w*h/750) of what a
model would be sent, priced as if served by `price_as` so the cost meter shows the would-be cost.
"""
from __future__ import annotations

import json
import math

from eval.pricing import cost_usd
from eval.schema import EvalItem, Usage

from . import Axis

NOTE = "REPLAY of fixture gold labels, not a model answer; tokens estimated"


def _cells_covering(box, rows, cols):
    c0, c1 = max(1, math.floor(box[0] * cols) + 1), min(cols, math.ceil(box[2] * cols))
    r0, r1 = max(1, math.floor(box[1] * rows) + 1), min(rows, math.ceil(box[3] * rows))
    return {(r, c) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)}


def _to_view(v: float, spans: list, px: int) -> float:
    """Original coord -> stitched coord (normalized), mirroring pipeline.visual.Axis."""
    axis = Axis(spans, px)
    for (a, b), off, n in zip(axis.spans, axis.offsets(), axis.lens):
        if a - 1e-9 <= v <= b + 1e-9:
            return (off + (v - a) / (b - a) * n) / axis.total
    # Outside every band (e.g. a gold edge a hair beyond the crop): snap to the nearest band edge, not to 0.
    edges = [(abs(v - a), off / axis.total) for (a, b), off, n in zip(axis.spans, axis.offsets(), axis.lens)]
    edges += [(abs(v - b), (off + n) / axis.total) for (a, b), off, n in zip(axis.spans, axis.offsets(), axis.lens)]
    return min(edges)[1]


def oracle(item: EvalItem, size: tuple[int, int], grid=(8, 6), price_as: str = "claude-opus-5-5",
           on_call=None):
    """Backend with anthropic_backend.call's signature that replays `item`'s gold labels."""
    rows, cols = grid
    state = {"calls": 0, "sel": None}

    def call(content, *, step_index, system, model, images_px, view_spans=None, **_):
        w, h = images_px[0]
        state["calls"] += 1
        if on_call is not None:
            on_call(content, state["calls"])
        u = Usage(step_index, "replay", price_as, input_text_tokens=len(system) // 4 + 40,
                  input_image_tokens=max(1, round(w * h / 750)), output_tokens=40,
                  estimated=True, image_px=images_px, note=NOTE)
        u.cost_usd = cost_usd(u)
        if not item.answerable or not item.evidence_boxes:
            return json.dumps({"action": "answer", "answer": None, "abstain": True}), u, "end_turn"
        if view_spans is not None:  # direct zoom (anchor crop or page fallback): answer on this view at once
            yspans, xspans = view_spans
            g = item.evidence_boxes[0]
            vb = [_to_view(g[0], xspans, size[0]), _to_view(g[1], yspans, size[1]),
                  _to_view(g[2], xspans, size[0]), _to_view(g[3], yspans, size[1])]
            return json.dumps({"action": "answer", "answer": item.answer, "abstain": False, "box": vb}), u, "end_turn"
        if state["calls"] == 1:
            rc = set().union(*(_cells_covering(b, rows, cols) for b in item.evidence_boxes))
            state["sel"] = ({r for r, _ in rc}, {c for _, c in rc})
            cells = [f"R{r}C{c}" for r, c in sorted(rc)]
            return json.dumps({"action": "zoom", "cells": cells, "look_for": "fixture evidence"}), u, "end_turn"
        rs, cs = state["sel"]
        yspans = [((r - 1) / rows, r / rows) for r in rs]
        xspans = [((c - 1) / cols, c / cols) for c in cs]
        g = item.evidence_boxes[0]
        vb = [_to_view(g[0], xspans, size[0]), _to_view(g[1], yspans, size[1]),
              _to_view(g[2], xspans, size[0]), _to_view(g[3], yspans, size[1])]
        return json.dumps({"action": "answer", "answer": item.answer, "abstain": False, "box": vb}), u, "end_turn"

    call.direct_zoom = True  # pipeline.router keeps the shipped route (anchor, page fallback) under this oracle
    return call


def unavailable(question: str):
    """Backend for a question with no fixture label: fails loudly instead of inventing an answer."""
    def call(*_, **__):
        raise LookupError(f"no fixture replay for this question (key-free demo): {question!r}")
    call.direct_zoom = True  # follows the shipped route too, and fails loudly at the first model call
    return call
