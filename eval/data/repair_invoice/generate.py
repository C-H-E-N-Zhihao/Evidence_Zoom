"""Synthetic garage repair invoices with counterfactual pairs.

    python3 -m eval.data.repair_invoice.generate

Writes images/inv-XXX[a|b].png, items.jsonl, items_dev.jsonl and items_heldout.jsonl next to this file.
Motor-claim use case: an insurer checks a repair invoice. Line items, totals and references are printed
text (OCR suffices); which payment option is marked and whether the invoice carries a rotated ink stamp
are only visible in pixels. The stamp's word is also printed in the stamp area's caption on every invoice
("PAID" / "APPROVED"), so finding the word in OCR text does not tell whether a stamp is there.
Each base invoice `inv-XXXa` has a partner `inv-XXXb` identical except for ONE detail: the stamp is
added/removed, or the payment mark moves to another option.

Templates:
  A (dev)      A4 portrait, sans-serif, Pos | Description | Qty | Unit price | Amount table, ticked
               payment checkboxes, rectangular red "PAID" stamp over the totals. 1500 x 2120 px.
  B (held-out) landscape, monospace, details and totals on the left, Code | Description | Qty | Amount
               table on the right, payment option circled by hand, round blue insurer "APPROVED" stamp,
               slight rotation. 1900 x 1250 px.
All garages, customers, plates and references are fictitious. Gold boxes are recorded while drawing.
"""
from __future__ import annotations

import json
import math
import random
from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache
from itertools import permutations
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
SEED = 202

# ---------------------------------------------------------------------------------------------------
# Shared synthetic-page helpers. Duplicated verbatim in every new set's generate.py on purpose, so each
# set folder is self-contained and can be regenerated on its own.
# ---------------------------------------------------------------------------------------------------
_SF = "/System/Library/Fonts/"
_SUP = _SF + "Supplemental/"
_DJ = "/usr/share/fonts/truetype/dejavu/"
_FONTS = {
    "sans": [_SF + "Helvetica.ttc", _SUP + "Arial.ttf", _DJ + "DejaVuSans.ttf"],
    "sansb": [_SUP + "Arial Bold.ttf", _DJ + "DejaVuSans-Bold.ttf"],
    "narrow": [_SUP + "Arial Narrow.ttf", _SUP + "Arial.ttf", _DJ + "DejaVuSansCondensed.ttf"],
    "narrowb": [_SUP + "Arial Narrow Bold.ttf", _SUP + "Arial Bold.ttf", _DJ + "DejaVuSansCondensed-Bold.ttf"],
    "serif": [_SUP + "Georgia.ttf", _SF + "Times.ttc", _DJ + "DejaVuSerif.ttf"],
    "serifb": [_SUP + "Georgia Bold.ttf", _DJ + "DejaVuSerif-Bold.ttf"],
    "mono": [_SUP + "Courier New.ttf", _SF + "Menlo.ttc", _DJ + "DejaVuSansMono.ttf"],
    "monob": [_SUP + "Courier New Bold.ttf", _DJ + "DejaVuSansMono-Bold.ttf"],
    "hand": [_SUP + "Bradley Hand Bold.ttf", _SF + "Noteworthy.ttc", _DJ + "DejaVuSans.ttf"],
    "note": [_SF + "Noteworthy.ttc", _SF + "MarkerFelt.ttc", _DJ + "DejaVuSans.ttf"],
    "stamp": [_SUP + "Impact.ttf", _SUP + "Arial Black.ttf", _DJ + "DejaVuSans-Bold.ttf"],
}


@lru_cache(maxsize=None)
def font(kind: str, size: int):
    for p in _FONTS[kind]:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def text(d: ImageDraw.ImageDraw, xy, s: str, f, fill="black", anchor="la") -> list[float]:
    """Draw text and return its pixel bbox (recorded at draw time, used for gold boxes)."""
    d.text(xy, s, font=f, fill=fill, anchor=anchor)
    return list(d.textbbox(xy, s, font=f, anchor=anchor))


def union(*bs) -> list[float]:
    return [min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs)]


def finish(img: Image.Image, seed: int, angle: float = 0.0, noise: float = 1.2) -> Image.Image:
    """Light realism, identical for both images of a pair (same seed and angle): an optional small rotation
    about the image centre, then uneven illumination and soft luminance grain."""
    if angle:
        img = img.rotate(angle, resample=Image.BICUBIC, fillcolor=img.getpixel((3, 3)))
    rng = np.random.default_rng(seed)
    a = np.asarray(img, dtype=np.float32)
    h, w = a.shape[:2]
    gx, gy = np.meshgrid(np.linspace(-1, 1, w, dtype=np.float32), np.linspace(-1, 1, h, dtype=np.float32))
    cx, cy = rng.uniform(-1, 1, 2)
    gain = 1.0 - 0.06 * ((gx - cx) ** 2 + (gy - cy) ** 2) / 4.0
    # grain at 1/6 resolution (fine per-pixel noise would blow up PNG size)
    g = rng.normal(0.0, noise, (h // 6 + 2, w // 6 + 2)).astype(np.float32)
    g = np.asarray(Image.fromarray(g).resize((w, h), Image.BILINEAR))
    a = a * gain[..., None] + g[..., None]
    return Image.fromarray(np.clip(np.round(a), 0, 255).astype(np.uint8))


def to_norm(b, w: int, h: int, angle: float = 0.0, pad: float = 4) -> list[float]:
    """Pixel box drawn on the unrotated page -> normalized box on the final (rotated) image."""
    x0, y0, x1, y1 = b[0] - pad, b[1] - pad, b[2] + pad, b[3] + pad
    if angle:
        t = math.radians(angle)
        c, s = math.cos(t), math.sin(t)
        cx, cy = w / 2, h / 2
        pts = [(x, y) for x in (x0, x1) for y in (y0, y1)]
        xs = [cx + (x - cx) * c + (y - cy) * s for x, y in pts]
        ys = [cy - (x - cx) * s + (y - cy) * c for x, y in pts]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    return [round(min(max(x0 / w, 0.0), 1.0), 4), round(min(max(y0 / h, 0.0), 1.0), 4),
            round(min(max(x1 / w, 0.0), 1.0), 4), round(min(max(y1 / h, 0.0), 1.0), 4)]


def multi(names: list[str]) -> tuple[str, list[str]]:
    """Gold string and every accepted ordering for a multi-valued answer."""
    gold = ", ".join(names)
    acc = []
    for p in permutations(names):
        for sep in (", ", " and ", "; "):
            s = sep.join(p)
            if s != gold and s not in acc:
                acc.append(s)
    return gold, acc


def item_factory(image_id: str, pair_id: str, note: str, w: int, h: int, angle: float):
    path = f"images/{image_id}.png"

    def q(n: int, question: str, answer, etype: str, boxes=(), acc=()) -> dict:
        return {"question_id": f"{image_id}-q{n}", "image_id": image_id, "image_path": path,
                "question": question, "answer": answer, "answerable": answer is not None,
                "evidence_type": etype,
                "evidence_boxes": [to_norm(b, w, h, angle) for b in boxes] if answer is not None else [],
                "accepted_answers": list(acc), "pair_id": pair_id, "source": "synthetic", "notes": note}
    return q


def write_items(here: Path, lines: list[dict]) -> None:
    """items.jsonl = everything; items_dev.jsonl / items_heldout.jsonl = split by template (see README)."""
    dump = lambda ls: "".join(json.dumps(l) + "\n" for l in ls)
    (here / "items.jsonl").write_text(dump(lines))
    (here / "items_dev.jsonl").write_text(dump([l for l in lines if "held-out" not in l["notes"]]))
    (here / "items_heldout.jsonl").write_text(dump([l for l in lines if "held-out" in l["notes"]]))


def hand_tick(d: ImageDraw.ImageDraw, box, rng: random.Random, fill=(20, 40, 140), width=5) -> None:
    """A hand-drawn check mark inside box (x0, y0, x1, y1)."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    j = lambda: rng.uniform(-0.06, 0.06)
    pts = [(x0 + w * (0.15 + j()), y0 + h * (0.55 + j())), (x0 + w * (0.42 + j()), y0 + h * (0.85 + j())),
           (x0 + w * (0.92 + j()), y0 + h * (0.08 + j()))]
    d.line(pts, fill=fill, width=width, joint="curve")


def hand_cross(d: ImageDraw.ImageDraw, box, rng: random.Random, fill=(20, 40, 140), width=5) -> None:
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    j = lambda: rng.uniform(-0.05, 0.05) * w
    d.line([(x0 + 0.15 * w + j(), y0 + 0.15 * h + j()), (x1 - 0.15 * w + j(), y1 - 0.15 * h + j())], fill=fill, width=width)
    d.line([(x1 - 0.15 * w + j(), y0 + 0.15 * h + j()), (x0 + 0.15 * w + j(), y1 - 0.15 * h + j())], fill=fill, width=width)


def signature(d: ImageDraw.ImageDraw, box, rng: random.Random, fill=(25, 35, 120), width=4) -> None:
    """A scribbled signature filling box (x0, y0, x1, y1)."""
    x0, y0, x1, y1 = box
    n = 46
    pts = []
    for i in range(n):
        t = i / (n - 1)
        x = x0 + (x1 - x0) * (0.05 + 0.9 * t) + rng.uniform(-6, 6)
        y = (y0 + y1) / 2 + (y1 - y0) * 0.35 * math.sin(t * rng.uniform(14, 20) + rng.uniform(0, 3)) * (1 - 0.5 * t)
        pts.append((x, y))
    d.line(pts, fill=fill, width=width, joint="curve")
    d.line([(x0 + (x1 - x0) * 0.1, y1 - (y1 - y0) * 0.15), (x0 + (x1 - x0) * 0.8, y1 - (y1 - y0) * 0.25)],
           fill=fill, width=max(2, width - 1))
# ---------------------------------------------------------------------------------------------------

GARAGES = [("Garage du Lac SA", "Route de Morges 14, 1110 Morges"), ("Autohaus Feldmann AG", "Industriestr. 7, 3600 Thun"),
           ("Carrosserie Bellevue Sarl", "Ch. des Vignes 3, 1260 Nyon"), ("Officina Bernasconi", "Via Cantonale 22, 6900 Lugano"),
           ("Garage Central Jura", "Rue du Marche 9, 2800 Delemont")]
CUSTOMERS = ["Lena Vuillemin", "Marco Tschopp", "Ines Albrecht", "Yannick Perrin", "Sofia Gallo", "Thomas Egli",
             "Nadia Rochat", "Luca Fontana"]
ITEMS = [("Brake pads front (set)", 85, 140, 1, 1), ("Brake disc front", 120, 180, 1, 2), ("Labour (hours)", 118, 148, 1, 4),
         ("Engine oil 5W-30 (litre)", 14, 22, 4, 6), ("Oil filter", 18, 30, 1, 1), ("Wiper blades", 25, 45, 1, 2),
         ("Headlight bulb H7", 12, 20, 1, 2), ("Rear bumper repaint", 380, 520, 1, 1), ("Windscreen replacement", 650, 900, 1, 1),
         ("Side mirror, left", 210, 300, 1, 1), ("Diagnostic scan", 90, 120, 1, 1), ("Air filter", 25, 40, 1, 1),
         ("Tyre 205/55 R16", 110, 160, 2, 4), ("Wheel alignment", 80, 110, 1, 1), ("Disposal fee", 8, 15, 1, 1)]
PAYMENTS = ["Cash", "Card", "Bank transfer"]
UNANSWERABLE = ["What is the name of the mechanic who carried out the repair?", "What is the garage's IBAN?",
                "What was the vehicle's mileage when it came in?", "By what date must the invoice be paid?",
                "What is the customer's phone number?"]
INK = (20, 40, 140)


def money(x: Decimal) -> str:
    return f"{x.quantize(Decimal('0.01'), ROUND_HALF_UP)}"


def make_invoice(rng: random.Random, template: str, idx: int) -> dict:
    garage, addr = GARAGES[(idx - 1) % len(GARAGES)]
    lines = []
    for desc, lo, hi, qlo, qhi in rng.sample(ITEMS, rng.randint(5, 7)):
        qty = rng.randint(qlo, qhi)
        unit = Decimal(rng.randint(lo * 20, hi * 20)) / 20
        lines.append({"desc": desc, "qty": qty, "unit": unit, "amount": unit * qty, "code": f"{rng.randint(100, 999)}-{rng.randint(10, 99)}"})
    sub = sum((l["amount"] for l in lines), Decimal(0))
    vat = (sub * Decimal("0.081")).quantize(Decimal("0.01"), ROUND_HALF_UP)
    letters = "ABCDEFGHJKLMNPRSTUVWXYZ"
    return {"template": template, "garage": garage, "addr": addr, "customer": rng.choice(CUSTOMERS),
            "number": f"{rng.choice(['R', 'F', 'INV'])}-{rng.randint(2024, 2026)}-{rng.randint(10000, 99999)}",
            "date": f"{rng.randint(1, 28):02d}.{rng.randint(1, 12):02d}.2026",
            "plate": f"{rng.choice(['VD', 'GE', 'BE', 'TI', 'JU', 'FR'])} {rng.randint(10000, 899999)}",
            "claim": f"CL-{rng.randint(100000, 999999)}", "lines": lines, "sub": sub, "vat": vat, "total": sub + vat,
            "payment": rng.randrange(3), "stamp": rng.random() < 0.5,
            "stamp_date": f"{rng.randint(1, 28):02d}.{rng.randint(1, 12):02d}.2026",
            "seed": SEED * 1000 + idx, "angle": 0.0 if template == "A" else rng.choice([1.2, -1.4]),
            "unans": UNANSWERABLE[idx % len(UNANSWERABLE)]}


def stamp_layer(kind: str, p: dict) -> Image.Image:
    if kind == "rect":
        col = (196, 30, 45, 205)
        L = Image.new("RGBA", (380, 170), (0, 0, 0, 0))
        d = ImageDraw.Draw(L)
        d.rounded_rectangle((4, 4, 376, 166), 14, outline=col, width=7)
        d.rounded_rectangle((16, 16, 364, 154), 10, outline=col, width=3)
        d.text((190, 72), "PAID", font=font("stamp", 84), fill=col, anchor="mm")
        d.text((190, 132), p["stamp_date"], font=font("sansb", 26), fill=col, anchor="mm")
        return L.rotate(17, resample=Image.BICUBIC, expand=True)
    col = (30, 70, 175, 200)
    L = Image.new("RGBA", (330, 330), (0, 0, 0, 0))
    d = ImageDraw.Draw(L)
    d.ellipse((5, 5, 325, 325), outline=col, width=8)
    d.ellipse((30, 30, 300, 300), outline=col, width=3)
    d.text((165, 105), "LEMANIC", font=font("sansb", 30), fill=col, anchor="mm")
    d.text((165, 168), "APPROVED", font=font("stamp", 56), fill=col, anchor="mm")
    d.text((165, 228), p["stamp_date"], font=font("sansb", 26), fill=col, anchor="mm")
    return L.rotate(-12, resample=Image.BICUBIC, expand=True)


def paste_stamp(img: Image.Image, L: Image.Image, xy) -> list[float]:
    img.paste(L, (int(xy[0]), int(xy[1])), L)
    x0, y0, x1, y1 = L.getbbox()
    return [xy[0] + x0, xy[1] + y0, xy[0] + x1, xy[1] + y1]


def render_a(p: dict) -> tuple[Image.Image, dict]:
    W, H = 1500, 2120
    img = Image.new("RGB", (W, H), (252, 251, 247))
    d = ImageDraw.Draw(img)
    bx = {}
    d.ellipse((60, 60, 170, 170), fill=(30, 90, 150))
    text(d, (115, 115), "".join(w[0] for w in p["garage"].split()[:2]), font("sansb", 44), "white", "mm")
    text(d, (195, 66), p["garage"], font("sansb", 40), (25, 25, 25))
    text(d, (195, 120), p["addr"], font("sans", 26), (80, 80, 80))
    text(d, (195, 154), "Tel. 0" + str(21 + p["seed"] % 70) + " 555 " + str(10 + p["seed"] % 89) + " 00", font("sans", 26), (80, 80, 80))
    text(d, (1430, 70), "INVOICE", font("sansb", 60), (30, 90, 150), "ra")
    y = 250
    for key, label in (("number", "Invoice no."), ("date", "Date"), ("plate", "Vehicle"), ("claim", "Claim ref.")):
        a = text(d, (870, y), label, font("sans", 28), (90, 90, 90))
        b = text(d, (1080, y), p[key], font("sansb", 28), (20, 20, 20))
        bx[key] = union(a, b)
        y += 46
    text(d, (80, 250), "Bill to", font("sans", 26), (90, 90, 90))
    bx["customer"] = text(d, (80, 286), p["customer"], font("sansb", 30), (20, 20, 20))
    text(d, (80, 326), "c/o Lemanic Assurance, claims dept.", font("sans", 26), (60, 60, 60))
    # table
    cols = [(80, "Pos", "la"), (170, "Description", "la"), (930, "Qty", "ra"), (1170, "Unit price", "ra"), (1420, "Amount", "ra")]
    ty = 520
    d.rectangle((70, ty, 1430, ty + 56), fill=(225, 232, 240))
    for x, lab, an in cols:
        text(d, (x, ty + 14), lab, font("sansb", 28), (20, 20, 20), an)
    ty += 56
    for i, l in enumerate(p["lines"]):
        yy = ty + i * 58
        d.line((70, yy + 58, 1430, yy + 58), fill=(200, 200, 200), width=1)
        f = font("sans", 28)
        pb = text(d, (80, yy + 14), str(i + 1), f)
        db = text(d, (170, yy + 14), l["desc"], f)
        qb = text(d, (930, yy + 14), str(l["qty"]), f, "black", "ra")
        ub = text(d, (1170, yy + 14), money(l["unit"]), f, "black", "ra")
        ab = text(d, (1420, yy + 14), money(l["amount"]), f, "black", "ra")
        bx[f"row{i}"] = [70, yy, 1430, yy + 58]
        bx[f"desc{i}"], bx[f"amount{i}"] = db, ab
    ty += len(p["lines"]) * 58 + 30
    for key, label, fb in (("sub", "Subtotal", "sans"), ("vat", "VAT 8.1%", "sans"), ("total", "Total CHF", "sansb")):
        a = text(d, (960, ty), label, font(fb, 30))
        b = text(d, (1420, ty), money(p[key]), font(fb, 30), "black", "ra")
        bx[key] = union(a, b)
        ty += 50
    # payment method
    py = ty + 50
    text(d, (80, py), "Payment method:", font("sansb", 28))
    x = 340
    for k, name in enumerate(PAYMENTS):
        cb = (x, py - 2, x + 34, py + 32)
        d.rectangle(cb, outline=(40, 40, 40), width=3)
        lb = text(d, (x + 48, py), name, font("sans", 28))
        bx[f"pay{k}"] = union(list(cb), lb)
        if k == p["payment"]:
            hand_tick(d, (cb[0] - 4, cb[1] - 12, cb[2] + 10, cb[3] + 2), random.Random(p["seed"] + k), INK, 6)
        x = lb[2] + 60
    bx["payall"] = union(*(bx[f"pay{k}"] for k in range(3)))
    # office-use stamp area (caption always contains the word PAID)
    oy = py + 110
    area = (860, oy, 1430, oy + 230)
    d.rectangle(area, outline=(150, 150, 150), width=2)
    text(d, (872, oy + 10), "For office use (PAID stamp)", font("sans", 22), (110, 110, 110))
    bx["stamp"] = list(area)
    # signature + footer
    sy = oy + 120
    d.line((80, sy + 80, 600, sy + 80), fill=(60, 60, 60), width=2)
    text(d, (80, sy + 90), "Customer signature", font("sans", 24), (90, 90, 90))
    signature(d, (110, sy, 520, sy + 75), random.Random(p["seed"] * 7), INK)
    text(d, (750, 2040), "Thank you for your trust.  VAT no. CHE-" + str(100 + p["seed"] % 800) + ".482.117 MWST",
         font("sans", 22), (110, 110, 110), "mm")
    if p["stamp"]:
        sb = paste_stamp(img, stamp_layer("rect", p), (area[0] + 60, area[1] - 110))
        bx["stamp"] = union(bx["stamp"], sb)
    return img, bx


def render_b(p: dict) -> tuple[Image.Image, dict]:
    W, H = 1900, 1250
    img = Image.new("RGB", (W, H), (247, 246, 240))
    d = ImageDraw.Draw(img)
    bx = {}
    d.rectangle((0, 0, W, 120), fill=(45, 52, 64))
    text(d, (60, 28), p["garage"].upper(), font("serifb", 44), (245, 245, 245))
    text(d, (1840, 46), p["addr"], font("serif", 26), (210, 210, 210), "ra")
    text(d, (60, 150), "REPAIR INVOICE", font("monob", 40), (20, 20, 20))
    y = 220
    for key, label in (("number", "Invoice"), ("date", "Date"), ("customer", "Customer"), ("plate", "Plate"), ("claim", "Claim")):
        a = text(d, (60, y), f"{label:<9}:", font("mono", 28), (60, 60, 60))
        b = text(d, (260, y), p[key], font("monob", 28), (20, 20, 20))
        bx[key] = union(a, b)
        y += 44
    # totals
    y += 30
    d.line((60, y, 680, y), fill=(80, 80, 80), width=2)
    y += 16
    for key, label in (("sub", "Net"), ("vat", "VAT 8.1%"), ("total", "TOTAL CHF")):
        fn = "monob" if key == "total" else "mono"
        a = text(d, (60, y), label, font(fn, 30))
        b = text(d, (680, y), money(p[key]), font(fn, 30), "black", "ra")
        bx[key] = union(a, b)
        y += 48
    # payment: circle one option
    y += 40
    text(d, (60, y), "Paid by (circle one):", font("mono", 26), (60, 60, 60))
    y += 52
    x = 80
    for k, name in enumerate(["CASH", "CARD", "TRANSFER"]):
        lb = text(d, (x, y), name, font("monob", 30))
        if k == p["payment"]:
            r = random.Random(p["seed"] + k)
            e = (lb[0] - 22 + r.uniform(-4, 4), lb[1] - 18, lb[2] + 22 + r.uniform(-4, 4), lb[3] + 18)
            d.ellipse(e, outline=INK, width=5)
            d.arc((e[0] + 6, e[1] - 4, e[2] + 8, e[3] + 2), 200, 300, fill=INK, width=4)
        bx[f"pay{k}"] = [lb[0] - 30, lb[1] - 24, lb[2] + 32, lb[3] + 24]
        x = lb[2] + 90
    bx["payall"] = union(*(bx[f"pay{k}"] for k in range(3)))
    # table on the right
    tx0, tx1 = 760, 1850
    ty = 160
    cols = [(780, "CODE", "la"), (960, "DESCRIPTION", "la"), (1600, "QTY", "ra"), (1835, "AMOUNT", "ra")]
    d.line((tx0, ty + 50, tx1, ty + 50), fill=(30, 30, 30), width=3)
    for x, lab, an in cols:
        text(d, (x, ty + 10), lab, font("monob", 26), (20, 20, 20), an)
    ty += 56
    for i, l in enumerate(p["lines"]):
        yy = ty + i * 56
        f = font("mono", 26)
        text(d, (780, yy + 14), l["code"], f, (70, 70, 70))
        db = text(d, (960, yy + 14), l["desc"], f)
        text(d, (1600, yy + 14), str(l["qty"]), f, "black", "ra")
        ab = text(d, (1835, yy + 14), money(l["amount"]), f, "black", "ra")
        for xx in range(tx0, tx1, 18):
            d.line((xx, yy + 54, xx + 9, yy + 54), fill=(170, 170, 170), width=1)
        bx[f"row{i}"] = [tx0, yy, tx1, yy + 56]
        bx[f"desc{i}"], bx[f"amount{i}"] = db, ab
    # insurer stamp area (caption always contains APPROVED)
    area = (1240, 820, 1850, 1180)
    d.rectangle(area, outline=(150, 150, 150), width=2)
    text(d, (1254, 832), "Insurer stamp (APPROVED / REJECTED)", font("mono", 22), (110, 110, 110))
    bx["stamp"] = list(area)
    d.line((760, 1120, 1180, 1120), fill=(60, 60, 60), width=2)
    text(d, (760, 1130), "Workshop signature", font("mono", 22), (90, 90, 90))
    signature(d, (790, 1040, 1150, 1112), random.Random(p["seed"] * 7), (30, 30, 30))
    if p["stamp"]:
        sb = paste_stamp(img, stamp_layer("round", p), (area[0] + 150, area[1] - 30))
        bx["stamp"] = union(bx["stamp"], sb)
    return img, bx


def counterfactual(rng: random.Random, base: dict, idx: int) -> tuple[dict, str]:
    cf = dict(base)
    if idx % 2:
        cf["stamp"] = not base["stamp"]
        what = "stamp " + ("removed" if base["stamp"] else "added")
    else:
        cf["payment"] = rng.choice([k for k in range(3) if k != base["payment"]])
        what = f"payment mark moved from {PAYMENTS[base['payment']]} to {PAYMENTS[cf['payment']]}"
    return cf, what


def items_for(p: dict, image_id: str, pair_id: str, note: str, w: int, h: int, bx: dict) -> list[dict]:
    q = item_factory(image_id, pair_id, note, w, h, p["angle"])
    rng = random.Random(p["seed"])
    n = len(p["lines"])
    a_i = rng.randrange(n)
    b_i = rng.randrange(n - 1)
    L = p["lines"]
    amt, tot = money(L[a_i]["amount"]), money(p["total"])
    pay = PAYMENTS[p["payment"]]
    if p["template"] == "A":
        pay_q = "Which payment method is ticked on the invoice?"
        st_q = "Has a PAID stamp been applied to this invoice? Answer yes or no."
    else:
        pay_q = "Which payment option is circled on the invoice?"
        st_q = "Does this invoice carry the insurer's APPROVED stamp? Answer yes or no."
    pay_acc = {"Cash": ["cash"], "Card": ["card"], "Bank transfer": ["transfer", "bank transfer"]}[pay]
    return [
        q(1, "What is the invoice number?", p["number"], "text", [bx["number"]]),
        q(2, "What is the registration plate of the repaired vehicle?", p["plate"], "text", [bx["plate"]]),
        q(3, f"What amount is charged for the line '{L[a_i]['desc']}'?", amt, "layout", [bx[f"row{a_i}"]],
          [f"CHF {amt}", f"{amt} CHF"]),
        q(4, f"Which line item is listed directly below '{L[b_i]['desc']}'?", L[b_i + 1]["desc"], "layout",
          [bx[f"desc{b_i}"], bx[f"desc{b_i + 1}"]]),
        q(5, "What is the total amount of the invoice including VAT?", tot, "text", [bx["total"]], [f"CHF {tot}", f"{tot} CHF"]),
        q(6, pay_q, pay, "visual", [bx["payall"]], pay_acc),
        q(7, st_q, "yes" if p["stamp"] else "no", "visual", [bx["stamp"]]),
        q(8, p["unans"], None, "text"),
    ]


def main() -> None:
    rng = random.Random(SEED)
    (HERE / "images").mkdir(exist_ok=True)
    lines = []
    for idx, template in enumerate(["A", "A", "A", "B", "B"], start=1):
        base = make_invoice(rng, template, idx)
        cf, what = counterfactual(rng, base, idx)
        split = "dev" if template == "A" else "held-out"
        for suffix, p, extra in (("a", base, "base"), ("b", cf, f"counterfactual: {what}")):
            image_id = f"inv-{idx:03d}{suffix}"
            img, bx = (render_a if template == "A" else render_b)(p)
            img = finish(img, p["seed"], p["angle"])
            img.save(HERE / "images" / f"{image_id}.png")
            lines += items_for(p, image_id, f"inv-{idx:03d}", f"template {template} ({split}); {extra}",
                               img.width, img.height, bx)
    write_items(HERE, lines)
    print(f"wrote {len(lines) // 8} images and {len(lines)} items to {HERE}")


if __name__ == "__main__":
    main()
