"""Synthetic homework pages for the general assistant route (owner: claude-andrew-b, message 145).

Each base page has a partner identical except one visual detail (the circled multiple-choice option and the
tallest bar move), so an answer read from OCR text alone cannot pass both. Gold boxes are recorded at draw time.

    python -m eval.data.homework_v1.generate      (writes images/ and items.jsonl next to this file)
Questions per page (8): equation (text), passage fact (text), passage inference (text), triangle hypotenuse
(mixed: side labels are text, which side is which is in the drawing), circled option (visual), tallest bar (visual),
bar value (visual), student's grade (unanswerable).
"""
from __future__ import annotations

import json
import math
import os
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
OUT = Path(os.environ.get("HW_OUT", str(HERE)))
SEED = int(os.environ.get("HW_SEED", "4242"))
W, H = 1600, 2200
FONTS = ["/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Georgia.ttf",
         "/System/Library/Fonts/Supplemental/Times New Roman.ttf"]
NAMES = ["Lena", "Marco", "Aisha", "Tom", "Yuki", "Pablo", "Sara", "Jonas"]
TOWNS = ["Lausanne", "Montreux", "Sion", "Fribourg", "Nyon", "Vevey"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
TRIPLES = [(3, 4, 5), (6, 8, 10), (5, 12, 13), (9, 12, 15), (8, 15, 17)]


def font(path, size):
    return ImageFont.truetype(path, size)


def nb(box):  # normalise a pixel box
    return [round(box[0] / W, 4), round(box[1] / H, 4), round(box[2] / W, 4), round(box[3] / H, 4)]


def text(d, xy, s, f, fill=(20, 20, 20)):
    d.text(xy, s, font=f, fill=fill)
    l, t, r, b = d.textbbox(xy, s, font=f)
    return (l, t, r, b)


def make_page(rng):
    a = rng.randint(2, 9); x = rng.randint(2, 12); b = rng.randint(1, 20); c = a * x + b
    name, town = rng.choice(NAMES), rng.choice(TOWNS)
    year = rng.randint(1890, 1990)
    km = rng.randint(12, 80)
    tri = rng.choice(TRIPLES)
    opts = [str(v) for v in rng.sample(range(10, 60), 4)]
    circled = rng.randrange(4)
    bars = [rng.randint(10, 90) for _ in MONTHS]
    return dict(a=a, x=x, b=b, c=c, name=name, town=town, year=year, km=km, tri=tri, opts=opts, circled=circled,
                bars=bars, font=rng.choice(FONTS))


def partner(p, rng):
    q = dict(p); q["bars"] = list(p["bars"])
    q["circled"] = (p["circled"] + rng.randint(1, 3)) % 4
    top = max(range(6), key=lambda i: p["bars"][i])
    new = (top + rng.randint(1, 5)) % 6
    q["bars"][new] = max(p["bars"]) + rng.randint(8, 15)
    return q


def render(p):
    img = Image.new("RGB", (W, H), (252, 252, 248))
    d = ImageDraw.Draw(img)
    F = p["font"]
    h1, body, small = font(F, 44), font(F, 30), font(F, 24)
    g = {}
    text(d, (90, 70), "Homework sheet - Grade 8", h1)
    text(d, (90, 135), f"Name: {p['name']}", body)
    y = 220
    # 1. equation
    g["eq"] = text(d, (90, y), f"1. Solve for x:  {p['a']}x + {p['b']} = {p['c']}", body)
    y += 110
    # 2. passage
    t1 = text(d, (90, y), "2. Read the passage and answer the questions.", body); y += 50
    passage = [f"The old bridge in {p['town']} was built in {p['year']}. It carried the railway",
               f"across the river for many years. Today the line is {p['km']} km long and trains",
               "still cross the bridge every hour, although the original wooden deck was",
               "replaced with steel after a flood."]
    pboxes = []
    for line in passage:
        pboxes.append(text(d, (120, y), line, body)); y += 44
    g["year"] = pboxes[0]; g["km"] = pboxes[1]; g["deck"] = pboxes[2]
    g["deck2"] = pboxes[3]
    y += 60
    # 3. triangle (labels near the sides; which side is the hypotenuse is in the drawing)
    t3 = text(d, (90, y), "3. Find the length of the hypotenuse of the right triangle below.", body); y += 70
    s1, s2, hyp = p["tri"]
    ox, oy, sc = 260, y + 300, 32  # right angle at (ox, oy)
    ax, ay = ox + s2 * sc * 0.9 if False else ox + min(420, s2 * 28), oy
    bx, by = ox, oy - min(280, s1 * 28)
    d.line([(ox, oy), (ax, ay), (bx, by), (ox, oy)], fill=(30, 30, 30), width=4)
    d.rectangle([ox, oy - 26, ox + 26, oy], outline=(30, 30, 30), width=3)
    lb1 = text(d, (ox - 60, (oy + by) // 2 - 15), str(s1), body)
    lb2 = text(d, ((ox + ax) // 2 - 10, oy + 12), str(s2), body)
    lbh = text(d, ((ax + bx) // 2 + 20, (ay + by) // 2 - 40), "c", body)
    g["tri"] = (ox - 70, by - 10, ax + 60, oy + 50)
    y = oy + 110
    # 4. multiple choice, student's circle
    t4 = text(d, (90, y), f"4. Which number is divisible by 7? (circle one)", body); y += 60
    obox = []
    for i, o in enumerate(p["opts"]):
        x0 = 140 + i * 230
        obox.append(text(d, (x0, y), f"({'ABCD'[i]}) {o}", body))
    ci = p["circled"]; l, t, r, b = obox[ci]
    d.ellipse([l - 18, t - 14, r + 18, b + 14], outline=(200, 40, 40), width=4)
    g["circle"] = (l - 20, t - 16, r + 20, b + 16)
    y += 110
    # 5. bar chart
    t5 = text(d, (90, y), "5. The chart shows bicycles sold per month at a shop.", body); y += 60
    cx0, cy1, bw, gap = 200, y + 420, 110, 60
    d.line([(cx0 - 20, y), (cx0 - 20, cy1), (cx0 + 6 * (bw + gap), cy1)], fill=(30, 30, 30), width=3)
    for v in (0, 50, 100):
        yy = cy1 - v * 4
        text(d, (cx0 - 80, yy - 14), str(v), small)
        d.line([(cx0 - 26, yy), (cx0 - 20, yy)], fill=(30, 30, 30), width=2)
    bboxes = []
    for i, m in enumerate(MONTHS):
        x0 = cx0 + i * (bw + gap); v = p["bars"][i]
        d.rectangle([x0, cy1 - v * 4, x0 + bw, cy1], fill=(70, 120, 190))
        lab = text(d, (x0 + 25, cy1 + 10), m, small)
        bboxes.append((x0, cy1 - v * 4, x0 + bw, lab[3]))
    g["chart"] = (cx0 - 90, y, cx0 + 6 * (bw + gap), cy1 + 50)
    top = max(range(6), key=lambda i: p["bars"][i])
    g["top"] = bboxes[top]
    g["mar"] = bboxes[2]
    return img, g


def items_for(p, g, iid, pid):
    top = MONTHS[max(range(6), key=lambda i: p["bars"][i])]
    hyp = p["tri"][2]
    out = []

    def it(k, q, ans, et, boxes, acc=()):
        out.append({"question_id": f"{iid}-q{k}", "image_id": iid, "image_path": f"images/{iid}.png", "question": q,
                    "answer": ans, "answerable": ans is not None, "evidence_type": et,
                    "evidence_boxes": [nb(b) for b in boxes], "accepted_answers": list(acc), "pair_id": pid,
                    "source": "synthetic", "notes": None})
    it(1, "Solve problem 1. What is x?", str(p["x"]), "text", [g["eq"]], (f"x = {p['x']}", f"x={p['x']}"))
    it(2, "In the passage, in which year was the bridge built?", str(p["year"]), "text", [g["year"]])
    it(3, "According to the passage, what was the original deck replaced with?", "steel", "text", [g["deck2"]],
       ("with steel", "steel deck"))
    it(4, "What is the length of the hypotenuse in problem 3?", str(hyp), "mixed", [g["tri"]], (f"c = {hyp}",))
    it(5, "Which option did the student circle in problem 4? Answer with the letter.",
       "ABCD"[p["circled"]], "visual", [g["circle"]], (f"({'ABCD'[p['circled']]})",))
    it(6, "In the chart in problem 5, which month had the most bicycles sold?", top, "visual", [g["top"]])
    it(7, "Is the circled answer in problem 4 correct? Answer yes or no.",
       "yes" if int(p["opts"][p["circled"]]) % 7 == 0 else "no", "visual", [g["circle"]])
    it(8, "What grade did the teacher give this homework?", None, "text", [])
    return out


def main():
    rng = random.Random(SEED)
    (OUT / "images").mkdir(parents=True, exist_ok=True)
    lines = []
    for n in range(1, 6):
        base = make_page(rng)
        # make problem 4 well-posed: exactly one option divisible by 7
        opts = [v for v in rng.sample(range(10, 60), 12) if v % 7]
        sev = rng.choice([14, 21, 28, 35, 42, 49, 56])
        base["opts"] = [str(v) for v in opts[:3]] + [str(sev)]
        rng.shuffle(base["opts"])
        for tag, p in (("a", base), ("b", partner(base, rng))):
            iid, pid = f"hw-{n:03d}{tag}", f"hw-{n:03d}"
            img, g = render(p)
            img.save(OUT / "images" / f"{iid}.png")
            lines += items_for(p, g, iid, pid)
    with open(OUT / "items.jsonl", "w") as fh:
        for it in lines:
            fh.write(json.dumps(it) + "\n")
    print(len(lines), "items")


if __name__ == "__main__":
    main()
