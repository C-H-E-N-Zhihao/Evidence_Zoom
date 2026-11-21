"""Measure how the backend bills images of different sizes, before any paid run.

Uses the free count_tokens endpoint: tokens(image + "x") - tokens("x") = image tokens.
Answers 004/006's question: does an overview + native-size crop actually cost less than the full image?

    python -m eval.billing_probe --image path/to/page.png --out eval/results/billing_probe.json

Sizes probed: full image, long side in --overview sizes (aspect kept), and square native crops in --crops.
Also records whether a crop upscaled to the full size costs as much as the full image (the 004 trap).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image

from .backends import anthropic_backend as ab


def resize_long_side(img: Image.Image, long_side: int) -> Image.Image:
    w, h = img.size
    s = long_side / max(w, h)
    return img.resize((max(1, round(w * s)), max(1, round(h * s))), Image.LANCZOS)


def image_tokens(img: Image.Image, model: str, base: int) -> int:
    return ab.count_tokens([ab.image_block(img), {"type": "text", "text": "x"}], model=model) - base


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--model", default=ab.DEFAULT_MODEL)
    ap.add_argument("--overview", type=int, nargs="*", default=[256, 384, 512, 768, 1024])
    ap.add_argument("--crops", type=int, nargs="*", default=[128, 256, 384, 512])
    ap.add_argument("--out", default="eval/results/billing_probe.json")
    a = ap.parse_args()

    img = Image.open(a.image).convert("RGB")
    base = ab.count_tokens([{"type": "text", "text": "x"}], model=a.model)
    rows = [{"kind": "full", "px": list(img.size), "tokens": image_tokens(img, a.model, base)}]
    for s in a.overview:
        im = resize_long_side(img, s)
        rows.append({"kind": "overview", "px": list(im.size), "tokens": image_tokens(im, a.model, base)})
    for s in a.crops:
        crop = img.crop((0, 0, min(s, img.width), min(s, img.height)))
        rows.append({"kind": "crop_native", "px": list(crop.size), "tokens": image_tokens(crop, a.model, base)})
        up = crop.resize(img.size, Image.LANCZOS)
        rows.append({"kind": "crop_upscaled_to_full", "px": list(up.size), "tokens": image_tokens(up, a.model, base)})
    for r in rows:
        r["tokens_per_px_x750"] = round(r["tokens"] * 750 / (r["px"][0] * r["px"][1]), 3)

    out = {"model": a.model, "image": a.image, "text_base_tokens": base, "rows": rows, "estimated": False}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, indent=2))
    for r in rows:
        print(f"{r['kind']:>22} {r['px'][0]:>5}x{r['px'][1]:<5} {r['tokens']:>6} tok  (tok*750/px = {r['tokens_per_px_x750']})")


if __name__ == "__main__":
    main()
