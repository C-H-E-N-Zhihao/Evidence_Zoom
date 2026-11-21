"""Declarative per-template configuration (owner: claude-andrew-b; message 093).

The built-in OCR field rules and anchor rules (pipeline/ocr, pipeline/anchor) cover accident-statement layouts
with side-by-side "Vehicle A/B" columns and "N." circumstance labels. A layout family they cannot read is added
here as a small DECLARATIVE template, written from one example image. No model, no training. The generic engine
below turns a template into the same outputs the built-in rules produce (a field value span; an anchor.Layout).

A template is used only if all of its `detect` phrases are found on the page, and every lookup still declines
(returns None) unless exactly one candidate fits, so an unknown or ambiguous page falls back as before.
"""
from __future__ import annotations

import re
from typing import Optional

TEMPLATES: dict[str, dict] = {
    # Written from ONE image of blind layout v3 (eas3-001a); evaluated on the other 11 v3 images (message 094).
    "eas_v3_banded": {
        "detect": ["13. sketch of the accident", "12. circumstances", "name of driver", "licence plate"],
        "fields": {"policy": "policy no", "registration": "licence plate", "insurer": "insurance company",
                   "driver": "name of driver"},
        "field_value": "below",              # the value is printed directly below its label
        "vehicle_order": ["a", "b"],         # n-th occurrence of a label (top to bottom) belongs to vehicle n
        "circumstances": {"heading": "12. circumstances", "row_number": "bare",   # "8", not "8."
                          "tick_columns": "left_of_numbers", "column_order": ["a", "b"]},
        "sketch": {"heading": "13. sketch"},
    },
}


def _key(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold().strip().rstrip(":").strip())


def match(spans: list[dict]) -> Optional[dict]:
    """The template whose detect phrases all appear (as span prefixes), or None. Two matches = ambiguous = None."""
    keys = [_key(s["text"]) for s in spans if s["confidence"] >= 0.5]
    hits = [t for t in TEMPLATES.values() if all(any(k.startswith(p) for k in keys) for p in t["detect"])]
    return hits[0] if len(hits) == 1 else None


# ---- fields ----------------------------------------------------------------------------------------------
def field(spans: list[dict], name: str, side: str) -> Optional[dict]:
    t = match(spans)
    if t is None or name not in t["fields"] or t["field_value"] != "below":
        return None
    order = t["vehicle_order"]
    if side not in order:
        return None
    label_text = t["fields"][name]
    labels = sorted((s for s in spans if _key(s["text"]) == label_text and s["confidence"] >= 0.8),
                    key=lambda s: s["box"][1])
    if len(labels) != len(order):
        return None
    lb = labels[order.index(side)]["box"]
    all_labels = {v for v in t["fields"].values()}
    below = [s for s in spans if _key(s["text"]) not in all_labels
             and lb[0] - 0.01 <= s["box"][0] <= lb[0] + 0.03          # left-aligned with the label
             and lb[3] - 0.002 <= s["box"][1] <= lb[3] + 0.03]        # directly below it
    return below[0] if len(below) == 1 and below[0]["confidence"] >= 0.8 else None


# ---- anchor layout -----------------------------------------------------------------------------------------
def _box_columns(image, band, xrange, dark=180) -> list[float]:
    """Centres (normalised x) of columns of square box outlines in `xrange` over the rows `band`: each column
    shows as two vertical edges dark over 40-95% of the band, 1.2-3.5% of the page width apart. `dark` is a
    lighter threshold than the built-in one, so coloured (e.g. orange) outlines count."""
    import numpy as np

    g = np.asarray(image.convert("L"))
    h, w = g.shape
    y0, y1 = int(band[0] * h), int(band[1] * h)
    x0, x1 = int(xrange[0] * w), int(xrange[1] * w)
    if y1 - y0 < 20 or x1 - x0 < 10:
        return []
    prof = (g[y0:y1, x0:x1] < dark).mean(0)
    edges = []
    for x in (x0 + i for i in np.where((prof > 0.4) & (prof < 0.95))[0]):
        if edges and x - edges[-1][1] <= 2:
            edges[-1][1] = x
        else:
            edges.append([x, x])
    centers = [(a + b) / 2 for a, b in edges]
    cols, used = [], set()
    for i, c1 in enumerate(centers):  # pair neighbouring edges into boxes
        if i in used or i + 1 >= len(centers):
            continue
        c2 = centers[i + 1]
        if 0.012 * w <= c2 - c1 <= 0.035 * w:
            cols.append((c1 + c2) / 2 / w)
            used |= {i, i + 1}
    return cols


def layout(spans: list[dict], image):
    """anchor.Layout for a matching template, or None."""
    from pipeline.anchor import Layout, _fill_rows

    t = match(spans)
    if t is None or "circumstances" not in t:
        return None
    c = t["circumstances"]
    heads = [s for s in spans if _key(s["text"]).startswith(c["heading"])]
    if len(heads) != 1:
        return None
    top = heads[0]["box"][3]
    sk = [s for s in spans if _key(s["text"]).startswith(t["sketch"]["heading"])] if "sketch" in t else []
    bottom = sk[0]["box"][1] if len(sk) == 1 and sk[0]["box"][1] > top else 1.0
    if c["row_number"] != "bare":
        return None
    nums = [s for s in spans if re.fullmatch(r"\d{1,2}", s["text"].strip()) and top < s["box"][1] < bottom
            and 1 <= int(s["text"]) <= 17 and s["confidence"] >= 0.5]
    if not nums:
        return None
    x_med = sorted(s["box"][0] for s in nums)[len(nums) // 2]
    rows, x1s = {}, {}
    for s in nums:
        n = int(s["text"])
        if abs(s["box"][0] - x_med) < 0.012 and n not in rows:
            rows[n] = (s["box"][1], s["box"][3])
    if len(rows) < 12:
        return None
    rows = _fill_rows(rows)
    num_right = max(s["box"][2] for s in nums if abs(s["box"][0] - x_med) < 0.012)
    for n, (y0, y1) in rows.items():  # right edge of the circumstance text on each row
        txt = [s["box"][2] for s in spans if s["box"][0] > num_right and min(y1, s["box"][3]) - max(y0, s["box"][1]) > 0]
        x1s[n] = max(txt) if txt else num_right + 0.3
    if c["tick_columns"] != "left_of_numbers":
        return None
    centers = _box_columns(image, (rows[1][0], rows[17][1]), (0.0, x_med - 0.003))
    if len(centers) != len(c["column_order"]):
        return None
    cols = {side: (float(x) - 0.02, float(x) + 0.02) for side, x in zip(c["column_order"], sorted(centers))}
    sketch = None
    if len(sk) == 1:
        s0 = sk[0]["box"][3] + 0.003
        sketch = (s0, min(1.0, s0 + 0.22, *([heads[0]["box"][1] - 0.005] if heads[0]["box"][1] > s0 else [])))
    return Layout(rows, x_med, x1s, cols, sketch)
