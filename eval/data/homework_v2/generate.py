"""Synthetic held-out 'general vision assistant' test set (homework_v2).

Six study-page kinds, each rendered as an (a, b) pair that differ in 1-3 visual details which change the
gold answer of the visual questions. 8 questions per page, 96 items total.

    python3 -m eval.data.homework_v2.generate        # env: HW2_SEED (9091), HW2_OUT (package dir)
"""
from __future__ import annotations

import json
import math
import os
import random
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

SEED = int(os.environ.get("HW2_SEED", "9091"))
OUT = Path(os.environ.get("HW2_OUT", str(Path(__file__).resolve().parent)))
FD = "/System/Library/Fonts/Supplemental/"
FONTS = {
    "georgia": "Georgia.ttf", "georgiab": "Georgia Bold.ttf", "times": "Times New Roman.ttf",
    "timesb": "Times New Roman Bold.ttf", "verdana": "Verdana.ttf", "verdanab": "Verdana Bold.ttf",
    "tahoma": "Tahoma.ttf", "tahomab": "Tahoma Bold.ttf", "trebuchet": "Trebuchet MS.ttf",
    "trebuchetb": "Trebuchet MS Bold.ttf", "arial": "Arial.ttf", "arialb": "Arial Bold.ttf",
    "hand": "Bradley Hand Bold.ttf", "courier": "Courier New Bold.ttf", "comic": "Comic Sans MS.ttf",
}
_fc: dict = {}


def F(name: str, size: int):
    k = (name, size)
    if k not in _fc:
        _fc[k] = ImageFont.truetype(FD + FONTS[name], size)
    return _fc[k]


INK = (30, 30, 35)
RED = (205, 35, 35)
GREEN = (0, 140, 60)
BLUE = (30, 80, 200)
HANDINK = (25, 55, 165)


class Page:
    def __init__(self, W, H, bg=(252, 250, 244)):
        self.W, self.H = W, H
        self.img = Image.new("RGB", (W, H), bg)
        self.d = ImageDraw.Draw(self.img)
        self.qas: list = []

    def t(self, x, y, s, font, fill=INK, anchor="la"):
        self.d.text((x, y), s, font=font, fill=fill, anchor=anchor)
        return list(self.d.textbbox((x, y), s, font=font, anchor=anchor))

    def q(self, kind, question, answer, acc=None, boxes=None):
        self.qas.append(dict(kind=kind, question=question, answer=answer, acc=acc or [], boxes=boxes or []))


def U(*bs, pad=12):
    return [min(b[0] for b in bs) - pad, min(b[1] for b in bs) - pad, max(b[2] for b in bs) + pad, max(b[3] for b in bs) + pad]


def star(d, cx, cy, r, fill, outline=None):
    pts = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.42
        pts.append((cx + rr * math.cos(ang), cy + rr * math.sin(ang)))
    d.polygon(pts, fill=fill, outline=outline)
    if outline:
        d.line(pts + [pts[0]], fill=outline, width=3)


def tick(d, x, y, s, col=GREEN, w=11):
    d.line([(x, y + 0.55 * s), (x + 0.35 * s, y + s), (x + s, y)], fill=col, width=w, joint="curve")


def cross(d, x, y, s, col=RED, w=11):
    d.line([(x, y), (x + s, y + s)], fill=col, width=w)
    d.line([(x + s, y), (x, y + s)], fill=col, width=w)


def triangle_up(d, cx, cy, w, fill, outline):
    pts = [(cx - w / 2, cy + w * 0.4), (cx + w / 2, cy + w * 0.4), (cx, cy - w * 0.55)]
    d.polygon(pts, fill=fill, outline=outline)
    d.line(pts + [pts[0]], fill=outline, width=4)
    return [cx - w / 2, cy - w * 0.55, cx + w / 2, cy + w * 0.4]


# ----------------------------------------------------------------------------------------- page 1
def page_science(v):
    A = v == "a"
    p = Page(2200, 1500, (251, 250, 246))
    d = p.d
    p.t(100, 70, "Investigation 3: Heating Water", F("verdanab", 58))
    p.t(100, 160, "Year 9 Science  |  Lab worksheet", F("verdana", 32), (90, 90, 90))
    # table
    tx, ty, rh = 100, 300, 85
    cw = [330, 430]
    A_vals = [20, 30, 40, 45, 50, None, 65]
    miss = 55 if A else 60
    hdr = ["Time (min)", "Sample A (°C)"]
    x = tx
    d.rectangle([tx, ty, tx + sum(cw), ty + rh], fill=(215, 225, 240))
    for i, h in enumerate(hdr):
        p.t(x + cw[i] / 2, ty + rh / 2, h, F("verdanab", 32), anchor="mm")
        x += cw[i]
    cells = {}
    for r in range(7):
        y = ty + rh * (r + 1)
        vals = [str(r), "?" if A_vals[r] is None else str(A_vals[r])]
        x = tx
        for c in range(2):
            b = p.t(x + cw[c] / 2, y + rh / 2, vals[c], F("verdana", 36), anchor="mm")
            cells[(r, c)] = [x, y, x + cw[c], y + rh]
            x += cw[c]
    for r in range(9):
        d.line([(tx, ty + r * rh), (tx + sum(cw), ty + r * rh)], fill=INK, width=3) if r <= 8 else None
    for xx in [tx, tx + cw[0], tx + sum(cw)]:
        d.line([(xx, ty), (xx, ty + 8 * rh)], fill=INK, width=3)
    p.t(100, 1040, "Method: heat 200 mL of water on a hot plate.", F("verdana", 28), (70, 70, 70))
    p.t(100, 1090, "Record the temperature every minute.", F("verdana", 28), (70, 70, 70))
    p.t(100, 1140, "Sample B was plotted on the graph only.", F("verdana", 28), (70, 70, 70))
    # graph
    px0, px1, py0, py1 = 1250, 2090, 380, 1150
    gt = p.t(px0 + (px1 - px0) / 2, 300, "Temperature of water over time", F("verdanab", 34), anchor="mm")
    for g in range(0, 90, 10):
        y = py1 - g / 80 * (py1 - py0)
        d.line([(px0, y), (px1, y)], fill=(205, 205, 205), width=2)
        p.t(px0 - 18, y, str(g), F("verdana", 26), anchor="rm")
    for m in range(7):
        x = px0 + m / 6 * (px1 - px0)
        d.line([(x, py0), (x, py1)], fill=(225, 225, 225), width=2)
        p.t(x, py1 + 18, str(m), F("verdana", 26), anchor="mt")
    d.line([(px0, py0), (px0, py1), (px1, py1)], fill=INK, width=5)
    xl = p.t((px0 + px1) / 2, py1 + 85, "Time (min)", F("verdanab", 30), anchor="mm")
    tmp = Image.new("RGBA", (360, 50), (0, 0, 0, 0))
    ImageDraw.Draw(tmp).text((180, 25), "Temperature (°C)", font=F("verdanab", 30), fill=INK, anchor="mm")
    rot = tmp.rotate(90, expand=True)
    p.img.paste(rot, (px0 - 125, int((py0 + py1) / 2 - 180)), rot)
    yl = [px0 - 125, int((py0 + py1) / 2 - 180), px0 - 75, int((py0 + py1) / 2 + 180)]

    def P(m, val):
        return (px0 + m / 6 * (px1 - px0), py1 - val / 80 * (py1 - py0))

    Avals = [20, 30, 40, 45, 50, miss, 65]
    Bvals = [25, 45, 60, 55, 50, 45, 40] if A else [25, 30, 35, 45, 55, 60, 50]
    for vals, col in ((Avals, BLUE), (Bvals, RED)):
        pts = [P(m, val) for m, val in enumerate(vals)]
        d.line(pts, fill=col, width=6, joint="curve")
        for (x, y) in pts:
            d.ellipse([x - 12, y - 12, x + 12, y + 12], fill=col, outline="white", width=2)
    ring_m = 1 if A else 3
    rx, ry = P(ring_m, Avals[ring_m])
    d.ellipse([rx - 30, ry - 30, rx + 30, ry + 30], outline=(0, 170, 70), width=6)
    # legend
    ly = 1380
    d.line([(1250, ly), (1310, ly)], fill=BLUE, width=7)
    p.t(1325, ly, "Sample A", F("verdana", 28), anchor="lm")
    d.line([(1530, ly), (1590, ly)], fill=RED, width=7)
    p.t(1605, ly, "Sample B", F("verdana", 28), anchor="lm")
    d.ellipse([1790, ly - 20, 1830, ly + 20], outline=(0, 170, 70), width=6)
    p.t(1845, ly, "= repeat reading", F("verdana", 28), anchor="lm")
    # questions
    p.q("text", "What is the temperature of Sample A at 3 minutes?", "45", ["45 °C", "45 degrees", "45 C"], [cells[(3, 1)]])
    p.q("text", "What is plotted on the y-axis of the graph?", "Temperature", ["temperature in °C", "temperature (°C)", "temperature in degrees Celsius"], [yl])
    p.q("text", "How many minutes does the first column of the table go up to?", "6", ["6 minutes", "6 min", "six"], [U(cells[(6, 0)], cells[(0, 0)], pad=2)])
    p.q("mixed", "What is the missing value in the table?", str(miss), [f"{miss} °C", f"{miss} degrees", f"{miss} C"],
        [cells[(5, 1)], U([*P(5, miss), *P(5, miss)], pad=40)])
    ax, ay = P(2, 40)
    bx, by = P(2, Bvals[2])
    p.q("visual", "At minute 2, which line is higher on the graph, the blue line or the red line?", "red" if A else "blue",
        ["red line" if A else "blue line", "the red one" if A else "the blue one"], [U([ax, ay, ax, ay], [bx, by, bx, by], pad=40)])
    pk = 2 if A else 5
    qx, qy = P(pk, Bvals[pk])
    p.q("visual", "At which minute does the red line reach its highest point?", str(pk), [f"minute {pk}", f"{pk} minutes", f"{pk} min"],
        [[qx - 45, qy - 45, qx + 45, qy + 45]])
    p.q("visual", "Which minute has a green ring around its point on the graph?", str(ring_m), [f"minute {ring_m}", f"{ring_m} minutes", f"{ring_m} min"],
        [[rx - 40, ry - 40, rx + 40, ry + 40]])
    p.q("unanswerable", "What was the room temperature during the experiment?", None)
    return p


# ----------------------------------------------------------------------------------------- page 2
def page_map(v):
    A = v == "a"
    p = Page(1700, 2200, (250, 248, 240))
    d = p.d
    tb = p.t(100, 70, "Geography Quiz 4: The Island of Valoria", F("georgiab", 56))
    p.t(100, 170, "Study the map carefully, then answer the questions below.", F("georgia", 34), (80, 80, 80))
    d.rectangle([100, 260, 1600, 1260], fill=(196, 224, 245), outline=INK, width=6)
    island = [(200, 500), (380, 340), (800, 310), (1250, 360), (1500, 520), (1540, 820), (1430, 1080), (1100, 1190),
              (700, 1170), (350, 1100), (190, 850)]
    imask = Image.new("L", (p.W, p.H), 0)
    ImageDraw.Draw(imask).polygon(island, fill=255)
    orange, lav = (250, 165, 80), (215, 190, 225)
    regions = {
        "North Vale": ([(100, 260), (1000, 260), (950, 560), (550, 600), (100, 540)], (190, 226, 170)),
        "Eastridge": ([(1000, 260), (1600, 260), (1600, 1000), (1150, 1000), (1050, 700), (950, 560)], (232, 208, 160)),
        "Central Basin": ([(550, 600), (950, 560), (1050, 700), (1150, 1000), (850, 1000), (550, 900)], (245, 232, 150)),
        "West Plains": ([(100, 540), (550, 600), (550, 900), (500, 1260), (100, 1260)], lav if A else orange),
        "South Bay": ([(550, 900), (850, 1000), (1150, 1000), (1600, 1000), (1600, 1260), (500, 1260)], orange if A else lav),
    }
    bmask = Image.new("L", (p.W, p.H), 0)
    bd = ImageDraw.Draw(bmask)
    for name, (poly, col) in regions.items():
        m = Image.new("L", (p.W, p.H), 0)
        ImageDraw.Draw(m).polygon(poly, fill=255)
        p.img.paste(col, mask=ImageChops.multiply(m, imask))
        bd.line(poly + [poly[0]], fill=255, width=5)
    p.img.paste((70, 60, 50), mask=ImageChops.multiply(bmask, imask))
    d.line(island + [island[0]], fill=(40, 40, 40), width=8, joint="curve")
    labels = {"North Vale": (690, 385), "Eastridge": (1290, 900), "Central Basin": (780, 690), "West Plains": (360, 760), "South Bay": (900, 1110)}
    lb = {}
    for n, (x, y) in labels.items():
        lb[n] = p.t(x, y, n, F("georgiab", 44), (40, 40, 40), anchor="mm")
    # mountains
    mt = [(1220, 460), (1340, 480), (1430, 640)] + ([] if A else [(1400, 780), (1320, 800)])
    mtb = [triangle_up(d, x, y, 64, (150, 105, 70), (80, 50, 30)) for x, y in mt]
    for x, y in [(800, 490), (880, 510)]:
        triangle_up(d, x, y, 64, (150, 105, 70), (80, 50, 30))
    cities = {"Port Elm": (430, 500), "Kestrel": (1230, 600), "Dunmere": (760, 840), "Harrow": (330, 960), "Saltcove": (640, 1040)}
    capital = "Kestrel" if A else "Dunmere"
    cb = {}
    for n, (x, y) in cities.items():
        if n == capital:
            star(d, x, y, 44, RED, (110, 0, 0))
            lab = p.t(x + 52, y, n, F("georgiab", 32), anchor="lm")
            cb[n] = U([x - 44, y - 44, x + 44, y + 44], lab, pad=8)
        else:
            d.ellipse([x - 13, y - 13, x + 13, y + 13], fill=(30, 30, 30))
            lab = p.t(x + 24, y, n, F("georgia", 32), anchor="lm")
            cb[n] = U([x - 13, y - 13, x + 13, y + 13], lab, pad=8)
    # compass
    cx, cy = 200, 1160
    d.ellipse([cx - 42, cy - 42, cx + 42, cy + 42], outline=INK, width=5, fill=(250, 250, 250))
    d.polygon([(cx, cy - 40), (cx - 14, cy), (cx + 14, cy)], fill=RED)
    d.polygon([(cx, cy + 40), (cx - 14, cy), (cx + 14, cy)], fill=(80, 80, 80))
    for s, (dx, dy) in {"N": (0, -68), "S": (0, 68), "E": (68, 0), "W": (-68, 0)}.items():
        p.t(cx + dx, cy + dy, s, F("georgiab", 32), anchor="mm")
    # key
    d.rectangle([100, 1300, 1600, 1470], outline=INK, width=4)
    p.t(130, 1320, "Key", F("georgiab", 34))
    star(d, 200, 1410, 36, RED, (110, 0, 0))
    k1 = p.t(250, 1410, "Capital city", F("georgia", 34), anchor="lm")
    triangle_up(d, 560, 1410, 56, (150, 105, 70), (80, 50, 30))
    p.t(610, 1410, "Mountains", F("georgia", 34), anchor="lm")
    d.ellipse([890, 1397, 916, 1423], fill=(30, 30, 30))
    p.t(930, 1410, "Town", F("georgia", 34), anchor="lm")
    sc = p.t(1100, 1410, "Scale: 1 cm = 50 km", F("georgiab", 36), anchor="lm")
    qy = 1540
    p.t(100, qy, "Questions", F("georgiab", 42))
    qs = ["1. Name the five regions of Valoria.", "2. Which region borders the sea on the south coast?",
          "3. Estimate how far Dunmere is from Saltcove.", "4. Describe the landscape of Eastridge.",
          "5. Suggest why most towns are near the coast."]
    qb = []
    for i, s in enumerate(qs):
        qb.append(p.t(100, qy + 80 + i * 75, s, F("georgia", 38)))
    p.t(100, 2060, "Answer in full sentences.", F("georgia", 32), (90, 90, 90))
    p.q("text", "What is the scale given in the key?", "1 cm = 50 km", ["1 cm to 50 km", "1cm = 50km", "50 km per cm", "1 cm represents 50 km"], [sc])
    p.q("text", "How many questions are there in the quiz?", "5", ["five", "5 questions"], [U(*qb, pad=10)])
    p.q("text", "What is the name of the island?", "Valoria", ["the Island of Valoria", "Island of Valoria"], [tb])
    capreg = "Eastridge" if A else "Central Basin"
    p.q("mixed", "In which region is the capital city?", capreg, [f"the {capreg}" if not A else "East Ridge", f"{capreg} region"], [cb[capital], lb[capreg]])
    reg_or = "South Bay" if A else "West Plains"
    p.q("mixed", "Which region is shaded orange?", reg_or, [f"the {reg_or}", f"{reg_or} region"], [lb[reg_or]])
    p.q("visual", "Which city is marked with the star on the map?", capital, [f"the star marks {capital}", f"star is at {capital}"], [cb[capital]])
    p.q("visual", "How many mountain symbols are drawn inside Eastridge?", "3" if A else "5", ["three" if A else "five", "3 mountains" if A else "5 mountains"], [U(*mtb, pad=20)])
    p.q("unanswerable", "What is the population of Valoria?", None)
    return p


# ----------------------------------------------------------------------------------------- page 3
def page_fractions(v):
    A = v == "a"
    p = Page(1700, 2200, (253, 251, 245))
    d = p.d
    tb = p.t(100, 80, "Adding and Subtracting Fractions", F("timesb", 76))
    p.t(100, 190, "Maths practice  •  Class 5B", F("times", 46), (80, 80, 80))
    p.t(100, 270, "Name:", F("times", 48))
    p.t(260, 262, "Maya", F("hand", 68), HANDINK)
    d.line([(250, 325), (620, 325)], fill=INK, width=3)
    p.t(100, 370, "Work out each answer. Write it in its simplest form.", F("times", 42), (60, 60, 60))
    probs = ["1/2 + 1/4 =", "2/3 - 1/6 =", "1/3 + 1/3 =", "3/4 - 1/2 =", "1/5 + 3/10 =", "5/6 - 1/3 =", "1/4 + 1/8 =", "7/8 - 3/4 ="]
    correct = ["3/4", "1/2", "2/3", "1/4", "1/2", "1/2", "3/8", "1/8"]
    stud = ["3/4", "1/2", "1/3" if A else "2/3", "1/4", "4/15", "1/2" if A else "2/3", "3/8", "1/4"]
    rows = {}
    for i in range(8):
        y = 520 + i * 190
        nb = p.t(120, y, f"{i + 1})", F("timesb", 64))
        pb = p.t(240, y, probs[i], F("times", 68))
        d.line([(850, y + 82), (1200, y + 82)], fill=(150, 150, 150), width=3)
        ab = p.t(880, y - 6, stud[i], F("hand", 84), HANDINK)
        ok = stud[i] == correct[i]
        mx, my = 1290, y - 5
        if ok:
            tick(d, mx, my, 85)
        else:
            cross(d, mx, my, 80)
        rows[i] = dict(prob=pb, ans=ab, mark=[mx - 8, my - 8, mx + 95, my + 95], row=[100, y - 15, 1400, y + 105])
    sb = p.t(100, 2080, "Score:  ______ / 8", F("times", 52))
    crosses = [i + 1 for i in range(8) if stud[i] != correct[i]]
    cs = ", ".join(map(str, crosses[:-1])) + " and " + str(crosses[-1])
    acc = [", ".join(map(str, crosses)), " ".join(map(str, crosses)), cs, "questions " + cs, "numbers " + cs]
    p.q("text", "What is the topic of this worksheet?", "Adding and subtracting fractions", ["fractions", "adding and subtracting fractions"], [tb])
    p.q("text", "What is problem 5 on the worksheet?", "1/5 + 3/10", ["1/5 + 3/10 =", "1/5 plus 3/10", "one fifth plus three tenths"], [rows[4]["prob"]])
    p.q("text", "Which class is this worksheet for?", "5B", ["class 5B", "Class 5B"], [[100, 190, 700, 250]])
    p.q("mixed", "Is the student's answer to question 3 correct?", "No" if A else "Yes",
        ["incorrect", "wrong", "not correct", "it is wrong"] if A else ["yes", "right", "yes it is"], [U(rows[2]["prob"], rows[2]["ans"], rows[2]["mark"])])
    p.q("mixed", "Did the student get question 6 right?", "Yes" if A else "No",
        ["yes", "right", "yes they did"] if A else ["incorrect", "wrong", "not right", "no they did not"], [U(rows[5]["prob"], rows[5]["ans"], rows[5]["mark"])])
    p.q("visual", "Which questions did the teacher mark with a cross?", cs, acc, [U(*[rows[i - 1]["mark"] for i in crosses], pad=10)])
    p.q("visual", "Is there a tick or a cross next to question 6?", "tick" if A else "cross", ["a tick" if A else "a cross", "check mark" if A else "an x", "green tick" if A else "red cross"], [rows[5]["mark"]])
    p.q("visual", "What did the student write as the answer to question 3?", stud[2], ["one third" if A else "two thirds", stud[2], "the student wrote " + stud[2]], [rows[2]["ans"]])
    p.q("unanswerable", "What score did the student get?", None)
    assert len(p.qas) == 9
    p.qas.pop(2)  # drop the class question (kept page at 8 items)
    return p


# ----------------------------------------------------------------------------------------- page 4
def page_vocab(v):
    A = v == "a"
    p = Page(2200, 1500, (247, 250, 252))
    d = p.d
    tb = p.t(100, 70, "Earth Science Vocabulary", F("verdanab", 60))
    p.t(100, 160, "Draw a line from each word to its meaning.", F("verdana", 36), (70, 70, 70))
    words = ["Erosion", "Volcano", "Delta", "Glacier", "Fossil", "Canyon"]
    defs = {"A": "Slow river of ice", "B": "Remains of ancient life", "C": "Deep valley with steep sides",
            "D": "Wearing away of rock", "E": "Land formed at a river mouth", "F": "Opening that erupts lava"}
    right = ["A", "B", "C", "D", "E", "F"]
    rx0, rx1, lx0, lx1 = 1230, 2080, 100, 700
    ys = [350 + i * 170 for i in range(6)]
    wb, db = {}, {}
    for i, w in enumerate(words):
        d.rounded_rectangle([lx0, ys[i] - 55, lx1, ys[i] + 55], radius=14, fill=(255, 255, 255), outline=INK, width=4)
        wb[w] = p.t(lx0 + 30, ys[i], f"{i + 1}. {w}", F("verdanab", 44), anchor="lm")
        wb[w] = [lx0, ys[i] - 55, lx1, ys[i] + 55]
    for i, L in enumerate(right):
        d.rounded_rectangle([rx0, ys[i] - 55, rx1, ys[i] + 55], radius=14, fill=(255, 255, 255), outline=INK, width=4)
        db[L] = [rx0, ys[i] - 55, rx1, ys[i] + 55]
        p.t(rx0 + 25, ys[i], f"{L}.  {defs[L]}", F("verdana", 34), anchor="lm")
    if A:
        match = {"Erosion": "D", "Volcano": "F", "Delta": "E", "Glacier": "A", "Fossil": "B", "Canyon": None}
    else:
        match = {"Erosion": "E", "Volcano": None, "Delta": "D", "Glacier": "A", "Fossil": "B", "Canyon": "C"}
    cols = [(220, 40, 40), (30, 90, 220), (20, 150, 70), (150, 40, 190), (230, 130, 0), (0, 150, 160)]
    lb = {}
    for i, w in enumerate(words):
        L = match[w]
        if L is None:
            continue
        j = right.index(L)
        a, b = (lx1 + 6, ys[i]), (rx0 - 6, ys[j])
        d.line([a, b], fill=cols[i], width=6)
        d.ellipse([a[0] - 9, a[1] - 9, a[0] + 9, a[1] + 9], fill=cols[i])
        d.ellipse([b[0] - 9, b[1] - 9, b[0] + 9, b[1] + 9], fill=cols[i])
        lb[w] = [a[0] - 10, min(a[1], b[1]) - 10, b[0] + 10, max(a[1], b[1]) + 10]
    p.t(100, 1400, "Total: 6 words", F("verdana", 30), (110, 110, 110))
    wcol = [w for w in words if match[w] is None][0]
    inv = {L: w for w, L in match.items() if L}
    q_e = "Delta" if A else "Erosion"
    ero = match["Erosion"]
    p.q("text", "What is the title of this exercise?", "Earth Science Vocabulary", ["Earth Science Vocabulary exercise"], [tb])
    p.q("text", "What is the definition labelled D?", "Wearing away of rock", ["wearing away of rock"], [db["D"]])
    p.q("text", "How many words are in the left column?", "6", ["six", "6 words"], [U(*wb.values(), pad=6)])
    p.q("mixed", "Is the student's match for 'Delta' correct?", "Yes" if A else "No",
        ["yes", "right", "correct"] if A else ["incorrect", "wrong", "not correct", "no it is wrong"],
        [U(wb["Delta"], db[match["Delta"]], lb["Delta"])])
    p.q("visual", "Which letter is the word 'Erosion' connected to by a line?", ero, [f"definition {ero}", f"letter {ero}", defs[ero]], [U(wb["Erosion"], db[ero], lb["Erosion"])])
    p.q("visual", "Which word is connected by a line to definition E?", q_e, [f"the word {q_e}", f"{q_e.lower()}"], [U(wb[q_e], db["E"], lb[q_e])])
    p.q("visual", "Which word has no line drawn from it?", wcol, [f"the word {wcol}", wcol.lower(), f"{wcol} has no line"], [wb[wcol]])
    p.q("unanswerable", "What mark did the teacher give for this exercise?", None)
    return p


# ----------------------------------------------------------------------------------------- page 5
def page_timetable(v):
    A = v == "a"
    p = Page(2000, 1500, (250, 249, 245))
    d = p.d
    tb = p.t(100, 60, "Class 7B Weekly Timetable", F("tahomab", 62))
    p.t(100, 150, "Autumn term", F("tahoma", 34), (90, 90, 90))
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    times = ["8:30", "9:30", "10:30", "11:30", "12:30", "1:30", "2:30"]
    grid = {
        0: ["Maths", "English", "Science", "Maths", "Art"],
        1: ["English", "Maths", "Maths", "French", "Science"],
        2: ["Science", "History", "English", "Science", "Maths"],
        3: ["History", "Art", "PE", "English", "French"],
        5: ["PE", "Science", "French", "Geography", "English"],
        6: ["Geography", "Music", "History", "Art", "PE"],
    }
    x0, y0, tw, cw, hh, rh = 100, 230, 200, 310, 90, 125
    grey_col = 4 if A else 0
    yel = (2, 2) if A else (3, 2)  # (day, row)
    star_cell = (1, 3) if A else (4, 6)
    d.rectangle([x0, y0, x0 + tw + 5 * cw, y0 + hh], fill=(55, 85, 135))
    p.t(x0 + tw / 2, y0 + hh / 2, "Time", F("tahomab", 34), (255, 255, 255), anchor="mm")
    dayb = {}
    for c, dn in enumerate(days):
        dayb[c] = [x0 + tw + c * cw, y0, x0 + tw + (c + 1) * cw, y0 + hh]
        p.t(x0 + tw + c * cw + cw / 2, y0 + hh / 2, dn, F("tahomab", 34), (255, 255, 255), anchor="mm")
    cell = {}
    for r in range(7):
        y = y0 + hh + r * rh
        d.rectangle([x0, y, x0 + tw, y + rh], fill=(228, 233, 243))
        p.t(x0 + tw / 2, y + rh / 2, times[r], F("tahomab", 36), anchor="mm")
        if r == 4:
            d.rectangle([x0 + tw, y, x0 + tw + 5 * cw, y + rh], fill=(215, 235, 215))
            p.t(x0 + tw + 2.5 * cw, y + rh / 2, "LUNCH", F("tahomab", 40), (60, 100, 60), anchor="mm")
            continue
        for c in range(5):
            bx = [x0 + tw + c * cw, y, x0 + tw + (c + 1) * cw, y + rh]
            fill = (255, 255, 255)
            if c == grey_col:
                fill = (185, 185, 185)
            if (c, r) == yel:
                fill = (255, 232, 80)
            d.rectangle(bx, fill=fill)
            p.t((bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2, grid[r][c], F("tahoma", 38), anchor="mm")
            cell[(c, r)] = bx
    for r in range(9):
        y = y0 + (0 if r == 0 else hh + (r - 1) * rh)
        d.line([(x0, y), (x0 + tw + 5 * cw, y)], fill=INK, width=3)
    for c in range(7):
        x = x0 if c == 0 else x0 + tw + (c - 1) * cw
        d.line([(x, y0), (x, y0 + hh + 7 * rh)], fill=INK, width=3)
    sb = cell[star_cell]
    star(d, sb[2] - 38, sb[1] + 38, 28, (240, 110, 0), (120, 50, 0))
    ly = 1330
    d.rectangle([100, ly - 25, 150, ly + 25], fill=(255, 232, 80), outline=INK, width=3)
    p.t(165, ly, "= exam", F("tahoma", 32), anchor="lm")
    d.rectangle([420, ly - 25, 470, ly + 25], fill=(185, 185, 185), outline=INK, width=3)
    p.t(485, ly, "= teacher absent (cover lessons)", F("tahoma", 32), anchor="lm")
    star(d, 1250, ly, 30, (240, 110, 0), (120, 50, 0))
    p.t(1295, ly, "= homework due", F("tahoma", 32), anchor="lm")
    ex_sub = grid[yel[1]][yel[0]]
    ex_day = days[yel[0]]
    st_sub = grid[star_cell[1]][star_cell[0]]
    p.q("text", "What subject is on Tuesday at 9:30?", "Maths", ["maths", "math", "mathematics"], [cell[(1, 1)]])
    p.q("text", "What time does lunch start?", "12:30", ["12.30", "12:30 pm", "half past twelve"], [[x0, y0 + hh + 4 * rh, x0 + tw, y0 + hh + 5 * rh]])
    p.q("text", "What is on Thursday at 1:30?", "Geography", ["geography lesson"], [cell[(3, 5)]])
    p.q("mixed", "Which subject is highlighted in yellow?", ex_sub, [f"{ex_sub.lower()}", f"the {ex_sub.lower()} lesson"], [cell[yel]])
    p.q("mixed", "On which day is the exam?", ex_day, [ex_day[:3], ex_day.lower(), f"on {ex_day}"], [cell[yel], dayb[yel[0]]])
    gcol = days[grey_col]
    p.q("visual", "Which day's column is shaded grey?", gcol, [gcol[:3], gcol.lower(), f"{gcol} column"], [U(dayb[grey_col], cell[(grey_col, 6)], pad=4)])
    p.q("visual", "Which subject has a star sticker in its cell?", st_sub, [st_sub.lower(), f"the {st_sub.lower()} lesson"], [sb])
    p.q("unanswerable", "Who is the form teacher of class 7B?", None)
    return p


# ----------------------------------------------------------------------------------------- page 6
def page_geometry(v):
    A = v == "a"
    p = Page(1800, 2000, (252, 252, 248))
    d = p.d
    tb = p.t(100, 70, "Angles and Triangles", F("trebuchetb", 64))
    unit = p.t(100, 170, "All lengths are in cm. Figures are not drawn to scale.", F("trebuchet", 36), (80, 80, 80))
    # figure 1: 5-12-13 triangle
    s = 48
    P1 = (260, 850)
    P2 = (P1[0] + 12 * s, P1[1])
    P3 = (P1[0], P1[1] - 5 * s)
    d.polygon([P1, P2, P3], fill=(236, 243, 252))
    d.line([P1, P2, P3, P1], fill=INK, width=6, joint="curve")
    d.line([(P1[0] + 45, P1[1]), (P1[0] + 45, P1[1] - 45), (P1[0], P1[1] - 45)], fill=INK, width=5)
    lab = {"a": {"P1": "B", "P2": "A", "P3": "C"}, "b": {"P1": "C", "P2": "A", "P3": "B"}}[v]
    pts = {"P1": P1, "P2": P2, "P3": P3}
    off = {"P1": (-40, 30), "P2": (40, 30), "P3": (-40, -30)}
    vb = {}
    for k, (x, y) in pts.items():
        vb[lab[k]] = p.t(x + off[k][0], y + off[k][1], lab[k], F("trebuchetb", 50), anchor="mm")
    p.t((P1[0] + P2[0]) / 2, P1[1] + 55, "12 cm", F("trebuchet", 38), anchor="mm")
    p.t(P1[0] - 70, (P1[1] + P3[1]) / 2, "5 cm", F("trebuchet", 38), anchor="mm")
    p.t((P2[0] + P3[0]) / 2 + 70, (P2[1] + P3[1]) / 2 - 35, "13 cm", F("trebuchet", 38), anchor="mm")
    dotv = "A" if A else "B"
    dp = P2 if A else P3
    d.ellipse([dp[0] - 20, dp[1] - 20, dp[0] + 20, dp[1] + 20], fill=RED)
    p.t(P1[0] + 150, P1[1] + 160, "Figure 1", F("trebuchetb", 38), (90, 90, 90), anchor="mm")
    p.t(1100, 400, "Red dot = start vertex", F("trebuchet", 34), (90, 90, 90))
    d.ellipse([1040, 390, 1080, 430], fill=RED)
    # figure 2
    cx, cy, r = 700, 1380, 150
    th = 32.5
    sectors = {"right": (-th, th), "top": (-180 + th, -th), "left": (180 - th, 180 + th), "bottom": (th, 180 - th)}
    shaded = "left" if A else "top"
    s0, s1 = sectors[shaded]
    d.pieslice([cx - r, cy - r, cx + r, cy + r], s0, s1, fill=(255, 195, 195))
    d.arc([cx - r, cy - r, cx + r, cy + r], s0, s1, fill=RED, width=9)
    L = 340
    for sg in (+1, -1):
        a = math.radians(sg * th)
        d.line([(cx - L * math.cos(a), cy + L * math.sin(a)), (cx + L * math.cos(a), cy - L * math.sin(a))], fill=INK, width=6)
    ang = p.t(cx + 215, cy, "65°", F("trebuchetb", 54), anchor="mm")
    p.t(cx, cy + 330, "Figure 2", F("trebuchetb", 38), (90, 90, 90), anchor="mm")
    p.t(1130, 1260, "Both lines are straight.", F("trebuchet", 34), (90, 90, 90))
    qy = 1790
    qs = ["1. Find the length of side AB in Figure 1.", "2. Find the size of the shaded angle in Figure 2.",
          "3. Work out the area of the triangle in Figure 1."]
    for i, q in enumerate(qs):
        p.t(100, qy + i * 62, q, F("trebuchet", 38))
    figb = U([P1[0] - 90, P3[1] - 40, P2[0] + 90, P1[1] + 110], pad=0)
    ab = "12 cm" if A else "13 cm"
    rv = "B" if A else "C"
    shbox = [cx - r - 20, cy - r - 20, cx + r + 20, cy + r + 20]
    shsize = "65" if A else "115"
    abox = U(vb["A"], vb["B"] if A else vb["B"], pad=30)
    p.q("text", "What is the heading of this worksheet?", "Angles and Triangles", ["angles and triangles"], [tb])
    p.q("text", "What unit are the lengths given in?", "cm", ["centimetres", "centimeters", "centimetre"], [unit])
    p.q("mixed", "How long is side AB?", ab, [ab.replace(" cm", ""), ab.replace("cm", "centimetres")], [figb])
    p.q("mixed", "What is the size of the shaded angle in Figure 2?", shsize + "°", [shsize + " degrees", shsize, shsize + " deg"],
        [U(shbox, ang, pad=20)])
    p.q("visual", "At which vertex is the right-angle square drawn?", rv, [f"vertex {rv}", f"point {rv}", f"at {rv}"],
        [U([P1[0] - 20, P1[1] - 60, P1[0] + 60, P1[1] + 20], vb[rv], pad=10)])
    p.q("visual", "Which vertex has the red dot on it?", dotv, [f"vertex {dotv}", f"point {dotv}", f"at {dotv}"], [U([dp[0] - 25, dp[1] - 25, dp[0] + 25, dp[1] + 25], vb[dotv], pad=10)])
    p.q("visual", "Which part of Figure 2 is shaded: top, bottom, left or right?", shaded, [f"the {shaded} angle", f"{shaded} side", f"the {shaded} one"], [shbox])
    p.q("unanswerable", "What is the total number of marks available for this sheet?", None)
    return p


PAGES = [page_science, page_map, page_fractions, page_vocab, page_timetable, page_geometry]


def main():
    (OUT / "images").mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)
    items = []
    for n, fn in enumerate(PAGES, 1):
        for v in "ab":
            p = fn(v)
            iid = f"hw2-{n:03d}{v}"
            # deterministic faint paper grain
            px = p.img.load()
            for _ in range(2500):
                x, y = rng.randrange(p.W), rng.randrange(p.H)
                c = px[x, y]
                px[x, y] = tuple(max(0, k - rng.randrange(6)) for k in c)
            p.img.save(OUT / "images" / f"{iid}.png")
            assert len(p.qas) == 8, (iid, len(p.qas))
            for i, qa in enumerate(p.qas, 1):
                boxes = [[round(max(0.0, min(1.0, v_)), 4) for v_ in (b[0] / p.W, b[1] / p.H, b[2] / p.W, b[3] / p.H)] for b in qa["boxes"]]
                ans = qa["answer"]
                items.append(dict(
                    question_id=f"{iid}-q{i}", image_id=iid, image_path=f"images/{iid}.png", question=qa["question"],
                    answer=ans, answerable=ans is not None,
                    evidence_type={"unanswerable": "text"}.get(qa["kind"], qa["kind"]) if ans is not None else "text",
                    evidence_boxes=boxes if ans is not None else [],
                    accepted_answers=[a for a in dict.fromkeys(qa["acc"]) if a != ans], pair_id=f"hw2-{n:03d}",
                    source="synthetic", notes=None))
    with open(OUT / "items.jsonl", "w") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    print(f"wrote {len(items)} items, {len(PAGES) * 2} images to {OUT}")


if __name__ == "__main__":
    main()
