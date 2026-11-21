"""Accuracy-vs-cost frontier: one point per (run, pipeline), the pitch chart.

    python -m eval.plot_frontier eval/results/run_A.json [run_B.json ...] \
        [--group visual] [--x tokens|usd|gpu_s|latency_ms] [--out eval/results/frontier.png]

x axis (per question, mean):
  tokens      all input tokens incl. images and cache reads, as the backend reported them (default)
  usd         cost_usd_mean (estimated where the run says so)
  gpu_s       GPU seconds of self-hosted model calls (Usage.device == "gpu")
  latency_ms  median end-to-end latency
y axis: accuracy in the chosen evidence-type group (default "all").

Points on the Pareto frontier (no other point is both cheaper and at least as accurate) are drawn filled and
joined; dominated points are hollow. Labels are the pipeline names, shortened. The title names the runs' commits
and items, so a slide always carries its provenance. Estimated x values are marked with "*".
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def short(name: str) -> str:
    name = re.sub(r"@local:Qwen/Qwen2\.5-VL-(\d+B)[-\w]*", r" (\1)", name)
    name = re.sub(r"@or:[\w.-]+/", " @", name)
    return name.replace("pipeline.", "").replace(":factory", "").replace("_px:", " ")


def x_of(s: dict, kind: str) -> float | None:
    n = s["n"] or 1
    if kind == "tokens":
        return (s["input_image_tokens"] + s["input_text_tokens"] + s["cache_read_tokens"]) / n
    if kind == "usd":
        return s["cost_usd_mean"]
    if kind == "gpu_s":
        return (s.get("gpu_seconds") or 0) / n
    if kind == "latency_ms":
        return s["latency_ms_median"]
    raise SystemExit(f"unknown --x {kind}")


def pareto(points: list[tuple[float, float]]) -> set[int]:
    keep = set()
    for i, (x, y) in enumerate(points):
        if not any((x2 <= x and y2 >= y) and (x2 < x or y2 > y) for j, (x2, y2) in enumerate(points) if j != i):
            keep.add(i)
    return keep


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--group", default="all")
    ap.add_argument("--x", default="tokens", choices=["tokens", "usd", "gpu_s", "latency_ms"])
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    pts, labels, est, prov = [], [], [], set()
    for path in a.runs:
        run = json.loads(Path(path).read_text())
        prov.add(f"{run['meta']['commit']} · {Path(run['meta']['items']).name}")
        for name, rep in run["report"].items():
            s = rep["summary"].get(a.group)
            if not s or s.get("accuracy") is None or rep.get("aborted"):
                continue
            x = x_of(s, a.x)
            if x is None:
                continue
            pts.append((x, s["accuracy"]))
            labels.append(short(name))
            est.append(bool(s.get("any_estimated")) and a.x == "usd")
    if not pts:
        raise SystemExit("no points (check --group and that runs are not aborted)")

    front = pareto(pts)
    fig, ax = plt.subplots(figsize=(7.2, 4.4), dpi=160)
    fx = sorted((pts[i] for i in front), key=lambda p: p[0])
    ax.plot([p[0] for p in fx], [p[1] for p in fx], lw=1.2, color="#2b6cb0", alpha=0.6, zorder=1)
    for i, ((x, y), lab) in enumerate(zip(pts, labels)):
        on = i in front
        ax.scatter([x], [y], s=46, zorder=2, color="#2b6cb0" if on else "white", edgecolors="#2b6cb0", linewidths=1.4)
        ax.annotate(lab + ("*" if est[i] else ""), (x, y), xytext=(5, 4), textcoords="offset points", fontsize=7)
    xl = {"tokens": "input tokens per question (as reported)", "usd": "$ per question",
          "gpu_s": "GPU seconds per question", "latency_ms": "median latency per question (ms)"}[a.x]
    ax.set_xlabel(xl)
    ax.set_ylabel(f"accuracy ({a.group})")
    ax.set_ylim(-0.02, 1.02)
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(alpha=0.25)
    ax.set_title("Accuracy vs. cost · filled = Pareto frontier · " + "; ".join(sorted(prov)), fontsize=7, loc="left")
    if any(est):
        fig.text(0.01, 0.01, "* estimated cost", fontsize=6)
    fig.tight_layout()
    out = a.out or str(Path(a.runs[0]).with_name(f"frontier_{a.group}_{a.x}.png"))
    fig.savefig(out)
    print(f"wrote {out}  ({len(pts)} points, {len(front)} on the frontier)")
    for i in sorted(front, key=lambda i: pts[i][0]):
        print(f"  frontier: {labels[i]:<40} x={pts[i][0]:.4g}  acc={pts[i][1]:.0%}")


if __name__ == "__main__":
    main()
