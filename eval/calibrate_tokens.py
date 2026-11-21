"""Fit billed input tokens against the pixels actually sent: replaces the w·h/750 assumption (message 066/067).

    python -m eval.calibrate_tokens eval/results/paid_*/run_*.json [--out eval/results/token_calibration.json]

Uses every API call (provider != local/fake/estimate) that recorded `image_px`. Per served model it fits
    billed_input_tokens ≈ text_base + k · total_pixels
by least squares (stdlib only), where billed input = uncached input + cache reads + cache writes, and prints the fit,
the implied "pixels per token" (cf. the 750 assumption), and residuals per image size. A provider that downscales
large images makes big pages fall below the line; the per-size table shows it.

The output JSON (`{model: {"text_base": .., "tokens_per_pixel": .., "n": .., "max_rel_residual": ..}}`) is MEASURED-
calibrated: valid for the models, sizes and prompt lengths seen, not beyond.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def points(runs: list[str]):
    by_model: dict[str, list[tuple[float, float, str]]] = defaultdict(list)
    for path in runs:
        run = json.loads(Path(path).read_text())
        for name, rep in run["report"].items():
            for r in rep.get("results", []):
                for u in r.get("usage", []):
                    if u.get("provider") in ("local", "fake", "estimate", None) or not u.get("image_px"):
                        continue
                    px = sum(w * h for w, h in u["image_px"])
                    tok = (u.get("input_text_tokens", 0) + u.get("input_image_tokens", 0)
                           + u.get("cache_read_tokens", 0) + u.get("cache_write_tokens", 0))
                    if tok > 0:
                        size = "+".join(f"{w}x{h}" for w, h in u["image_px"])
                        by_model[u.get("model") or "?"].append((px, tok, size))
    return by_model


def fit(pts: list[tuple[float, float, str]]) -> tuple[float, float]:
    n = len(pts)
    mx = sum(p[0] for p in pts) / n
    my = sum(p[1] for p in pts) / n
    sxx = sum((p[0] - mx) ** 2 for p in pts)
    if sxx == 0:
        return my, 0.0
    k = sum((p[0] - mx) * (p[1] - my) for p in pts) / sxx
    return my - k * mx, k


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--out", default="eval/results/token_calibration.json")
    a = ap.parse_args()
    out = {}
    for model, pts in sorted(points(a.runs).items()):
        if len(pts) < 2:
            print(f"{model}: only {len(pts)} point(s), skipped")
            continue
        c, k = fit(pts)
        rel = [abs((c + k * px) - tok) / tok for px, tok, _ in pts]
        out[model] = {"text_base": round(c, 1), "tokens_per_pixel": k, "pixels_per_token": round(1 / k, 1) if k else None,
                      "n": len(pts), "max_rel_residual": round(max(rel), 3)}
        print(f"\n{model}: tokens ≈ {c:.0f} + {k:.6f}·pixels  (≈ 1 token per {1 / k if k else float('inf'):.0f} px; "
              f"assumption was 750) · n={len(pts)} · max residual {max(rel):.1%}")
        by_size: dict[str, list[float]] = defaultdict(list)
        for px, tok, size in pts:
            by_size[size].append(tok)
        for size, toks in sorted(by_size.items(), key=lambda kv: -len(kv[1]))[:8]:
            w, h = size.split("+")[0].split("x")
            print(f"  {size:>22}  n={len(toks):>3}  billed median {sorted(toks)[len(toks) // 2]:>6.0f}  "
                  f"w·h/750 = {int(w) * int(h) / 750:>6.0f}")
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, indent=2))
    print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
