"""Second real-document sample (fresh: new seed, no row overlap with realdocs_v1), for testing fixes made after v1.

Copy of realdocs_v1/fetch.py with: seed 2266, 70 rows per source, InfographicVQA added, v1 rows excluded.
Original v1 notes follow.

Public benchmark rows, fetched one by one through the Hugging Face datasets-server API (only the sampled images are
downloaded):
  - DocVQA validation (scanned business documents; questions answerable from the page text)  -> evidence_type "text"
  - ChartQA test (charts; answers usually need reading the plot)                              -> evidence_type "visual"
The evidence_type labels are by source, not per question (some ChartQA charts print their values; some DocVQA
answers need layout). No gold boxes exist, so only answer accuracy is scored. accepted_answers = all gold answers.

    python3 -m eval.data.realdocs_v1.fetch      (RD_SEED=1163, RD_N=100 per source)
"""
from __future__ import annotations

import ast
import hashlib
import io
import json
import os
import random
import time
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

HERE = Path(__file__).parent
SEED = int(os.environ.get("RD_SEED", "2266"))
N = int(os.environ.get("RD_N", "70"))
API = "https://datasets-server.huggingface.co/rows"
SOURCES = [
    ("docvqa", "lmms-lab-encoder/DocVQA", "DocVQA", "validation", "text"),
    ("infovqa", "lmms-lab-encoder/DocVQA", "InfographicVQA", "validation", "mixed"),
    ("chartqa", "lmms-lab-encoder/ChartQA", "default", "test", "visual"),
]
V1 = {json.loads(l)["question_id"] for l in open(HERE.parent / "realdocs_v1" / "items.jsonl")}
MAX_SIDE = 2400  # downscale very large pages (keeps disk small; the route and the baseline see the same file)


def get(url: str, tries: int = 4) -> bytes:
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "eval-sampler"}), timeout=60) as r:
                return r.read()
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(2 * (i + 1))
    raise RuntimeError("unreachable")


def rows(ds, cfg, split, offset, length=1):
    q = urllib.parse.urlencode({"dataset": ds, "config": cfg, "split": split, "offset": offset, "length": length})
    return json.loads(get(f"{API}?{q}"))


def answers(row) -> list[str]:
    a = row.get("answers", row.get("answer"))
    if isinstance(a, str) and a.startswith("["):
        try:
            a = ast.literal_eval(a)
        except Exception:
            a = [a]
    if isinstance(a, str):
        a = [a]
    return [str(x).strip() for x in a if str(x).strip()]


def main():
    rng = random.Random(SEED)
    (HERE / "images").mkdir(parents=True, exist_ok=True)
    out, seen_img = [], set()
    for tag, ds, cfg, split, et in SOURCES:
        total = rows(ds, cfg, split, 0)["num_rows_total"]
        offs = rng.sample(range(total), N * 2)  # spares for failed fetches / duplicate images
        got = 0
        for off in offs:
            if got >= N:
                break
            if f"rd-{tag}-{off}" in V1:
                continue
            try:
                r = rows(ds, cfg, split, off)["rows"][0]["row"]
                src = r["image"]["src"] if isinstance(r["image"], dict) else ast.literal_eval(r["image"])["src"]
                img = Image.open(io.BytesIO(get(src))).convert("RGB")
            except Exception as e:  # skip unreachable rows; the seed fixes which are tried
                print("skip", tag, off, type(e).__name__)
                continue
            if max(img.size) > MAX_SIDE:
                s = MAX_SIDE / max(img.size)
                img = img.resize((round(img.width * s), round(img.height * s)), Image.LANCZOS)
            h = hashlib.sha256(img.tobytes()).hexdigest()[:12]
            iid = f"rd-{tag}-{h}"
            if iid not in seen_img:
                img.save(HERE / "images" / f"{iid}.png")
                seen_img.add(iid)
            ans = answers(r)
            out.append({"question_id": f"rd-{tag}-{off}", "image_id": iid, "image_path": f"images/{iid}.png",
                        "question": r["question"].strip(), "answer": ans[0], "answerable": True,
                        "evidence_type": et, "evidence_boxes": [], "accepted_answers": ans[1:], "pair_id": None,
                        "source": f"{ds}:{cfg}:{split}:{off}", "notes": None})
            got += 1
        print(tag, got)
    with open(HERE / "items.jsonl", "w") as fh:
        for it in out:
            fh.write(json.dumps(it) + "\n")
    print(len(out), "items")


if __name__ == "__main__":
    main()
