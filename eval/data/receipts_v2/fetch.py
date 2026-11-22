"""Real-receipt QA set from CORD-v2 validation (receipts_v2, message 217; fresh split, same generator as receipts_v1).

Rows + images come from the Hugging Face datasets-server API (only sampled images downloaded).
Questions per receipt (only when the gold field exists): total, change, tax, price of first menu item,
plus one unanswerable question from a rotating list of fields CORD never annotates.

    SSL_CERT_FILE=$(python -m certifi) python3 -m eval.data.receipts_v2.fetch      (RC_SEED=2222, RC_N=60)
"""
from __future__ import annotations

import ast
import hashlib
import io
import json
import os
import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

HERE = Path(__file__).parent
SEED = int(os.environ.get("RC_SEED", "2222"))
N = int(os.environ.get("RC_N", "60"))
DS, CFG, SPLIT = "naver-clova-ix/cord-v2", "default", "validation"  # receipts_v2: the split no route was developed on
API = "https://datasets-server.huggingface.co/rows"
MAX_SIDE = 2400
UNANSWERABLE = ["What is the store's website?", "What is the cashier's name?", "What is the store's email address?",
                "What is the receipt's loyalty card number?", "What is the table's reservation name?",
                "What is the VAT registration number?"]


def get(url: str, tries: int = 8) -> bytes:
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "eval-sampler"}), timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if i == tries - 1:
                raise
            wait = 2 * (i + 1) ** 2
            if e.code == 429:
                try:
                    wait = max(wait, int(e.headers.get("Retry-After", 0)))
                except ValueError:
                    pass
                wait = max(wait, 15)
            time.sleep(wait)
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(2 * (i + 1))
    raise RuntimeError("unreachable")


def rows(offset, length=1):
    q = urllib.parse.urlencode({"dataset": DS, "config": CFG, "split": SPLIT, "offset": offset, "length": length})
    return json.loads(get(f"{API}?{q}"))


def s(x):
    """Gold values can be str, or (rarely) dict/list; return a clean string or None."""
    if isinstance(x, str) and x.strip():
        return x.strip()
    return None


def variants(v: str) -> list[str]:
    """Accepted forms of an amount string: as printed, bare digits, thousands separators of both kinds, currency symbols."""
    out = {v}
    digits = re.sub(r"[^\d]", "", v)
    core = v
    for sym in ("Rp.", "Rp", "IDR", "$"):
        core = core.replace(sym, "")
    core = core.strip()
    out.add(core)
    if digits and "." not in core and "," not in core or re.fullmatch(r"[\d.,]+", core or "x"):
        if digits:
            out.add(digits)
            if len(digits) > 3 and not re.search(r"[.,]\d{1,2}$", core):
                out.add(f"{int(digits):,}")
                out.add(f"{int(digits):,}".replace(",", "."))
    for b in list(out):
        out.add(f"Rp {b}")
        out.add(f"Rp{b}")
    out.discard("")
    out.discard(v)
    return sorted(out)


def find_box(gt, category, W, H):
    for vl in gt.get("valid_line", []):
        if vl.get("category") == category:
            ws = vl.get("words", [])
            if not ws:
                continue
            xs = [q for w in ws for q in (w["quad"]["x1"], w["quad"]["x2"], w["quad"]["x3"], w["quad"]["x4"])]
            ys = [q for w in ws for q in (w["quad"]["y1"], w["quad"]["y2"], w["quad"]["y3"], w["quad"]["y4"])]
            b = [min(xs) / W, min(ys) / H, max(xs) / W, max(ys) / H]
            return [round(min(max(c, 0), 1), 4) for c in b]
    return None


def main():
    rng = random.Random(SEED)
    (HERE / "images").mkdir(parents=True, exist_ok=True)
    total = rows(0)["num_rows_total"]
    offs = rng.sample(range(total), min(total, N * 2))  # CORD test has only 100 rows
    out, got, ukind = [], 0, 0
    sizes = []
    for off in offs:
        if got >= N:
            break
        try:
            r = rows(off)["rows"][0]["row"]
            src = r["image"]["src"] if isinstance(r["image"], dict) else ast.literal_eval(r["image"])["src"]
            img = Image.open(io.BytesIO(get(src))).convert("RGB")
            gt = json.loads(r["ground_truth"])
        except Exception as e:
            print("skip", off, type(e).__name__)
            continue
        orig = img.size
        W, H = gt.get("meta", {}).get("image_size", {}).get("width", orig[0]), gt.get("meta", {}).get("image_size", {}).get("height", orig[1])
        if max(img.size) > MAX_SIDE:
            k = MAX_SIDE / max(img.size)
            img = img.resize((round(img.width * k), round(img.height * k)), Image.LANCZOS)
        sizes.append(img.size)
        iid = f"rc-{hashlib.sha256(img.tobytes()).hexdigest()[:12]}"
        img.save(HERE / "images" / f"{iid}.png")
        p = gt.get("gt_parse", {})
        tot, sub = p.get("total") or {}, p.get("sub_total") or {}
        menu = p.get("menu")
        if isinstance(menu, dict):
            menu = [menu]
        first = (menu or [None])[0] or {}
        note0 = f"CORD-v2 test row {off}; original size {orig[0]}x{orig[1]}; stored {img.width}x{img.height}"
        qs = []
        tp = s(tot.get("total_price"))
        if tp:
            box = find_box(gt, "total.total_price", W, H)
            qs.append(("What is the total amount on this receipt?", tp, [box] if box else [], "total_price"))
        cp = s(tot.get("changeprice"))
        if cp:
            box = find_box(gt, "total.changeprice", W, H)
            qs.append(("How much change was given?", cp, [box] if box else [], "changeprice"))
        tx = s(sub.get("tax_price"))
        if tx:
            box = find_box(gt, "sub_total.tax_price", W, H)
            qs.append(("What is the tax amount?", tx, [box] if box else [], "tax_price"))
        nm, pr = s(first.get("nm")), s(first.get("price"))
        if nm and pr:
            qs.append((f"What is the price of {nm}?", pr, [], "first_item_price"))
        for k, (q, a, boxes, fld) in enumerate(qs):
            out.append({"question_id": f"rv-{off}-q{k}", "image_id": iid, "image_path": f"images/{iid}.png", "question": q,
                        "answer": a, "answerable": True, "evidence_type": "text", "evidence_boxes": boxes,
                        "accepted_answers": variants(a), "pair_id": None, "source": f"cord-v2:test:{off}",
                        "notes": f"{note0}; gold field {fld}" + ("; box from CORD valid_line quads" if boxes else "")})
        uq = UNANSWERABLE[ukind % len(UNANSWERABLE)]
        ukind += 1
        out.append({"question_id": f"rv-{off}-q{len(qs)}", "image_id": iid, "image_path": f"images/{iid}.png", "question": uq,
                    "answer": None, "answerable": False, "evidence_type": "text", "evidence_boxes": [],
                    "accepted_answers": [], "pair_id": None, "source": f"cord-v2:test:{off}",
                    "notes": f"{note0}; unanswerable (field never annotated in CORD)"})
        got += 1
        print(got, off, len(qs) + 1)
    with open(HERE / "items.jsonl", "w") as fh:
        for it in out:
            fh.write(json.dumps(it) + "\n")
    print(len(out), "items;", got, "receipts; sizes", min(sizes), max(sizes))


if __name__ == "__main__":
    main()
