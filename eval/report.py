"""Turn one or more run JSONs into a Markdown results table (for messages, README and the pitch).

    python -m eval.report eval/results/run_A.json [eval/results/run_B.json ...] [--out eval/results/REPORT.md]

One row per pipeline x evidence type: n, accuracy, joint answer+evidence, evidence hit, abstain/correct-abstain,
cost per question, median latency, mean image/text/output tokens per question, calls per question.
Numbers marked * contain estimated usage. Every table names the commit and items file it came from.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

GROUPS = ["all", "text", "layout", "visual", "mixed"]


def pct(v) -> str:
    return "–" if v is None else f"{v:.0%}"


def table(run: dict) -> str:
    meta = run["meta"]
    lines = [
        f"### Run {meta['time']} · commit `{meta['commit']}` · `{meta['items']}` · input `{meta.get('degrade', 'clean')}`"
        f" · spent ${meta['spent_usd']:.4f}",
        "",
        *(["> Geometric degradation: gold boxes no longer align exactly, so `joint` and `hit@0.3` and any gold_crop "
           "rows are approximate.\n"] if meta.get("geometric_degrade") else []),
        "| pipeline | group | n | acc | joint | hit@0.3 | abstain | correct abstain | $/q | p50 ms | in tok/q | of which image | out tok/q | calls/q | pair follow | zoomed | zoom covers gold | acc when covered |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, rep in run["report"].items():
        if rep.get("aborted") or not rep.get("complete", True):
            lines.insert(2, f"> **`{name}` is not a clean measurement:** "
                            f"{rep.get('aborted') or 'incomplete (budget cap)'}; degraded results: {rep.get('degraded', '?')}.\n")
        for g in GROUPS:
            s = rep["summary"].get(g)
            if not s or not s["n"]:
                continue
            n = s["n"]
            star = "*" if s["any_estimated"] else ""
            pf = pct(rep.get("pair_follow_rate")) if g == "all" else ""
            lines.append(
                f"| `{name}` | {g} | {n} | {pct(s['accuracy'])} | {pct(s['joint_answer_evidence'])} | "
                f"{pct(s['evidence_hit@0.3'])} | {pct(s['abstain_rate'])} | {pct(s['correct_abstain_rate'])} | "
                f"{s['cost_usd_mean']:.5f}{star} | {s['latency_ms_median']:.0f} | "
                f"{(s['input_image_tokens'] + s['input_text_tokens'] + s['cache_read_tokens']) / n:.0f} | "
                f"{(str(round(s['input_image_tokens'] / n)) if s['input_image_tokens'] else '–')} | "
                f"{s['output_tokens'] / n:.0f} | {s['calls'] / n:.2f} | {pf} | "
                f"{pct(s.get('zoom_rate'))} | {pct(s.get('zoom_covers_gold@0.9'))} | {pct(s.get('acc_given_zoom_covers'))} |"
            )
    lines += ["", "`*` = contains estimated usage. Cost per question excludes one-off indexing unless the pipeline "
              "recorded it in `usage`. `in tok/q` = all input tokens incl. images and cache reads, as the backend "
              "reported them; `of which image` is shown only when an image/text split was available (probe hint), "
              "otherwise `–` (the image tokens are inside `in tok/q`).", ""]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    md = "\n".join(table(json.loads(Path(r).read_text())) for r in a.runs)
    if a.out:
        Path(a.out).write_text(md)
        print(f"wrote {a.out}")
    print(md)


if __name__ == "__main__":
    main()
