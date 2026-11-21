"""Free-form handwriting pages from real IAM handwriting (owner: claude-andrew-b; Andrew's idea, 2026-11-22).

Each page stacks 7 consecutive lines of the IAM-line test split (Teklia/IAM-line on Hugging Face, fetched through the
datasets-server API), which are consecutive lines of one writer's handwritten paragraph. Questions can only be
answered by reading the handwriting:
  q1-q3  "What word comes right after 'W' in the handwritten text?"   (text: printed nowhere, only handwritten)
  q4     "What is the last word of the handwritten text?"              (text)
  q5     "How many lines of handwriting are on the page?"              (mixed: layout)
  q6     "Who signed this note?"                                       (unanswerable: there is no signature)
Gold = the IAM transcription. Evidence boxes = the pasted line strips that hold the words.

    python3 -m eval.data.handwriting_v1.fetch     (HW_SEED=2211, HW_PAGES=10)
"""
from __future__ import annotations

import io
import json
import os
import random
import re
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

HERE = Path(__file__).parent
SEED = int(os.environ.get("HW_SEED", "2211"))
PAGES = int(os.environ.get("HW_PAGES", "10"))
LINES = 7
API = "https://datasets-server.huggingface.co/rows"


def get(url, tries=6):
    import time
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "eval-sampler"}),
                                        timeout=60) as r:
                return r.read()
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(10 * (i + 1))  # datasets-server rate limit (429)


def rows(offset, length):
    q = urllib.parse.urlencode({"dataset": "Teklia/IAM-line", "config": "default", "split": "test",
                                "offset": offset, "length": length})
    return json.loads(get(f"{API}?{q}"))


def words(t):
    return re.findall(r"[A-Za-z][A-Za-z'-]*", t)


def main():
    rng = random.Random(SEED)
    (HERE / "images").mkdir(parents=True, exist_ok=True)
    total = rows(0, 1)["num_rows_total"]
    starts = sorted(rng.sample(range(0, total - LINES, LINES * 3), PAGES))
    out = []
    for n, st in enumerate(starts, 1):
        rs = [r["row"] for r in rows(st, LINES)["rows"]]
        strips = [Image.open(io.BytesIO(get(r["image"]["src"]))).convert("L") for r in rs]
        texts = [r["text"] for r in rs]
        W = max(s.width for s in strips) + 160
        gap = 40
        H = sum(s.height for s in strips) + gap * (LINES - 1) + 240
        page = Image.new("L", (W, H), 255)
        y, boxes = 120, []
        for s in strips:
            page.paste(s, (80, y))
            boxes.append([80 / W, y / H, (80 + s.width) / W, (y + s.height) / H])
            y += s.height + gap
        iid = f"hw1-{n:03d}"
        page.convert("RGB").save(HERE / "images" / f"{iid}.png")
        # (word, line index) in reading order
        toks = [(w, i) for i, t in enumerate(texts) for w in words(t)]
        low = [w.lower() for w, _ in toks]
        cands = [k for k in range(len(toks) - 1)
                 if len(toks[k][0]) >= 4 and low.count(low[k]) == 1 and len(toks[k + 1][0]) >= 2]
        picks = sorted(rng.sample(cands, min(3, len(cands))))

        def it(k, q, ans, et, bx, acc=()):
            out.append({"question_id": f"{iid}-q{k}", "image_id": iid, "image_path": f"images/{iid}.png",
                        "question": q, "answer": ans, "answerable": ans is not None, "evidence_type": et,
                        "evidence_boxes": [[round(v, 4) for v in b] for b in bx], "accepted_answers": list(acc),
                        "pair_id": None, "source": f"Teklia/IAM-line:test:{st}-{st + LINES - 1}", "notes": None})
        for j, k in enumerate(picks, 1):
            w, li = toks[k]
            nxt, lj = toks[k + 1]
            it(j, f"What word comes right after '{w}' in the handwritten text?", nxt, "text",
               [boxes[li]] + ([boxes[lj]] if lj != li else []))
        lw, ll = toks[-1]
        it(4, "What is the last word of the handwritten text?", lw, "text", [boxes[ll]])
        it(5, "How many lines of handwriting are on the page?", str(LINES), "mixed", boxes, ("seven",))
        it(6, "Who signed this note?", None, "text", [])
        print(iid, st, len(picks))
    with open(HERE / "items.jsonl", "w") as fh:
        for x in out:
            fh.write(json.dumps(x) + "\n")
    print(len(out), "items")


if __name__ == "__main__":
    main()
