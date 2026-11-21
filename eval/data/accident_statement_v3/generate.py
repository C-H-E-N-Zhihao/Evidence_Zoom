"""Third, independent synthetic layout of the European Accident Statement. Deterministic.

    python3 -m eval.data.accident_statement_v3.generate
"""
from __future__ import annotations

import json
import os
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
W, H = 1650, 2340
# Overrides (defaults reproduce the committed v3 set): EAS3_SEED, EAS3_OUT (output folder), EAS3_PREFIX (id prefix).
# Used to generate fresh forms of the same template, e.g. v3b (message 115).
SEED = int(os.environ.get("EAS3_SEED", "3003"))
OUT = Path(os.environ.get("EAS3_OUT", str(HERE)))
PREFIX = os.environ.get("EAS3_PREFIX", "eas3")

def font(path, size, index=0):
    return ImageFont.truetype(path, size, index=index)

PAL = "/System/Library/Fonts/Palatino.ttc"
OPT = "/System/Library/Fonts/Optima.ttc"
F_TITLE = font(PAL, 46, 2) if True else None
F_SEC = font(OPT, 30, 1)
F_LAB = font(OPT, 20, 0)
F_VAL = font("/System/Library/Fonts/Courier.ttc", 30, 0)
F_TXT = font(PAL, 24, 0)
F_NUM = font(OPT, 26, 1)
F_BIG = font(OPT, 64, 1)
F_SM = font(OPT, 17, 0)

CIRC = [
    "Vehicle was parked or standing still",
    "Vehicle was leaving a parking place or door opening",
    "Vehicle was entering a parking place",
    "Vehicle was coming out of a car park, private land or track",
    "Vehicle was entering a car park, private land or track",
    "Vehicle was entering a roundabout",
    "Vehicle was circulating on a roundabout",
    "Vehicle struck the rear of the other vehicle while travelling in the same direction and lane",
    "Vehicle was travelling in the same direction but in a different lane",
    "Vehicle was changing lanes",
    "Vehicle was overtaking",
    "Vehicle was turning right",
    "Vehicle was turning left",
    "Vehicle was reversing",
    "Vehicle encroached on the opposite carriageway",
    "Vehicle was coming from the right at a crossroads",
    "Vehicle had not observed a priority sign or red light",
]

INSURERS = ["Helvetia Nord Assurances", "Matterhorn Cover", "Lac Leman Mutual", "Jura Protect SA",
            "Alpina Versicherung", "Rhone Valley Insurance", "Saentis Garantie", "Aare Fidelity",
            "Gotthard Assurance", "Bernina Safe", "Engadin Re", "Santis Shield"]
FIRST = ["Luc", "Marta", "Jonas", "Elodie", "Paolo", "Sabine", "Tomas", "Nadia", "Hugo", "Irene", "Felix", "Chloe"]
LAST = ["Bertrand", "Keller", "Moretti", "Dubois", "Furrer", "Rochat", "Vogel", "Pasquier", "Imhof", "Zufferey", "Brunner", "Maillard"]
CANTONS = ["VD", "GE", "BE", "ZH", "VS", "FR", "TI", "LU"]


def make_forms():
    rng = random.Random(SEED)
    ins = INSURERS[:]; rng.shuffle(ins)
    fn = FIRST[:]; rng.shuffle(fn)
    ln = LAST[:]; rng.shuffle(ln)
    forms = []
    for n in range(1, 7):
        def pol(): return f"{''.join(rng.choice('ABCDEFGHKLMNPRSTVWZ') for _ in range(2))}-{rng.randint(1000, 9999)}-{rng.randint(1000, 9999)}"
        def plate(): return f"{rng.choice(CANTONS)} {rng.randint(100, 999)} {rng.randint(100, 999)}"
        veh = {}
        for k, v in enumerate("AB"):
            i = (n - 1) * 2 + k
            veh[v] = dict(insurer=ins[i], policy=pol(), plate=plate(), driver=f"{fn[i]} {ln[i]}")
        kind = "tick" if n in (1, 2, 3, 4) else "sketch"
        # A ticks 8 <=> A struck B from behind, so B is the vehicle hit
        a8 = n in (1, 3, 5, 6)
        a_ticks = {8} if a8 else {rng.choice([1, 12, 13, 14])}
        if a8:
            b_ticks = {rng.choice([[1], [3, 16], [10], [15, 17], [9]][n % 5])}if False else set(rng.choice([[1], [3, 16], [10], [15, 17], [9]]))
        else:
            b_ticks = {8} | rng.choice([set(), {10}])
        if n == 2:
            b_ticks = set()
        base = dict(n=n, veh=veh, a=a_ticks, b=b_ticks, hit="B" if a8 else "A", partner=kind)
        p = json.loads(json.dumps(base, default=list))
        p["a"], p["b"] = set(a_ticks), set(b_ticks)
        if kind == "tick":
            if not b_ticks:
                p["b"] = {rng.choice([2, 5, 11])}
            elif len(b_ticks) == 1 and n % 2:
                p["b"] = b_ticks | {rng.choice([x for x in (4, 7, 13, 16) if x not in b_ticks])}
            else:
                old = max(b_ticks)
                p["b"] = (b_ticks - {old}) | {rng.choice([x for x in (2, 6, 11, 14) if x not in b_ticks])}
        else:
            p["hit"] = "A" if base["hit"] == "B" else "B"
        base["a"], base["b"] = set(a_ticks), set(b_ticks)
        forms.append((base, p))
    return forms


def nb(box):
    return [round(box[0] / W, 4), round(box[1] / H, 4), round(box[2] / W, 4), round(box[3] / H, 4)]


def tb(d, xy, text, f):
    b = d.textbbox(xy, text, font=f)
    return [b[0] - 3, b[1] - 3, b[2] + 3, b[3] + 3]


def render(form):
    img = Image.new("RGB", (W, H), (252, 251, 247))
    d = ImageDraw.Draw(img)
    ink = (28, 30, 40)
    geo = {}
    # header
    d.rectangle([0, 0, W, 150], fill=(22, 52, 96))
    d.text((70, 36), "ACCIDENT REPORT FORM", font=F_TITLE, fill="white")
    d.text((72, 100), "European statement - to be signed by both drivers", font=F_LAB, fill=(190, 205, 230))
    d.text((W - 330, 56), "Form ref. EU-AR / 3", font=F_LAB, fill=(190, 205, 230))
    # vehicle panels stacked
    cols = {"A": ((226, 238, 252), (40, 90, 170)), "B": ((253, 238, 220), (205, 110, 20))}
    y = 175
    labels = [("insurer", "Insurance company"), ("policy", "Policy No"), ("plate", "Licence plate"), ("driver", "Name of driver")]
    for v in "AB":
        bg, ac = cols[v]
        d.rectangle([50, y, W - 50, y + 215], fill=bg, outline=ac, width=3)
        d.rectangle([50, y, 190, y + 215], fill=ac)
        d.text((120, y + 107), v, font=F_BIG, fill="white", anchor="mm")
        d.text((120, y + 175), "VEHICLE", font=F_SM, fill="white", anchor="mm")
        pos = {"insurer": (230, y + 22), "policy": (950, y + 22), "plate": (230, y + 120), "driver": (950, y + 120)}
        for key, lab in labels:
            x0, y0 = pos[key]
            d.text((x0, y0), lab, font=F_LAB, fill=(80, 85, 100))
            d.line([x0, y0 + 80, x0 + 640, y0 + 80], fill=ac, width=1)
            val = form["veh"][v][key]
            vf = F_TXT if key in ("insurer", "driver") else F_VAL
            d.text((x0 + 6, y0 + 32), val, font=vf, fill=ink)
            geo[(v, key)] = nb(tb(d, (x0 + 6, y0 + 32), val, vf))
        y += 235
    # sketch section
    sy = y + 5
    d.text((50, sy), "13.  Sketch of the accident", font=F_SEC, fill=(22, 52, 96))
    ry0, ry1 = sy + 45, sy + 440
    d.rectangle([50, ry0, W - 50, ry1], fill=(250, 250, 250), outline=(120, 120, 120), width=2)
    rx0, rx1 = 520, 1130
    d.rectangle([rx0, ry0, rx1, ry1], fill=(120, 124, 130))
    for yy in range(ry0 + 10, ry1, 50):
        d.line([(rx0 + rx1) // 2, yy, (rx0 + rx1) // 2, yy + 26], fill="white", width=5)
    d.line([rx0 + 14, ry0, rx0 + 14, ry1], fill="white", width=4)
    d.line([rx1 - 14, ry0, rx1 - 14, ry1], fill="white", width=4)
    # front vehicle (hit) up, rear vehicle down, both in right-hand lane, travelling up
    hit = form["hit"]
    other = "A" if hit == "B" else "B"
    cx = 930
    front = [cx - 70, ry0 + 60, cx + 70, ry0 + 170]
    rear = [cx - 70, ry0 + 235, cx + 70, ry0 + 345]
    for v, box in ((hit, front), (other, rear)):
        d.rounded_rectangle(box, radius=14, fill=cols[v][1], outline=(20, 20, 20), width=3)
        d.text(((box[0] + box[2]) // 2, (box[1] + box[3]) // 2), v, font=F_BIG, fill="white", anchor="mm")
        geo[("sk", v)] = nb(box)
    # direction arrow beside the vehicles
    ax = cx + 125
    d.line([ax, ry0 + 340, ax, ry0 + 90], fill=(20, 20, 20), width=6)
    d.polygon([(ax - 22, ry0 + 100), (ax + 22, ry0 + 100), (ax, ry0 + 55)], fill=(20, 20, 20))
    d.text((ax + 30, ry0 + 190), "direction\nof travel", font=F_SM, fill=(50, 50, 50))
    d.text((70, ry0 + 16), "Draw both vehicles on the road;\nmark the direction of travel.", font=F_SM, fill=(90, 90, 90))
    # circumstances
    cy = ry1 + 30
    d.text((50, cy), "12.  Circumstances", font=F_SEC, fill=(22, 52, 96))
    d.text((W - 50, cy + 8), "tick one box per line for each vehicle that applies", font=F_SM, fill=(90, 90, 90), anchor="ra")
    cy += 50
    xA, xB, xN, xT = 70, 140, 215, 290
    d.rectangle([50, cy, W - 50, cy + 36], fill=(22, 52, 96))
    d.text((xA + 24, cy + 18), "A", font=F_NUM, fill="white", anchor="mm")
    d.text((xB + 24, cy + 18), "B", font=F_NUM, fill="white", anchor="mm")
    d.text((xN - 4, cy + 18), "No.", font=F_LAB, fill="white", anchor="lm")
    d.text((xT, cy + 18), "Situation of the vehicle at the time of impact", font=F_LAB, fill="white", anchor="lm")
    cy += 36
    rh = (H - 105 - cy) // 17
    for i, text in enumerate(CIRC, 1):
        top = cy + (i - 1) * rh
        if i % 2 == 0:
            d.rectangle([50, top, W - 50, top + rh], fill=(240, 242, 247))
        d.line([50, top + rh, W - 50, top + rh], fill=(190, 195, 205), width=1)
        for v, x in (("A", xA), ("B", xB)):
            bx = [x, top + (rh - 46) // 2, x + 46, top + (rh - 46) // 2 + 46]
            d.rectangle(bx, fill="white", outline=cols[v][1], width=3)
            if i in form[v.lower()]:
                d.line([bx[0] + 8, bx[1] + 8, bx[2] - 8, bx[3] - 8], fill=ink, width=6)
                d.line([bx[0] + 8, bx[3] - 8, bx[2] - 8, bx[1] + 8], fill=ink, width=6)
            geo[("box", v, i)] = nb(bx)
        d.text((xN, top + rh // 2), str(i), font=F_NUM, fill=ink, anchor="lm")
        geo[("num", i)] = nb(tb(d, (xN, top + rh // 2 - 14), str(i), F_NUM))
        d.text((xT, top + rh // 2), text, font=F_TXT, fill=ink, anchor="lm")
    d.rectangle([50, cy, W - 50, cy + 17 * rh], outline=(120, 125, 140), width=2)
    # footer
    d.line([50, H - 80, W - 50, H - 80], fill=(150, 150, 160), width=1)
    d.text((50, H - 62), "Signature driver A: ________________", font=F_LAB, fill=(80, 85, 100))
    d.text((W - 50, H - 62), "Signature driver B: ________________", font=F_LAB, fill=(80, 85, 100), anchor="ra")
    return img, geo


def union(*bs):
    return [min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs)]


def items_for(form, geo, tag):
    n = form["n"]
    iid = f"{PREFIX}-{n:03d}{tag}"
    pid = f"{PREFIX}-{n:03d}"
    b = sorted(form["b"])
    bans = ", ".join(map(str, b)) if b else "none"
    import itertools
    acc_b = sorted({", ".join(map(str, p)) for p in itertools.permutations(b)}) if len(b) > 1 else []
    if b:
        gold4 = [geo[("box", "B", i)] for i in b] + [geo[("num", i)] for i in b]
    else:
        gold4 = [union(*[geo[("box", "B", i)] for i in range(1, 18)])]
    V = form["veh"]
    qs = [
        ("What is vehicle A's insurance policy number?", V["A"]["policy"], "text", [geo[("A", "policy")]], []),
        ("What is the registration number of vehicle B?", V["B"]["plate"], "text", [geo[("B", "plate")]], []),
        (f"Which vehicle is insured by {V['B']['insurer']}?", "B", "layout", [geo[("B", "insurer")]], ["vehicle B"]),
        ("Which circumstance boxes did driver B tick? Answer with the box numbers.", bans, "visual", gold4, acc_b),
        ("Did driver A tick circumstance 8 (striking the rear of the other vehicle)? Answer yes or no.",
         "yes" if 8 in form["a"] else "no", "visual", [geo[("box", "A", 8)]], []),
        ("In the sketch, which vehicle was hit from behind? Answer A or B.", form["hit"], "visual",
         [geo[("sk", "A")], geo[("sk", "B")]], []),
        ("What is driver A's driving licence number?", None, "text", [], []),
        ("Who is vehicle A's insurer?", V["A"]["insurer"], "text", [geo[("A", "insurer")]], []),
    ]
    out = []
    for k, (q, a, et, boxes, acc) in enumerate(qs, 1):
        out.append(dict(question_id=f"{iid}-q{k}", image_id=iid, image_path=f"images/{iid}.png", question=q,
                        answer=a, answerable=a is not None, evidence_type=et, evidence_boxes=boxes,
                        accepted_answers=acc, pair_id=pid, source="synthetic", notes=None))
    return iid, out


def main():
    (OUT / "images").mkdir(parents=True, exist_ok=True)
    lines = []
    for base, partner in make_forms():
        for tag, f in (("a", base), ("b", partner)):
            img, geo = render(f)
            iid, its = items_for(f, geo, tag)
            img.save(OUT / "images" / f"{iid}.png")
            lines += its
    with open(OUT / "items.jsonl", "w") as fh:
        for it in lines:
            fh.write(json.dumps(it) + "\n")
    print(len(lines), "items")


if __name__ == "__main__":
    main()
