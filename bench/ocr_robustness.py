"""OCR-route robustness to scan/phone-photo degradations ($0, local; owner: claude-andrew-b).

The synthetic forms are clean renders. Real constats arrive as phone photos and scans. This runs
pipeline.ocr on the OCR-eligible items (text, layout, unanswerable) under each degradation and counts:
  exit_ok   OCR answered and the answer is correct
  exit_bad  OCR answered WRONGLY (the costly failure: no fallback, wrong claim data)
  fallback  OCR deferred to the visual path (safe, but costs a paid call)

    python -m bench.ocr_robustness [--items eval/data/accident_statement/items.jsonl] [--out eval/results/REPORT_ocr_robustness.md]
"""
from __future__ import annotations

import argparse
import io
import random
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image, ImageFilter

from eval.metrics import answer_correct
from eval.run_eval import load_items
from pipeline.router import ensure_ocr_bin


def _jpeg(im, q):
    b = io.BytesIO(); im.save(b, "JPEG", quality=q); b.seek(0)
    return Image.open(b).convert("RGB")


def _scale(im, long_side):
    s = long_side / max(im.size)
    return im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)


def _rotate(im, deg):
    return im.rotate(deg, resample=Image.BICUBIC, expand=True, fillcolor=(255, 255, 255))


def _perspective(im, k):
    w, h = im.size  # top edge narrower than bottom by k*w on each side (phone held at an angle)
    coeffs = _find_coeffs([(0, 0), (w, 0), (w, h), (0, h)], [(k * w, 0), (w - k * w, 0), (w, h), (0, h)])
    return im.transform(im.size, Image.PERSPECTIVE, coeffs, Image.BICUBIC, fillcolor=(255, 255, 255))


def _find_coeffs(dst, src):
    import numpy as np
    a = []
    for (x, y), (u, v) in zip(dst, src):
        a += [[x, y, 1, 0, 0, 0, -u * x, -u * y], [0, 0, 0, x, y, 1, -v * x, -v * y]]
    return np.linalg.solve(np.array(a, float), np.array(src, float).reshape(8)).tolist()


def _photo(im):  # combined: angle + perspective + blur + downscale + jpeg
    im = _perspective(_rotate(im, 2.5), 0.03).filter(ImageFilter.GaussianBlur(1.2))
    return _jpeg(_scale(im, 1280), 55)


DEGRADATIONS = {
    "clean": lambda im: im,
    "scale_1280": lambda im: _scale(im, 1280),
    "scale_1024": lambda im: _scale(im, 1024),
    "scale_768": lambda im: _scale(im, 768),
    "jpeg_q40": lambda im: _jpeg(im, 40),
    "blur_1.5": lambda im: im.filter(ImageFilter.GaussianBlur(1.5)),
    "rotate_2": lambda im: _rotate(im, 2),
    "rotate_5": lambda im: _rotate(im, 5),
    "perspective_3%": lambda im: _perspective(im, 0.03),
    "phone_photo": _photo,
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", default="eval/data/accident_statement/items.jsonl")
    ap.add_argument("--out", default="eval/results/REPORT_ocr_robustness.md")
    ap.add_argument("--only", nargs="*", help="subset of degradation names")
    a = ap.parse_args()
    if ensure_ocr_bin() is None:
        raise SystemExit("OCR helper unavailable (needs macOS + swiftc)")
    from pipeline.ocr import answer

    random.seed(0)
    items = [it for it in load_items(Path(a.items)) if it.evidence_type in ("text", "layout") or not it.answerable]
    by_img = defaultdict(list)
    for it in items:
        by_img[it.image_path].append(it)
    names = a.only or list(DEGRADATIONS)
    rows, bad_examples = {}, []
    for name in names:
        c = Counter()
        for path, its in by_img.items():
            with Image.open(Path(a.items).parent / path) as im:
                img = DEGRADATIONS[name](im.convert("RGB"))
            for it in its:
                r = answer(img, it.question)
                exited = not (r.route and r.route[-1].step == "fallback")
                if not exited:
                    c["fallback"] += 1
                elif answer_correct(it, r):
                    c["exit_ok"] += 1
                else:
                    c["exit_bad"] += 1
                    bad_examples.append((name, it.question_id, it.answer, r.answer))
        c["n"] = sum(len(v) for v in by_img.values())
        rows[name] = c
        print(f"{name:>15} n={c['n']} exit_ok={c['exit_ok']} exit_bad={c['exit_bad']} fallback={c['fallback']}", flush=True)

    answerable = sum(1 for it in items if it.answerable)
    lines = [
        "# OCR route robustness to scan / phone-photo degradations",
        "",
        f"`python -m bench.ocr_robustness` · {len(items)} OCR-eligible items ({answerable} answerable text/layout, "
        f"{len(items) - answerable} unanswerable) from `{a.items}` · Apple Vision, local, $0.",
        "",
        "| degradation | exit correct | **exit wrong** | fallback to visual |",
        "|---|---:|---:|---:|",
    ]
    lines += [f"| {k} | {v['exit_ok']} | **{v['exit_bad']}** | {v['fallback']} |" for k, v in rows.items()]
    if bad_examples:
        lines += ["", "Wrong exits (degradation, item, gold, OCR answer):", ""]
        lines += [f"- {n} · `{q}` · gold `{g}` · got `{o}`" for n, q, g, o in bad_examples[:30]]
    Path(a.out).write_text("\n".join(lines) + "\n")
    print("wrote", a.out)


if __name__ == "__main__":
    main()
