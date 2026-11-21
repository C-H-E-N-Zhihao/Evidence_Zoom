"""Offline scorecard ($0, no key): what we MEASURED, what the ORACLE shows, what is ESTIMATED.

    ROUTER_REQUIRE_OCR=1 python -m eval.scorecard [--items eval/data/accident_statement/items.jsonl] \
        [--models claude-opus-5-5 claude-sonnet-5-5 claude-haiku-5-5] [--out eval/results/SCORECARD.md]

Needs macOS (the OCR route uses Apple Vision). Runs pipeline.router with the REAL OCR route and an ORACLE visual
backend (pipeline.visual.selftest.oracle: selects the gold cells and answers with gold). Every number in the output
carries one of three labels:

  MEASURED   observed on this machine: OCR exits, OCR correctness, wrong exits, OCR latency, route mix
  ORACLE     visual path with gold selection and gold answers: checks geometry (crop, mosaic, box mapping) only;
             says nothing about a real model's selection or reading accuracy
  ESTIMATED  tokens from image sizes (~w*h/750 after downscaling to 1568 px / 1.15 MP, app/costs.py) and list prices
             (eval/pricing.py); output = 40 tokens per call, text = prompt length / 4. Ignores thinking tokens, which
             Opus 5.5 always spends (billed as output), so real costs are higher, especially for multi-call routes.

A "measured paid" column is reserved and stays empty until a key-backed run (eval.run_eval) fills it.
"""
from __future__ import annotations

import argparse
import os
import platform
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path
from statistics import median

from PIL import Image

from .metrics import answer_correct, evidence_iou
from .pricing import cost_usd
from .run_eval import load_items
from .schema import EvalItem, PipelineResult, Usage

GROUPS = ["text", "layout", "visual", "unanswerable", "all"]


def group_of(it: EvalItem) -> str:
    return "unanswerable" if not it.answerable else it.evidence_type


def route_of(r: PipelineResult) -> str:
    if r.usage and all(u.provider == "local" for u in r.usage):
        return "ocr_exit"
    if any(s.step == "zoom" for s in r.route):
        return "visual_zoom"
    return "visual_overview_only"


def full_image_usage(img: Image.Image, it: EvalItem, model: str, q_index: int, cached: bool) -> Usage:
    from app.costs import image_tokens
    from .pipelines.baselines import SYSTEM

    tok = image_tokens(*img.size)
    u = Usage(0, "anthropic", model, input_text_tokens=len(SYSTEM) // 4 + len(it.question) // 4,
              output_tokens=40, estimated=True, image_px=[list(img.size)])
    if not cached:
        u.input_image_tokens = tok
    elif q_index == 0:
        u.cache_write_tokens = tok
    else:
        u.cache_read_tokens = tok
    u.cost_usd = cost_usd(u)
    return u


def reprice(r: PipelineResult, model: str) -> float:
    """Re-price the oracle's estimated API usage at `model`; local OCR stays $0."""
    total = 0.0
    for u in r.usage:
        if u.provider == "local":
            continue
        v = Usage(**{**u.__dict__, "model": model, "provider": "anthropic"})
        total += cost_usd(v)
    return total


def pct(x) -> str:
    return "–" if x is None else f"{x:.0%}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", default="eval/data/accident_statement/items.jsonl")
    ap.add_argument("--models", nargs="+", default=["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"])
    ap.add_argument("--out", default="eval/results/SCORECARD.md")
    a = ap.parse_args()

    os.environ.setdefault("ROUTER_REQUIRE_OCR", "1")  # never let a missing OCR helper inflate the visual share
    import pipeline.router as router
    import pipeline.visual as visual
    from pipeline.visual.selftest import oracle

    items = load_items(Path(a.items))
    imgs: dict[str, Image.Image] = {}
    q_index: dict[str, int] = defaultdict(int)
    rows = []
    t0 = time.time()
    for it in items:
        img = imgs.setdefault(it.image_path, Image.open(it.image_path).convert("RGB"))
        visual.CALL_OVERRIDE = oracle(it, img.size)
        r = router.answer(img, it.question)
        r.question_id, r.image_id = it.question_id, it.image_id
        qi = q_index[it.image_id]
        q_index[it.image_id] += 1
        rows.append({
            "it": it, "r": r, "group": group_of(it), "route": route_of(r), "q_index": qi,
            "correct": answer_correct(it, r), "iou": evidence_iou(it, r),
            "ocr_ms": sum(u.latency_ms for u in r.usage if u.provider == "local"),
            "img_tok": sum(u.input_image_tokens for u in r.usage if u.provider != "local"),
            "full": {m: (full_image_usage(img, it, m, qi, False).cost_usd,
                         full_image_usage(img, it, m, qi, True).cost_usd) for m in a.models},
            "router_cost": {m: reprice(r, m) for m in a.models},
            "error": r.error,
        })
    visual.CALL_OVERRIDE = None
    from app.costs import image_tokens
    page_px = next(iter(imgs.values())).size
    full_tok = image_tokens(*page_px)

    def sel(g):
        return [x for x in rows if g == "all" or x["group"] == g]

    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    L = [
        "# Offline scorecard: measured vs. oracle vs. estimated",
        "",
        f"Generated by `python -m eval.scorecard` · commit `{commit}` · `{a.items}` ({len(items)} items, "
        f"{len(imgs)} images) · {platform.platform()} · Python {sys.version.split()[0]} · "
        f"{time.strftime('%Y-%m-%d %H:%M %Z')} · {time.time() - t0:.0f} s · **$0 spent**.",
        "",
        "Labels: **MEASURED** = observed on this machine · **ORACLE** = visual path given gold cells and gold "
        "answers (geometry check only) · **ESTIMATED** = token/price arithmetic, see assumptions at the end.",
        "",
        "## 1. Route mix and OCR (MEASURED)",
        "",
        "| group | n | OCR exit | OCR exit correct | **OCR wrong exit** | to visual path | OCR latency p50 (ms) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for g in GROUPS:
        xs = sel(g)
        if not xs:
            continue
        ex = [x for x in xs if x["route"] == "ocr_exit" and not x["r"].abstained]
        lat = [x["ocr_ms"] for x in xs if x["ocr_ms"] > 0]
        L.append(f"| {g} | {len(xs)} | {len(ex)} | {sum(x['correct'] for x in ex)} | "
                 f"**{sum(not x['correct'] for x in ex)}** | {sum(x['route'] != 'ocr_exit' for x in xs)} | "
                 f"{median(lat):.0f} |" if lat else
                 f"| {g} | {len(xs)} | {len(ex)} | {sum(x['correct'] for x in ex)} | "
                 f"**{sum(not x['correct'] for x in ex)}** | {sum(x['route'] != 'ocr_exit' for x in xs)} | – |")
    errs = [x for x in rows if x["error"]]
    L += ["", f"Pipeline errors: {len(errs)}." + (" First: " + errs[0]["error"][:120] if errs else ""),
          "OCR under degraded inputs (phone photo, scans): see "
          "[REPORT_ocr_robustness_fix.md](REPORT_ocr_robustness_fix.md) (MEASURED, claude-andrew-b's bench).", ""]

    vis = [x for x in rows if x["route"] != "ocr_exit"]
    L += ["## 2. Visual path geometry (ORACLE)", "",
          "The oracle picks exactly the gold cells and answers with gold, so these numbers verify the grid → "
          "mosaic → box mapping, **not** a model's ability to choose cells or read ticks.", "",
          "| group | n via visual | accuracy (oracle) | evidence IoU mean (oracle) | image tokens/q (ESTIMATED) |",
          "|---|---:|---:|---:|---:|"]
    for g in GROUPS:
        xs = [x for x in vis if g == "all" or x["group"] == g]
        if not xs:
            continue
        ious = [x["iou"] for x in xs if x["iou"] is not None]
        L.append(f"| {g} | {len(xs)} | {pct(sum(x['correct'] for x in xs) / len(xs))} | "
                 f"{(sum(ious) / len(ious)) if ious else float('nan'):.2f} | {median(x['img_tok'] for x in xs):.0f} |")
    L += ["", f"Full page for comparison: {page_px[0]}×{page_px[1]} px ≈ **{full_tok}** image tokens (ESTIMATED).", ""]

    L += ["## 3. Cost per question (ESTIMATED) — measured paid column reserved", "",
          "Router = real OCR ($0) + the oracle's visual calls re-priced at each model. Full page = one call per "
          "question with the whole page; cached = cache write on the first question per image, reads after.", "",
          "| model | group | router $/q | full page $/q | full page cached $/q | router ÷ cached | measured paid |",
          "|---|---|---:|---:|---:|---:|---|"]
    for m in a.models:
        for g in GROUPS:
            xs = sel(g)
            if not xs:
                continue
            rc = sum(x["router_cost"][m] for x in xs) / len(xs)
            fu = sum(x["full"][m][0] for x in xs) / len(xs)
            fc = sum(x["full"][m][1] for x in xs) / len(xs)
            L.append(f"| `{m}` | {g} | {rc:.5f} | {fu:.5f} | {fc:.5f} | {rc / fc if fc else float('nan'):.2f} | "
                     f"pending key |")
    L += ["", "Per-group cached numbers depend on question order: in the dataset the text questions come first "
          "on each page and absorb the cache write. Only the `all` rows, and section 4, are order-fair.", ""]

    # ---- 4. cumulative cost vs. questions asked per page, averaged over random question orders -------------
    import random

    rng = random.Random(0)
    by_img: dict[str, list[dict]] = defaultdict(list)
    for x in rows:
        by_img[x["it"].image_id].append(x)
    pairs = [(m, m) for m in a.models] + [(a.models[-1], a.models[0])]  # same model; cheap router vs. strong page
    ks = sorted({1, 2, 3, max(len(v) for v in by_img.values())})
    L += ["## 4. Cost per page vs. number of questions asked (ESTIMATED, order-averaged)", "",
          "Mean cumulative $ per page when a handler asks k random questions about it (200 random orders per "
          "page, seed 0). Cached full page: cache write on the first question, reads after. The router does not "
          "cache its overview here, which slightly favours the baseline.", "",
          "| router model | full-page model | " + " | ".join(f"k={k}: router / full / cached" for k in ks) + " |",
          "|---|---|" + "---:|" * len(ks)]
    for rm, fm in pairs:
        acc = {k: [0.0, 0.0, 0.0, 0] for k in ks}
        for xs in by_img.values():
            for _ in range(200):
                order = rng.sample(xs, len(xs))
                for k in ks:
                    if k > len(order):
                        continue
                    sub = order[:k]
                    tok_img = imgs[sub[0]["it"].image_path]
                    cached = sum(full_image_usage(tok_img, x["it"], fm, i, True).cost_usd for i, x in enumerate(sub))
                    acc[k][0] += sum(x["router_cost"][rm] for x in sub)
                    acc[k][1] += sum(x["full"][fm][0] for x in sub)
                    acc[k][2] += cached
                    acc[k][3] += 1
        cells = []
        for k in ks:
            r_, f_, c_, n_ = acc[k]
            cells.append(f"{r_ / n_:.4f} / {f_ / n_:.4f} / {c_ / n_:.4f}" if n_ else "–")
        L.append(f"| `{rm}` | `{fm}` | " + " | ".join(cells) + " |")
    L += ["", "Reading: the router beats the cached page when few questions are asked per page or when OCR answers "
          "many of them; the cheap-router / strong-page row is the frugality claim **only if** the cheap model's "
          "accuracy on crops holds, which only a paid run can show.", ""]

    # ---- 4b. mixed strategy: router for the first s questions, then the cached full page (write at s+1) -----
    kmax = max(len(v) for v in by_img.values())
    m0 = a.models[0]
    switch_points = list(range(0, kmax + 1))  # s=0: cached page from the start; s=kmax: router only
    tot = {(s, k): [0.0, 0] for s in switch_points for k in range(1, kmax + 1)}
    rng2 = random.Random(1)
    for xs in by_img.values():
        page = imgs[xs[0]["it"].image_path]
        for _ in range(200):
            order = rng2.sample(xs, len(xs))
            for s in switch_points:
                run_cost = 0.0
                for k, x in enumerate(order, start=1):
                    if k <= s:
                        run_cost += x["router_cost"][m0]
                    else:
                        run_cost += full_image_usage(page, x["it"], m0, k - 1 - s, True).cost_usd
                    tot[(s, k)][0] += run_cost
                    tot[(s, k)][1] += 1
    L += [f"### 4b. Mixed strategy on `{m0}` (ESTIMATED, order-averaged)", "",
          "Router for the first *s* questions on a page, then the cached full page (cache write on question s+1). "
          "Rows: questions actually asked (k). Cells: mean cumulative $ per page; **bold** = cheapest s for that k. "
          "s=0 is the cached page from the start; s=k or more is router only.", "",
          "| k \\ s | " + " | ".join(str(s) for s in switch_points) + " |",
          "|---:|" + "---:|" * len(switch_points)]
    for k in range(1, kmax + 1):
        vals = [tot[(s, k)][0] / tot[(s, k)][1] for s in switch_points]
        best = min(vals)
        L.append(f"| {k} | " + " | ".join(f"**{v:.4f}**" if v == best else f"{v:.4f}" for v in vals) + " |")
    L += ["", "A switching rule is only supported if one fixed *s* is cheapest, or close to it, across the k a handler "
          "is likely to ask; otherwise the choice depends on how many questions will follow, which the app does "
          "not know in advance.", ""]

    L += ["## 5. Assumptions behind ESTIMATED numbers", "",
          "- Image tokens ≈ w·h/750 after downscaling to ≤1568 px long side and ≤1.15 MP (`app/costs.py`). "
          "Not yet checked against a provider: `eval/billing_probe.py` measures it once a key exists.",
          "- Output 40 tokens per call; text tokens ≈ characters/4. **Thinking tokens are ignored.** Opus 5.5 "
          "always thinks (billed as output), so multi-call routes are under-estimated relative to one-call "
          "baselines.",
          "- List prices from `eval/pricing.py` (Anthropic first-party, 2026-11-03). Cache write 1.25×, read 0.1× "
          "input unless the model lists its own cache-read price.",
          "- Questions are asked in dataset order per image (8 per image), which is what the cached baseline "
          "amortizes over.",
          "- Synthetic clean renders; real claims are open (see section 1 for the robustness link).", ""]

    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text("\n".join(L))
    print("\n".join(L))
    print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
