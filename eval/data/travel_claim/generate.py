"""Synthetic travel-medical claim forms (yes/no questionnaire grid) with counterfactual pairs.

    python3 -m eval.data.travel_claim.generate

Writes images/clm-XXX[a|b].png, items.jsonl, items_dev.jsonl and items_heldout.jsonl next to this file.
Travel-insurance use case: a claimant fills in a medical expenses claim abroad. Personal data and the
expenses table are typed text, the description of events is handwriting, and the yes/no answers and the
signature exist only as pen marks (pixels). Question texts and the "Yes"/"No" captions are printed for every
question, so OCR text alone cannot tell which answer was marked.
Each base form `clm-XXXa` has a partner `clm-XXXb` identical except for ONE detail: one questionnaire answer
flips (yes <-> no), or the declaration signature is added/removed.

Templates:
  A (dev)      A4 portrait, sans-serif, numbered sections; questionnaire as a ruled table with separate
               Yes / No checkbox columns (marked with a cross). 1400 x 1980 px.
  B (held-out) landscape, serif, two columns; questions as a numbered list with inline radio circles
               (filled by pen), description and signature boxes on the right, slight rotation. 2000 x 1400 px.
All persons, insurers and references are fictitious. Gold boxes are recorded while drawing.
"""
from __future__ import annotations

import json
import math
import random
from functools import lru_cache
from itertools import permutations
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
SEED = 303

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

NAMES = ["Clara Wenger", "Jonas Morel", "Elif Aydin", "Pascal Imhof", "Giulia Ferri", "Noah Baumann", "Amelie Junod",
         "David Kuster"]
PLACES = [("Valencia", "Spain"), ("Porto", "Portugal"), ("Split", "Croatia"), ("Innsbruck", "Austria"),
          ("Thessaloniki", "Greece"), ("Bordeaux", "France"), ("Krakow", "Poland")]
QUESTIONS = ["Did you need emergency treatment?", "Were you admitted to hospital overnight?",
             "Was the illness or injury caused by an accident?", "Did you have this condition before travelling?",
             "Were you repatriated to your home country?", "Is another person responsible for the injury?",
             "Did a doctor advise against travelling?", "Have you claimed these costs from another insurer?"]
EXPENSES = ["Emergency room", "Hospital stay", "Pharmacy", "X-ray", "Taxi to hospital", "Doctor consultation",
            "Physiotherapy"]
EVENTS = ["I slipped on wet stairs at the hotel in {c} and hurt my {b}. The reception called a taxi to the clinic.",
          "During a walking tour in {c} I fell on the pavement and injured my {b}. I was treated the same day.",
          "On the second day in {c} I had strong pain in my {b} and went to the emergency room near the station."]
BODY = ["left wrist", "right ankle", "knee", "shoulder", "back"]
UNANSWERABLE = ["What is the name of the treating doctor?", "What is the claimant's IBAN?", "What was the diagnosis?",
                "What is the claimant's e-mail address?", "What is the address of the hospital?"]
INK = (25, 40, 130)


def wrap(s: str, n: int) -> list[str]:
    words, lines, cur = s.split(), [], ""
    for w_ in words:
        if cur and len(cur) + 1 + len(w_) > n:
            lines.append(cur)
            cur = w_
        else:
            cur = (cur + " " + w_).strip()
    return lines + [cur]


def make_form(rng: random.Random, template: str, idx: int) -> dict:
    city, country = rng.choice(PLACES)
    exps = [(t, f"{rng.randint(1, 28):02d}.0{rng.randint(6, 9)}.2026", f"{rng.randint(25, 1900)}.{rng.choice(['00', '50', '80', '20'])}")
            for t in rng.sample(EXPENSES, rng.randint(3, 4))]
    answers = [rng.random() < 0.45 for _ in range(6)]
    return {"template": template, "insurer": rng.choice(["Edelweiss Travel Cover", "Mistral Assistance", "Nordlicht Reise"]),
            "name": rng.choice(NAMES), "policy": f"TRV-{rng.randint(10, 99)}-{rng.randint(100000, 999999)}",
            "dob": f"{rng.randint(1, 28):02d}.{rng.randint(1, 12):02d}.{rng.randint(1955, 2003)}",
            "city": city, "country": country, "trip": f"{rng.randint(1, 9):02d}.06.2026 - {rng.randint(10, 28)}.06.2026",
            "questions": rng.sample(QUESTIONS, 6), "answers": answers, "expenses": exps,
            "event": rng.choice(EVENTS).format(c=city, b=rng.choice(BODY)),
            "signed": rng.random() < 0.6, "sign_date": f"{rng.randint(10, 28)}.07.2026",
            "seed": SEED * 1000 + idx, "angle": 0.0 if template == "A" else rng.choice([-1.1, 1.5]),
            "unans": UNANSWERABLE[idx % len(UNANSWERABLE)]}


def render_a(p: dict) -> tuple[Image.Image, dict]:
    W, H = 1400, 1980
    img = Image.new("RGB", (W, H), (253, 253, 250))
    d = ImageDraw.Draw(img)
    bx = {}
    blue = (20, 70, 140)
    text(d, (70, 60), p["insurer"], font("sansb", 30), blue)
    text(d, (70, 104), "Travel Medical Claim Form", font("sansb", 50), (20, 20, 20))
    d.line((70, 175, 1330, 175), fill=blue, width=4)

    def section(y, title):
        d.rectangle((70, y, 1330, y + 42), fill=(226, 234, 246))
        text(d, (84, y + 8), title, font("sansb", 26), blue)
        return y + 58

    y = section(200, "1  Insured person")
    fields = [("name", "Full name"), ("policy", "Policy no."), ("dob", "Date of birth"), ("country", "Destination country"),
              ("trip", "Travel dates")]
    for i, (key, lab) in enumerate(fields):
        cx, cy = (84, y + (i // 2) * 72) if i % 2 == 0 else (720, y + (i // 2) * 72)
        a = text(d, (cx, cy), lab, font("sans", 22), (100, 100, 100))
        b = text(d, (cx, cy + 28), p[key], font("sans", 30), (15, 15, 15))
        d.line((cx, cy + 66, cx + 560, cy + 66), fill=(190, 190, 190), width=1)
        bx[key] = union(a, b)
    y = section(y + 230, "2  Medical questionnaire (tick one box per question)")
    # header row
    d.rectangle((70, y, 1330, y + 44), outline=(120, 120, 120), width=2)
    text(d, (84, y + 10), "No.", font("sansb", 24))
    text(d, (160, y + 10), "Question", font("sansb", 24))
    text(d, (1150, y + 22), "Yes", font("sansb", 24), "black", "mm")
    text(d, (1265, y + 22), "No", font("sansb", 24), "black", "mm")
    qtop = y
    y += 44
    for i, (qs, ans) in enumerate(zip(p["questions"], p["answers"])):
        d.rectangle((70, y, 1330, y + 64), outline=(120, 120, 120), width=2)
        d.line((140, y, 140, y + 64), fill=(120, 120, 120), width=2)
        d.line((1090, y, 1090, y + 64), fill=(120, 120, 120), width=2)
        d.line((1210, y, 1210, y + 64), fill=(120, 120, 120), width=2)
        nb = text(d, (100, y + 32), str(i + 1), font("sans", 26), "black", "mm")
        tb = text(d, (160, y + 18), qs, font("sans", 26))
        yb = (1132, y + 14, 1168, y + 50)
        nbx = (1247, y + 14, 1283, y + 50)
        d.rectangle(yb, outline=(40, 40, 40), width=3)
        d.rectangle(nbx, outline=(40, 40, 40), width=3)
        hand_cross(d, yb if ans else nbx, random.Random(p["seed"] * 10 + i), INK, 5)
        bx[f"q{i}"] = [70, y, 1330, y + 64]
        y += 64
    bx["grid"] = [70, qtop, 1330, y]
    y = section(y + 30, "3  Expenses claimed")
    for x, lab in ((84, "Type"), (640, "Date"), (1300, "Amount (EUR)")):
        text(d, (x, y), lab, font("sansb", 24), "black", "ra" if x == 1300 else "la")
    y += 40
    for i, (t, dt, amt) in enumerate(p["expenses"]):
        a = text(d, (84, y), t, font("sans", 28))
        text(d, (640, y), dt, font("sans", 28))
        b = text(d, (1300, y), amt, font("sans", 28), "black", "ra")
        d.line((84, y + 42, 1300, y + 42), fill=(205, 205, 205), width=1)
        bx[f"exp{i}"] = [76, y - 6, 1310, y + 44]
        y += 50
    y = section(y + 24, "4  Description of events")
    box = (84, y, 1316, y + 190)
    d.rectangle(box, outline=(150, 150, 150), width=2)
    for i, ln in enumerate(wrap(p["event"], 58)):
        text(d, (104, y + 14 + i * 52), ln, font("note", 36), INK)
    bx["event"] = list(box)
    y = section(y + 214, "5  Declaration")
    text(d, (84, y), "I confirm that the information given is true and complete.", font("sans", 24), (60, 60, 60))
    y += 50
    sbox = (84, y, 700, y + 130)
    d.rectangle(sbox, outline=(150, 150, 150), width=2)
    text(d, (96, y + 8), "Signature of insured person", font("sans", 20), (120, 120, 120))
    if p["signed"]:
        signature(d, (140, y + 38, 640, y + 118), random.Random(p["seed"] * 3), INK)
    bx["sign"] = list(sbox)
    dbox = (760, y, 1316, y + 130)
    d.rectangle(dbox, outline=(150, 150, 150), width=2)
    text(d, (772, y + 8), "Date", font("sans", 20), (120, 120, 120))
    text(d, (800, y + 50), p["sign_date"], font("note", 40), INK)
    return img, bx


def render_b(p: dict) -> tuple[Image.Image, dict]:
    W, H = 2000, 1400
    img = Image.new("RGB", (W, H), (250, 248, 242))
    d = ImageDraw.Draw(img)
    bx = {}
    green = (30, 95, 70)
    text(d, (60, 50), "CLAIM FOR MEDICAL EXPENSES ABROAD", font("serifb", 44), green)
    text(d, (1940, 62), p["insurer"], font("serif", 32), (60, 60, 60), "ra")
    d.line((60, 120, 1940, 120), fill=green, width=3)
    # left column: personal data then expenses
    y = 160
    for key, lab in (("policy", "Policy number"), ("name", "Insured person"), ("dob", "Born"), ("trip", "Trip"),
                     ("country", "Country of treatment")):
        a = text(d, (60, y), lab + ":", font("serif", 26), (80, 80, 80))
        b = text(d, (380, y - 4), p[key], font("mono", 30), (15, 15, 15))
        d.line((380, y + 34, 930, y + 34), fill=(170, 170, 170), width=1)
        bx[key] = union(a, b)
        y += 58
    y += 30
    text(d, (60, y), "Expenses", font("serifb", 30), green)
    y += 50
    for i, (t, dt, amt) in enumerate(p["expenses"]):
        a = text(d, (60, y), f"{dt}", font("mono", 26), (90, 90, 90))
        b = text(d, (260, y), t, font("serif", 28))
        c = text(d, (930, y), f"EUR {amt}", font("mono", 28), "black", "ra")
        bx[f"exp{i}"] = [52, y - 8, 940, y + 40]
        for xx in range(60, 930, 14):
            d.line((xx, y + 40, xx + 6, y + 40), fill=(180, 180, 180), width=1)
        y += 54
    # description box (left, bottom)
    y += 30
    text(d, (60, y), "What happened?", font("serifb", 30), green)
    box = (60, y + 46, 940, y + 330)
    d.rectangle(box, outline=(140, 140, 140), width=2)
    for i, ln in enumerate(wrap(p["event"], 40)):
        text(d, (80, y + 60 + i * 52), ln, font("hand", 34), INK)
    bx["event"] = list(box)
    # right column: questions with inline radio circles
    x0 = 1020
    text(d, (x0, 160), "Health questions (fill in one circle)", font("serifb", 30), green)
    y = 225
    qtop = y - 10
    for i, (qs, ans) in enumerate(zip(p["questions"], p["answers"])):
        tb = text(d, (x0, y), f"{i + 1}. {qs}", font("serif", 26))
        cy = y + 56
        res = {}
        for lab, xx in (("Yes", 1560), ("No", 1740)):
            c = (xx, cy - 15, xx + 30, cy + 15)
            d.ellipse(c, outline=(40, 40, 40), width=3)
            lt = text(d, (xx + 42, cy), lab, font("serif", 26), "black", "lm")
            res[lab] = union(list(c), lt)
            if (lab == "Yes") == ans:
                r = random.Random(p["seed"] * 10 + i)
                d.ellipse((xx + 5 + r.uniform(-2, 2), cy - 10 + r.uniform(-2, 2), xx + 25, cy + 10), fill=INK)
        bx[f"q{i}"] = [x0 - 8, y - 8, 1900, cy + 22]
        y += 100
    bx["grid"] = [x0 - 8, qtop, 1900, y - 10]
    # signature
    sbox = (1020, 1060, 1600, 1300)
    d.rectangle(sbox, outline=(140, 140, 140), width=2)
    text(d, (1034, 1070), "Signature", font("serif", 24), (110, 110, 110))
    if p["signed"]:
        signature(d, (1070, 1130, 1560, 1250), random.Random(p["seed"] * 3), INK, 5)
    bx["sign"] = list(sbox)
    text(d, (1640, 1070), "Place and date", font("serif", 24), (110, 110, 110))
    text(d, (1640, 1140), p['sign_date'], font("hand", 32), INK)
    return img, bx


def counterfactual(rng: random.Random, base: dict, idx: int) -> tuple[dict, int, str]:
    cf = dict(base)
    if idx in (2, 5):
        cf["signed"] = not base["signed"]
        return cf, rng.randrange(6), "declaration signature " + ("removed" if base["signed"] else "added")
    t = rng.randrange(6)
    cf["answers"] = list(base["answers"])
    cf["answers"][t] = not base["answers"][t]
    return cf, t, f"answer to question {t + 1} flipped to {'yes' if cf['answers'][t] else 'no'}"


def items_for(p: dict, image_id: str, pair_id: str, target: int, note: str, w: int, h: int, bx: dict) -> list[dict]:
    q = item_factory(image_id, pair_id, note, w, h, p["angle"])
    rng = random.Random(p["seed"])
    e = rng.randrange(len(p["expenses"]))
    et, _, amt = p["expenses"][e]
    yes = [str(i + 1) for i, a in enumerate(p["answers"]) if a]
    if yes:
        yes_gold, yes_acc = multi(yes)
    else:
        yes_gold, yes_acc = "none", ["no question", "none of them"]
    t_ans = "yes" if p["answers"][target] else "no"
    return [
        q(1, "What is the policy number on the claim form?", p["policy"], "text", [bx["policy"]]),
        q(2, "What is the name of the insured person?", p["name"], "text", [bx["name"]]),
        q(3, f"What amount is claimed for '{et}'?", amt, "layout", [bx[f"exp{e}"]], [f"EUR {amt}", f"{amt} EUR"]),
        q(4, "According to the handwritten description, in which city did the incident happen?", p["city"], "text",
          [bx["event"]]),
        q(5, f"How did the claimant answer question {target + 1} ('{p['questions'][target]}')? Answer yes or no.", t_ans,
          "visual", [bx[f"q{target}"]]),
        q(6, "Which health questions were answered 'Yes'? Give the question numbers.", yes_gold, "visual", [bx["grid"]],
          yes_acc),
        q(7, "Has the insured person signed the declaration? Answer yes or no.", "yes" if p["signed"] else "no", "visual",
          [bx["sign"]]),
        q(8, p["unans"], None, "text"),
    ]


def main() -> None:
    rng = random.Random(SEED)
    (HERE / "images").mkdir(exist_ok=True)
    lines = []
    for idx, template in enumerate(["A", "A", "A", "B", "B"], start=1):
        base = make_form(rng, template, idx)
        cf, target, what = counterfactual(rng, base, idx)
        split = "dev" if template == "A" else "held-out"
        for suffix, p, extra in (("a", base, "base"), ("b", cf, f"counterfactual: {what}")):
            image_id = f"clm-{idx:03d}{suffix}"
            img, bx = (render_a if template == "A" else render_b)(p)
            img = finish(img, p["seed"], p["angle"])
            img.save(HERE / "images" / f"{image_id}.png")
            lines += items_for(p, image_id, f"clm-{idx:03d}", target, f"template {template} ({split}); {extra}",
                               img.width, img.height, bx)
    write_items(HERE, lines)
    print(f"wrote {len(lines) // 8} images and {len(lines)} items to {HERE}")


if __name__ == "__main__":
    main()
