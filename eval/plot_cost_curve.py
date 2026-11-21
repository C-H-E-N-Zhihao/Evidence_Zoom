"""Frugality chart: mean cumulative cost vs. questions per image, one line per pipeline.

    python -m eval.plot_cost_curve eval/results/run_XXXX.json [--index-cost ocr_router=0.002] [--out chart.png]

`--index-cost name=usd` adds a one-off per-image indexing cost to that pipeline's curve, if the pipeline did not
already record its indexing calls in `usage`.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--index-cost", nargs="*", default=[])
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    run = json.loads(Path(a.run).read_text())
    extra = {k: float(v) for k, v in (s.split("=") for s in a.index_cost)}
    fig, ax = plt.subplots(figsize=(6.4, 4.0), dpi=150)
    for name, rep in run["report"].items():
        curve = rep["cost_curve"]
        if not curve:
            continue
        xs = [c["questions"] for c in curve]
        ys = [(c["mean_cum_cost_usd"] + extra.get(name, 0.0)) * 100 for c in curve]
        acc = rep["summary"]["all"]["accuracy"]
        ax.plot(xs, ys, marker="o", lw=1.8, ms=3.5, label=f"{name} (acc {acc:.0%})" if acc is not None else name)
    ax.set_xlabel("questions asked about one image")
    ax.set_ylabel("cumulative cost per image (US cents)")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.3)
    ax.legend(frameon=False, fontsize=8)
    ax.set_title(f"Cost vs. questions per image  (commit {run['meta']['commit']})", fontsize=9, loc="left")
    fig.tight_layout()
    out = a.out or str(Path(a.run).with_suffix(".png"))
    fig.savefig(out)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
