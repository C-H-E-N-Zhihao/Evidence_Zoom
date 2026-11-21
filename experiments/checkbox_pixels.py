"""Offline control for the two 17-row checkbox columns on the simplified accident statement.

Run: python3 -m experiments.checkbox_pixels [--items path/to/items.jsonl]
Requires Pillow, NumPy and SciPy. The detector takes only pixels. Left/right and
row order are template assumptions. An unknown layout or ambiguous ink yields no answer.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
from time import perf_counter

import numpy as np
from PIL import Image
from scipy import ndimage


def read_columns(image, max_side=1200):
    gray = image.convert("L")
    gray.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    dark = np.asarray(gray) < 180
    h, w = dark.shape
    components, _ = ndimage.label(dark)
    groups = {}
    for region in ndimage.find_objects(components):
        if region is None:
            continue
        ys, xs = region
        width, height = xs.stop - xs.start, ys.stop - ys.start
        if not (8 <= width <= .05*w and .85*width <= height <= 1.15*width):
            continue
        patch = dark[region]
        if min(patch[:2].any(axis=0).mean(), patch[-2:].any(axis=0).mean(),
               patch[:, :2].any(axis=1).mean(), patch[:, -2:].any(axis=1).mean()) < .85:
            continue
        margin = max(2, round(width*.18))
        ink = patch[margin:-margin, margin:-margin].mean()
        groups.setdefault(xs.start, []).append((ys.start, ink))
    columns = []
    for x, rows in sorted(groups.items()):
        if len(rows) != 17:
            continue
        rows.sort()
        gaps = np.diff([y for y, _ in rows])
        if max(gaps) > 1.12*min(gaps) or any(.025 < ink < .09 for _, ink in rows):
            continue
        columns.append((x, rows))
    if len(columns) != 2 or columns[1][0]-columns[0][0] < w/3:
        return None
    if any(abs(a[0]-b[0]) > 2 for a,b in zip(columns[0][1], columns[1][1])):
        return None
    return {side: [n for n, (_, ink) in enumerate(rows, 1) if ink >= .09]
            for side, (_, rows) in zip("AB", columns)}


def answer(columns, question):
    if columns is None:
        return None
    q = question.lower()
    group = re.fullmatch(r"which circumstance boxes did driver ([ab]) tick\?(?: answer with the box numbers\.)?", q)
    if group:
        return ", ".join(map(str, columns[group[1].upper()])) or "none"
    single = re.fullmatch(r"did driver ([ab]) tick circumstance (\d+)(?: \([^?]*\))?\?(?: answer yes or no\.)?", q)
    if single and 1 <= int(single[2]) <= 17:
        return "yes" if int(single[2]) in columns[single[1].upper()] else "no"
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--items", type=Path, default=Path("eval/data/accident_statement/items.jsonl"))
    parser.add_argument("--tilt", type=float, default=0)
    parser.add_argument("--max-side", type=int, default=1200)
    args = parser.parse_args()
    if args.max_side < 1:
        parser.error("--max-side must be positive")
    pages, counts = {}, Counter()
    start = perf_counter()
    for line in args.items.read_text().splitlines():
        item = json.loads(line)
        path = args.items.parent / item["image_path"]
        if path not in pages:
            with Image.open(path) as im:
                img = im.rotate(args.tilt, Image.Resampling.BICUBIC, expand=True, fillcolor="white") if args.tilt else im
                pages[path] = read_columns(img, args.max_side)
        prediction = answer(pages[path], item["question"])
        counts["abstain" if prediction is None else "correct" if prediction == item["answer"] else "wrong"] += 1
    print(f"{len(pages)} pages, {dict(counts)}, {perf_counter()-start:.2f}s")


if __name__ == "__main__":
    main()
