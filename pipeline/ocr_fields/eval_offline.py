"""Offline $0 eval of pipeline.ocr_fields. Run: PYTHONPATH=. EVIDENCE_OCR_BIN=... .venv/bin/python -m pipeline.ocr_fields.eval_offline"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

from PIL import Image

from eval.metrics import answer_correct
from eval.schema import EvalItem, PipelineResult
from pipeline.ocr import recognize_page
from pipeline.ocr_fields import classify, extract_from_spans

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "eval" / "results" / "ocr_fields_dev"
CACHE = Path(os.environ.get("OCR_SPAN_CACHE", OUT / "_spans_cache.json"))
THRESHOLDS = [0.0, 0.5, 0.75, 0.85]


def digits(s):
    s = re.sub(r"[.,]\d{1,2}$", "", s) if re.search(r"[.,]\d{1,2}$", s) and not re.search(r"[.,]\d{3}$", s) else s
    return re.sub(r"\D", "", s or "")


def num_equal(item, ans):
    if ans is None or not item.answer:
        return False
    return any(digits(ans) == digits(g) and digits(g) != "" for g in [item.answer, *item.accepted_answers])


def load(path):
    base = Path(path).parent
    items = []
    for l in open(path):
        d = json.loads(l)
        d = {k: v for k, v in d.items() if k in EvalItem.__dataclass_fields__}
        items.append((EvalItem(**d), base))
    return items


def run(name, path, cache, only=None, limit=None):
    rows = []
    items = load(path)
    if only:
        items = [x for x in items if only(x[0])]
    for item, base in items[:limit]:
        p = str(base / item.image_path)
        if p not in cache:
            spans, _ = recognize_page(Image.open(p))
            cache[p] = spans
        r = extract_from_spans(cache[p], item.question)
        field = r.get("field") or "other"
        rows.append((item, field, r))
    return rows


def summarize(rows, thr=0.0):
    per = defaultdict(lambda: dict(n=0, answerable=0, answered=0, correct=0, num_correct=0, wrong_on_unanswerable=0))
    for item, field, r in rows:
        for key in (field, "ALL"):
            d = per[key]
            d["n"] += 1
            d["answerable"] += item.answerable
            ans = r["answer"] if r["confidence"] >= thr else None
            if ans is None:
                continue
            d["answered"] += 1
            res = PipelineResult(ans, abstained=False)
            if not item.answerable:
                d["wrong_on_unanswerable"] += 1
            else:
                d["correct"] += answer_correct(item, res)
                d["num_correct"] += (answer_correct(item, res) or num_equal(item, ans))
    out = {}
    for k, d in per.items():
        d = dict(d)
        d["coverage"] = round(d["answered"] / d["n"], 3) if d["n"] else 0
        d["precision"] = round(d["correct"] / d["answered"], 3) if d["answered"] else None
        d["precision_numeric"] = round(d["num_correct"] / d["answered"], 3) if d["answered"] else None
        d["zero_token_correct_rate"] = round(d["correct"] / d["n"], 3) if d["n"] else 0
        out[k] = d
    return out


def main():
    cache = json.load(open(CACHE)) if CACHE.exists() else {}
    sets = {
        "receipts_v1": (ROOT / "eval/data/receipts_v1/items.jsonl", None),
        "repair_invoice": (ROOT / "eval/data/repair_invoice/items.jsonl", None),
        "realdocs_v2_docvqa": (ROOT / "eval/data/realdocs_v2/items_docvqa.jsonl", None),
    }
    summary, errors = {}, []
    for name, (path, only) in sets.items():
        if not path.exists():
            continue
        rows = run(name, path, cache)
        summary[name] = {f"thr_{t}": summarize(rows, t) for t in THRESHOLDS}
        for item, field, r in rows:
            if r["answer"] is not None:
                ok = answer_correct(item, PipelineResult(r["answer"])) if item.answerable else False
                if not ok:
                    errors.append(dict(set=name, qid=item.question_id, q=item.question, gold=item.answer, pred=r["answer"],
                                       conf=r["confidence"], line=r["line"], field=field))
        json.dump(cache, open(CACHE, "w"))
    OUT.mkdir(parents=True, exist_ok=True)
    json.dump(summary, open(OUT / "summary.json", "w"), indent=1)
    json.dump(errors, open(OUT / "errors.json", "w"), indent=1)
    for name, s in summary.items():
        print("==", name)
        for t in ("thr_0.0", "thr_0.75"):
            print(" ", t)
            for k, d in sorted(s[t].items()):
                print(f"   {k:10s} n={d['n']:3d} ans={d['answered']:3d} cov={d['coverage']} prec={d['precision']} numprec={d['precision_numeric']} zt={d['zero_token_correct_rate']} wrongUnans={d['wrong_on_unanswerable']}")


if __name__ == "__main__":
    main()
