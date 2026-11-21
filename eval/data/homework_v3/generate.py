"""Synthetic held-out set "homework_v3": 6 page kinds x (a, b) variants x 8 questions = 96 items.

Run:  python3 -m eval.data.homework_v3.generate     (env HW3_SEED=50505, HW3_OUT=<this dir>)
Each pair (a/b) shares all printed content and differs in 1-2 drawn details that change visual answers.
Evidence boxes are recorded at draw time (normalised x0,y0,x1,y1).
"""
from __future__ import annotations

import calendar
import json
import math
import os
import random

from PIL import Image, ImageDraw, ImageFont

FD = "/System/Library/Fonts/Supplemental/"
_FC: dict = {}


def ft(fam, bold, size):
    name = fam + (" Bold" if bold else "") + ".ttf"
    k = (name, size)
    if k not in _FC:
        _FC[k] = ImageFont.truetype(FD + name, size)
    return _FC[k]


NUMW = {0: "zero", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight",
        9: "nine", 10: "ten", 11: "eleven", 12: "twelve", 15: "fifteen", 20: "twenty", 30: "thirty"}


def nums(n, *units):
    out = [str(n)]
    if n in NUMW:
        out.append(NUMW[n])
    for u in units:
        out.append(f"{n} {u}")
        if n in NUMW:
            out.append(f"{NUMW[n]} {u}")
    return out


def ordinal(n):
    suf = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


def U(*bs):
    return (min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs))


class Canvas:
    def __init__(self, w, h, bg):
        self.w, self.h = w, h
        self.im = Image.new("RGB", (w, h), bg)
        self.d = ImageDraw.Draw(self.im)

    def n(self, b):
        x0, y0, x1, y1 = b
        cl = lambda v: round(min(1.0, max(0.0, v)), 4)
        return [cl(x0 / self.w), cl(y0 / self.h), cl(x1 / self.w), cl(y1 / self.h)]

    def text(self, xy, s, f, fill, anchor="la", pad=6):
        bb = self.d.textbbox(xy, s, font=f, anchor=anchor)
        self.d.text(xy, s, font=f, fill=fill, anchor=anchor)
        return (bb[0] - pad, bb[1] - pad, bb[2] + pad, bb[3] + pad)

    def wrap(self, s, f, width):
        lines, cur = [], ""
        for w in s.split():
            t = (cur + " " + w).strip()
            if self.d.textlength(t, font=f) <= width:
                cur = t
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
        return lines

    def para(self, x, y, width, s, f, fill, lh):
        """Draw wrapped paragraph; returns (bbox, y_after)."""
        bbs = []
        for ln in self.wrap(s, f, width):
            bbs.append(self.text((x, y), ln, f, fill))
            y += lh
        return U(*bbs), y

    def arrow(self, p0, p1, col, w=7, head=38):
        self.d.line([p0, p1], fill=col, width=w)
        a = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
        pts = [p1, (p1[0] - head * math.cos(a - 0.4), p1[1] - head * math.sin(a - 0.4)),
               (p1[0] - head * math.cos(a + 0.4), p1[1] - head * math.sin(a + 0.4))]
        self.d.polygon(pts, fill=col)


def Q(et, q, ans, acc, boxes):
    return dict(et=et, q=q, ans=ans, acc=acc, boxes=boxes)


FAMS = ["Georgia", "Arial", "Times New Roman", "Trebuchet MS", "Verdana", "Tahoma"]
INK = (25, 25, 35)


# ---------------------------------------------------------------- page 1: recipe card + measuring jug
def p1_params(rng):
    return dict(fam=rng.choice(FAMS[:4] + ["Comic Sans MS"]), bg=rng.choice([(247, 238, 214), (240, 244, 230), (250, 240, 236)]),
                accent=rng.choice([(150, 60, 40), (40, 100, 70), (60, 70, 140)]),
                eggs=rng.choice([2, 3, 4]), temp=rng.choice([160, 180, 200]), rest=rng.choice([15, 20, 30]),
                name=rng.choice(["Nana Rosa's", "Uncle Theo's", "Grandma June's"]))


def p1(P, v):
    W, H = 2100, 1500
    c = Canvas(W, H, P["bg"])
    d, fam, ac = c.d, P["fam"], P["accent"]
    d.rounded_rectangle([40, 40, W - 40, H - 40], radius=30, outline=ac, width=8)
    c.text((100, 70), f"{P['name']} Pancakes", ft(fam, True, 80), ac)
    c.text((100, 180), "Serves 4   |   Makes 8 pancakes", ft(fam, False, 38), INK)
    c.text((100, 260), "Ingredients", ft(fam, True, 52), ac)
    f = ft(fam, False, 38)
    ing = ["200 g plain flour", f"{P['eggs']} eggs", "300 ml milk", "1 tbsp sugar", "30 g butter, melted", "a pinch of salt"]
    y, ib = 335, []
    for s in ing:
        ib.append(c.text((120, y), "-  " + s, f, INK))
        y += 54
    c.text((100, y + 20), "Method", ft(fam, True, 52), ac)
    y += 100
    steps = ["Sift the flour and salt into a large bowl and make a well in the centre.",
             "Whisk the eggs with the milk, then pour into the well a little at a time.",
             f"Leave the batter to rest for {P['rest']} minutes.",
             f"Preheat the oven to {P['temp']}°C and keep the cooked pancakes warm.",
             "Fry each pancake in butter for about 2 minutes on each side."]
    sb = []
    for i, s in enumerate(steps, 1):
        bb, y = c.para(120, y, 1000, f"{i}.  {s}", ft(fam, False, 36), INK, 48)
        sb.append(bb)
        y += 14
    # jug
    jl, jr, y0, ytop = 1400, 1720, 1250, 440
    ypm = (y0 - 480) / 500.0
    lvl = 400 if v == "a" else 250
    yl = y0 - lvl * ypm
    d.polygon([(jl, ytop), (jl - 40, ytop - 10), (jl, ytop + 25)], fill=ac)  # spout
    d.arc([jr - 20, 600, jr + 130, 950], -90, 90, fill=ac, width=18)
    d.rectangle([jl + 3, yl, jr - 3, y0 - 3], fill=(120, 185, 235))
    d.line([(jl + 3, yl), (jr - 3, yl)], fill=(20, 80, 150), width=6)
    d.line([(jl, ytop), (jl, y0), (jr, y0), (jr, ytop)], fill=(40, 40, 50), width=8)
    d.line([(jl, ytop), (jr, ytop)], fill=(40, 40, 50), width=4)
    for ml in range(50, 501, 50):
        yy = y0 - ml * ypm
        L = 70 if ml % 100 == 0 else 38
        d.line([(jl, yy), (jl + L, yy)], fill=(20, 20, 30), width=4)
        if ml % 100 == 0:
            c.text((jl - 18, yy), str(ml), ft("Arial", True, 34), (20, 20, 30), anchor="rm")
    c.text((jl - 18, ytop - 55), "ml", ft("Arial", True, 34), ac, anchor="rm")
    c.text(((jl + jr) // 2, y0 + 30), "Measuring jug", ft(fam, False, 38), INK, anchor="ma")
    band = (jl - 110, max(ytop, yl - 90), jr + 20, min(y0 + 5, yl + 90))
    cap = lambda n: [f"{n} ml", f"{n}ml", str(n), *nums(n, "millilitres")[1:]]
    diff = 100 if v == "a" else 50
    qs = [
        Q("text", "How many eggs does the recipe need?", str(P["eggs"]), nums(P["eggs"], "eggs"), [ib[1]]),
        Q("text", "At what oven temperature should the pancakes be kept warm?", f"{P['temp']}°C",
          [str(P["temp"]), f"{P['temp']} C", f"{P['temp']} degrees", f"{P['temp']} degrees C", f"{P['temp']} degrees Celsius"], [sb[3]]),
        Q("text", "How long should the batter rest?", f"{P['rest']} minutes", nums(P["rest"], "minutes", "min", "mins"), [sb[2]]),
        Q("mixed", "Is there enough liquid in the jug for the amount of milk the recipe needs?",
          "Yes" if v == "a" else "No",
          ["yes", "enough", "yes there is"] if v == "a" else ["no", "not enough", "no there is not", "insufficient"], [ib[2], band]),
        Q("mixed", "By how many ml does the amount in the jug differ from the milk amount in the recipe?", f"{diff} ml",
          cap(diff) + [f"{diff} millilitres"], [ib[2], band]),
        Q("visual", "What volume does the measuring jug show?", f"{lvl} ml", cap(lvl), [band]),
        Q("visual", "What colour is the liquid in the jug?", "blue", ["light blue", "pale blue"], [band]),
        Q("text_absent", "How many calories are in one pancake?", None, [], []),
    ]
    return c, qs


# ---------------------------------------------------------------- page 2: circuit worksheet
def p2_params(rng):
    return dict(fam=rng.choice(FAMS), bg=rng.choice([(255, 255, 255), (250, 252, 255), (255, 253, 245)]),
                V=rng.choice(["9", "12"]), r1=rng.choice(["4.5", "6"]), r2=rng.choice(["3", "1.5"]),
                m2=rng.choice([3, 4, 5]), ink=rng.choice([(20, 20, 30), (30, 30, 80)]))


def hsw(d, x0, x1, y, closed, col=(10, 10, 10)):
    d.line([(x0, y), (x1, y)], fill=col, width=1)
    for x in (x0, x1):
        d.ellipse([x - 10, y - 10, x + 10, y + 10], fill=col)
    d.line([(x0, y), (x1, y)] if closed else [(x0, y), (x1 - 30, y - 75)], fill=col, width=7)


def vsw(d, x, y0, y1, closed, col=(10, 10, 10)):
    for y in (y0, y1):
        d.ellipse([x - 10, y - 10, x + 10, y + 10], fill=col)
    d.line([(x, y0), (x, y1)] if closed else [(x, y0), (x + 80, y1 - 25)], fill=col, width=7)


def p2(P, v):
    W, H = 1500, 2100
    c = Canvas(W, H, P["bg"])
    d, fam, ink = c.d, P["fam"], P["ink"]
    c.text((80, 50), "Physics Worksheet 7: Electric Circuits", ft(fam, True, 62), ink)
    c.text((80, 140), "Name: ______________________    Class: ________", ft(fam, False, 36), ink)
    k = (10, 10, 10)
    top, bot, xl, x1, x2 = 340, 890, 200, 700, 1150
    states = dict(S1=True, S2=True, S3=False) if v == "a" else dict(S1=True, S2=False, S3=True)
    W_ = 7
    d.line([(xl, top), (380, top)], fill=k, width=W_)
    d.line([(560, top), (x2, top)], fill=k, width=W_)
    d.line([(xl, top), (xl, 540)], fill=k, width=W_)
    d.line([(xl, 645), (xl, bot), (x2, bot)], fill=k, width=W_)
    for yy, ln, th in ((540, 100, 7), (575, 55, 16), (610, 100, 7), (645, 55, 16)):
        d.line([(xl - ln // 2, yy), (xl + ln // 2, yy)], fill=k, width=th)
    c.text((xl + 80, 595), "Battery", ft(fam, True, 38), ink, anchor="lm")
    c.text((xl - 70, 520), "+", ft("Arial", True, 52), ink, anchor="mm")
    hsw(d, 380, 560, top, states["S1"])
    c.text((470, 262), "S1", ft(fam, True, 42), ink, anchor="mm")
    sbox = {"S1": (360, 215, 590, 380)}
    for x, nm, lamp, lx in ((x1, "S2", "L1", x1), (x2, "S3", "L2", x2)):
        d.line([(x, top), (x, 430)], fill=k, width=W_)
        vsw(d, x, 430, 570, states[nm])
        d.line([(x, 570), (x, 640)], fill=k, width=W_)
        d.ellipse([x - 62, 640, x + 62, 764], outline=k, width=6)
        d.line([(x - 44, 658), (x + 44, 746)], fill=k, width=5)
        d.line([(x + 44, 658), (x - 44, 746)], fill=k, width=5)
        d.line([(x, 764), (x, bot)], fill=k, width=W_)
        d.ellipse([x - 9, top - 9, x + 9, top + 9], fill=k)
        d.ellipse([x - 9, bot - 9, x + 9, bot + 9], fill=k)
        c.text((x - 40, 500), nm, ft(fam, True, 42), ink, anchor="rm")
        c.text((x + 90, 702), lamp, ft(fam, True, 42), ink, anchor="lm")
        sbox[nm] = (x - 140, 405, x + 115, 590)
    circ = (80, 215, 1300, 930)
    y = 1000
    c.text((80, y), "Information", ft(fam, True, 48), ink)
    y += 75
    info = [f"The battery supplies {P['V']} V.", f"Lamp L1 is rated {P['r1']} V and lamp L2 is rated {P['r2']} V.",
            "The lamps are connected in parallel. Switch S1 is in the main wire next to the battery.",
            "Switch S2 is in the branch with lamp L1, and switch S3 is in the branch with lamp L2."]
    ib = []
    for s in info:
        bb, y = c.para(100, y, 1300, s, ft(fam, False, 38), ink, 54)
        ib.append(bb)
        y += 10
    y += 30
    c.text((80, y), "Questions", ft(fam, True, 48), ink)
    y += 75
    qq = ["1.  Which lamp or lamps will light up in the circuit as drawn?  [2 marks]",
          f"2.  Explain what happens to both lamps when S1 is opened.  [{P['m2']} marks]",
          "3.  State one advantage of connecting lamps in parallel.  [1 mark]"]
    qb = []
    for s in qq:
        bb, y = c.para(100, y, 1300, s, ft(fam, False, 38), ink, 54)
        qb.append(bb)
        d.line([(120, y + 40), (1380, y + 40)], fill=(150, 150, 150), width=3)
        y += 100
    opn = "S3" if v == "a" else "S2"
    lit = "L1" if v == "a" else "L2"
    qs = [
        Q("text", "What voltage does the battery supply?", f"{P['V']} V", [P["V"], f"{P['V']}V", f"{P['V']} volts"], [ib[0]]),
        Q("text", "What is the voltage rating of lamp L2?", f"{P['r2']} V", [P["r2"], f"{P['r2']}V", f"{P['r2']} volts"], [ib[1]]),
        Q("text", "How many marks is question 2 worth?", str(P["m2"]), nums(P["m2"], "marks"), [qb[1]]),
        Q("mixed", "Is the switch in the branch with lamp L2 open or closed?", "open" if v == "a" else "closed",
          ["open", "it is open", "S3 is open"] if v == "a" else ["closed", "it is closed", "S3 is closed", "shut"], [ib[3], sbox["S3"]]),
        Q("mixed", f"Would the lamp rated {P['r1']} V light up in the circuit as drawn?", "Yes" if v == "a" else "No",
          ["yes", "it would light", "L1 lights"] if v == "a" else ["no", "it would not light", "it stays off", "L1 does not light"], [ib[1], ib[3], circ]),
        Q("visual", "Which switch is drawn open?", opn, [opn, f"switch {opn}", f"{opn} is open", opn.replace("S", "S ")], [sbox[opn]]),
        Q("visual", "Which lamp would light up in the circuit as drawn?", lit, [lit, f"lamp {lit}", f"bulb {lit}", f"lamp {lit[1]}"], [circ]),
        Q("text_absent", "Who is the teacher who set this worksheet?", None, [], []),
    ]
    return c, qs


# ---------------------------------------------------------------- page 3: pie chart + paragraph
PIE_NAMES = ["Football", "Swimming", "Tennis", "Cycling", "Dance"]
PIE_COLS = [((205, 40, 40), "red"), ((40, 90, 210), "blue"), ((40, 160, 70), "green"), ((245, 150, 30), "orange"), ((140, 60, 180), "purple")]


def p3_params(rng):
    return dict(fam=rng.choice(FAMS), bg=rng.choice([(250, 250, 244), (244, 248, 252), (255, 250, 242)]),
                N=rng.choice([32, 36, 40]), cls=rng.choice(["7B", "8C", "6A"]),
                month=rng.choice(["March", "May", "October", "February"]))


def p3(P, v):
    W, H = 1700, 2100
    c = Canvas(W, H, P["bg"])
    d, fam = c.d, P["fam"]
    c.text((80, 60), f"Class {P['cls']} Survey: Favourite After-School Activity", ft(fam, True, 54), INK)
    y = 190
    sents = [f"In {P['month']}, {P['N']} pupils in class {P['cls']} were asked to choose their favourite after-school activity.",
             "Each pupil chose exactly one activity.", "Cycling was added to the list for the first time this year.",
             "The pie chart below shows the results."]
    sb = []
    for s in sents:
        bb, y = c.para(100, y, 1500, s, ft(fam, False, 42), INK, 62)
        sb.append(bb)
        y += 12
    vals = [36, 24, 18, 12, 10] if v == "a" else [24, 36, 12, 18, 10]
    cx, cy, r = 570, 1380, 430
    ang, boxes = -90.0, []
    for val, (col, _) in zip(vals, PIE_COLS):
        a1 = ang + val * 3.6
        d.pieslice([cx - r, cy - r, cx + r, cy + r], ang, a1, fill=col, outline=(255, 255, 255), width=5)
        pts = [(cx, cy)] + [(cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a))) for a in [ang + (a1 - ang) * i / 20 for i in range(21)]]
        boxes.append((min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)))
        ang = a1
    pie = (cx - r, cy - r, cx + r, cy + r)
    c.text((1180, 1020), "Key", ft(fam, True, 48), INK)
    lg = []
    for i, (nm, (col, _)) in enumerate(zip(PIE_NAMES, PIE_COLS)):
        yy = 1100 + i * 100
        d.rectangle([1180, yy, 1240, yy + 60], fill=col, outline=INK, width=3)
        lb = c.text((1270, yy + 30), nm, ft(fam, False, 48), INK, anchor="lm")
        lg.append(U((1180, yy, 1240, yy + 60), lb))
    order = sorted(range(5), key=lambda i: -vals[i])
    big, sec = order[0], order[1]
    qs = [
        Q("text", "How many pupils took part in the survey?", str(P["N"]), nums(P["N"], "pupils", "students"), [sb[0]]),
        Q("text", "In which month was the survey carried out?", P["month"], [P["month"].lower()], [sb[0]]),
        Q("text", "Which activity was added to the list for the first time this year?", "Cycling", ["cycling"], [sb[2]]),
        Q("mixed", "Is the slice for the activity that was new this year bigger or smaller than the Tennis slice?",
          "smaller" if v == "a" else "bigger",
          ["smaller", "it is smaller", "less", "small"] if v == "a" else ["bigger", "larger", "it is bigger", "it is larger", "greater"],
          [sb[2], boxes[3], boxes[2], lg[2], lg[3]]),
        Q("visual", "Which activity has the largest slice in the pie chart?", PIE_NAMES[big], [PIE_NAMES[big].lower()], [boxes[big], lg[big]]),
        Q("visual", "Which activity has the second largest slice in the pie chart?", PIE_NAMES[sec], [PIE_NAMES[sec].lower()], [boxes[sec], lg[sec]]),
        Q("visual", "What colour is the Dance slice?", "purple", ["violet"], [boxes[4], lg[4]]),
        Q("text_absent", "What is the name of the school where the survey was done?", None, [], []),
    ]
    return c, qs


# ---------------------------------------------------------------- page 4: calendar
EVENTS = ["Maths test", "Football 4pm", "Parents' evening 6pm", "Science fair", "Piano lesson 5pm", "Dentist 9am"]


def p4_params(rng):
    month = rng.choice([3, 5, 9, 10, 11, 4])
    N = calendar.monthrange(2026, month)[1]
    days = rng.sample(range(1, N + 1), 12)
    return dict(fam=rng.choice(FAMS), bg=rng.choice([(255, 255, 255), (252, 249, 240)]),
                head=rng.choice([(40, 80, 140), (140, 50, 70), (40, 110, 80)]), month=month, N=N, days=days)


def evacc(e):
    w = e.split()
    if w[-1].endswith(("am", "pm")):
        base, t = " ".join(w[:-1]), w[-1]
        return [e, base, f"{base} at {t}", f"{base} {t[:-2]} {t[-2:]}", f"{base} at {t[:-2]} {t[-2:]}"]
    return [e, e.lower()]


def p4(P, v):
    W, H = 2400, 1700
    c = Canvas(W, H, P["bg"])
    d, fam = c.d, P["fam"]
    month = P["month"]
    mname = calendar.month_name[month]
    c.text((100, 60), f"{mname} 2026", ft(fam, True, 92), P["head"])
    weeks = calendar.monthcalendar(2026, month)
    gx, gy, cw = 100, 230, 314
    hh = 70
    ch = min(215, (H - gy - hh - 80) // len(weeks))
    for i, nm in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]):
        d.rectangle([gx + i * cw, gy, gx + (i + 1) * cw, gy + hh], fill=P["head"])
        c.text((gx + i * cw + cw // 2, gy + hh // 2), nm, ft(fam, True, 40), (255, 255, 255), anchor="mm")
    dd = P["days"]
    ev = {dd[i]: EVENTS[i] for i in range(6)}
    crossed, hl = dd[6:8], dd[8] if v == "a" else dd[9]
    circ = dd[1] if v == "a" else dd[4]
    cell, num = {}, {}
    for r, wk in enumerate(weeks):
        for col, day in enumerate(wk):
            x0, y0 = gx + col * cw, gy + hh + r * ch
            x1, y1 = x0 + cw, y0 + ch
            fill = (245, 245, 250) if col >= 5 else (255, 255, 255)
            if day == hl:
                fill = (255, 235, 59)
            d.rectangle([x0, y0, x1, y1], fill=fill, outline=(60, 60, 60), width=3)
            if day == 0:
                d.rectangle([x0 + 3, y0 + 3, x1 - 3, y1 - 3], fill=(225, 225, 228))
                continue
            nb = c.text((x0 + 22, y0 + 12), str(day), ft(fam, True, 48), INK)
            num[day] = nb
            cell[day] = (x0, y0, x1, y1)
    evb = {}
    for day, e in ev.items():
        x0, y0, x1, y1 = cell[day]
        evb[day], _ = c.para(x0 + 14, y0 + 92, cw - 30, e, ft(fam, False, 30), (20, 20, 90), 38)
    for day in crossed:
        x0, y0, x1, y1 = cell[day]
        d.line([(x0 + 10, y0 + 68), (x1 - 10, y1 - 10)], fill=(190, 30, 30), width=7)
        d.line([(x1 - 10, y0 + 68), (x0 + 10, y1 - 10)], fill=(190, 30, 30), width=7)
    nb = num[circ]
    ccx, ccy = (nb[0] + nb[2]) / 2, (nb[1] + nb[3]) / 2
    d.ellipse([ccx - 56, ccy - 42, ccx + 56, ccy + 42], outline=(30, 60, 210), width=7)
    circbox = (ccx - 62, ccy - 52, ccx + 62, ccy + 52)
    pe = dd[2]
    qs = [
        Q("text", "Which month and year is shown on this calendar?", f"{mname} 2026", [f"{mname.lower()} 2026", mname], [(90, 40, 900, 190)]),
        Q("text", "What time does the parents' evening start?", "6 pm", ["6pm", "6:00 pm", "6", "18:00", "6 o'clock", "6 pm in the evening"], [evb[pe]]),
        Q("text", f"What is printed on the {ordinal(dd[0])} of the month?", "Maths test", ["maths test", "math test", "a maths test"], [evb[dd[0]]]),
        Q("mixed", "What event is printed on the circled date?", ev[circ], evacc(ev[circ]), [circbox, evb[circ]]),
        Q("visual", "Which date is circled?", str(circ), [str(circ), ordinal(circ), f"the {ordinal(circ)}", f"{mname} {circ}"], [circbox]),
        Q("visual", "Which date has a yellow background?", str(hl), [str(hl), ordinal(hl), f"the {ordinal(hl)}", f"{mname} {hl}"], [cell[hl]]),
        Q("visual", "How many dates are crossed out?", "2", ["2", "two", "2 dates", "two dates"], [cell[crossed[0]], cell[crossed[1]]]),
        Q("text_absent", "What time does the science fair start?", None, [], []),
    ]
    return c, qs


# ---------------------------------------------------------------- page 5: answer sheet
def p5_params(rng):
    key = [rng.choice("ABCD") for _ in range(12)]
    key[3] = "C"
    wrong = rng.sample([i for i in range(12) if i not in (3, 6)], 3)
    stu = list(key)
    for i in wrong:
        stu[i] = rng.choice([x for x in "ABCD" if x != key[i]])
    alt7 = rng.choice([x for x in "ABCD" if x != key[6]])
    return dict(fam=rng.choice(FAMS), bg=rng.choice([(255, 255, 255), (252, 252, 245)]), key=key, stu=stu, alt7=alt7,
                name=rng.choice(["Mara Ellis", "Jonas Berg", "Priya Nair"]), cls=rng.choice(["9C", "10A", "8B"]),
                unit=rng.choice(["Unit 4", "Unit 6", "Unit 2"]), ink=rng.choice([(20, 20, 20), (20, 30, 80)]))


def p5(P, v):
    W, H = 1500, 2000
    c = Canvas(W, H, P["bg"])
    d, fam, ink = c.d, P["fam"], P["ink"]
    c.text((80, 60), f"{P['unit']} Quiz: Answer Sheet", ft(fam, True, 70), ink)
    nb = c.text((80, 190), f"Name: {P['name']}", ft(fam, False, 46), ink)
    c.text((80, 260), f"Class: {P['cls']}", ft(fam, False, 46), ink)
    stu = list(P["stu"])
    if v == "a":
        stu[3] = "C"
        stu[6] = None
    else:
        stu[3] = "D"
        stu[6] = P["alt7"]
    bx = [280, 400, 520, 640]
    for L, x in zip("ABCD", bx):
        c.text((x, 400), L, ft("Arial", True, 40), ink, anchor="mm")
    rows, rowb = [], []
    for i in range(12):
        yy = 490 + i * 100
        c.text((200, yy), f"{i + 1}.", ft(fam, True, 42), ink, anchor="rm")
        for L, x in zip("ABCD", bx):
            if stu[i] == L:
                d.ellipse([x - 32, yy - 32, x + 32, yy + 32], fill=(10, 10, 10))
            else:
                d.ellipse([x - 32, yy - 32, x + 32, yy + 32], outline=(70, 70, 70), width=3)
                c.text((x, yy), L, ft("Arial", False, 28), (120, 120, 120), anchor="mm")
        rowb.append((100, yy - 40, 700, yy + 40))
    grid = (90, 365, 720, 490 + 11 * 100 + 45)
    c.text((860, 400), "Instructions", ft(fam, True, 48), ink)
    ib = []
    yy = 480
    for s in ["Use a dark pen. Fill each bubble completely.", "There are 12 questions. Each question is worth 1 mark.", "Time allowed: 20 minutes."]:
        bb, yy = c.para(860, yy, 560, s, ft(fam, False, 38), ink, 54)
        ib.append(bb)
        yy += 14
    d.rectangle([860, 1230, 1400, 1880], outline=ink, width=6)
    c.text((1130, 1275), "ANSWER KEY", ft(fam, True, 48), ink, anchor="mt")
    c.text((1130, 1335), "(for marking)", ft(fam, False, 32), ink, anchor="mt")
    kb = []
    for i in range(12):
        col, row = divmod(i, 6)
        kb.append(c.text((920 + col * 250, 1420 + row * 70), f"{i + 1}.  {P['key'][i]}", ft(fam, True, 42), ink))
    ncorrect = sum(1 for i in range(12) if stu[i] == P["key"][i])
    nmark = sum(1 for s in stu if s)
    k10 = P["key"][9]
    same = stu[3] == P["key"][3]
    qs = [
        Q("text", "According to the answer key, what is the correct answer to question 10?", k10, [k10, f"option {k10}", f"answer {k10}"], [kb[9]]),
        Q("text", "How many questions are on the quiz?", "12", nums(12, "questions"), [ib[1]]),
        Q("text", "What is the name written on the answer sheet?", P["name"], [P["name"].split()[0], P["name"].split()[1]], [nb]),
        Q("mixed", "Does the student's answer to question 4 match the answer key?", "Yes" if same else "No",
          ["yes", "it matches", "matches"] if same else ["no", "it does not match", "does not match", "incorrect"], [rowb[3], kb[3]]),
        Q("mixed", "How many questions did the student answer correctly according to the answer key?", str(ncorrect),
          nums(ncorrect, "questions", "correct"), [grid, (860, 1230, 1400, 1880)]),
        Q("visual", "Which bubble is filled in for question 4?", stu[3], [stu[3], f"option {stu[3]}", f"answer {stu[3]}", f"bubble {stu[3]}"], [rowb[3]]),
        Q("visual", "How many questions have a bubble filled in?", str(nmark), nums(nmark, "questions"), [grid]),
        Q("text_absent", "What is the name of the teacher who set the quiz?", None, [], []),
    ]
    return c, qs


# ---------------------------------------------------------------- page 6: textbook with plant diagram
def leaf(c, bx, by, ang, ln, wd, col):
    a = math.radians(ang)
    ux, uy = math.cos(a), math.sin(a)
    nx, ny = -uy, ux
    up, dn = [], []
    for i in range(0, 25):
        t = i / 24
        hw = wd / 2 * math.sin(math.pi * t) ** 0.8
        px, py = bx + ux * ln * t, by + uy * ln * t
        up.append((px + nx * hw, py + ny * hw))
        dn.append((px - nx * hw, py - ny * hw))
    c.d.polygon(up + dn[::-1], fill=col, outline=(30, 90, 30), width=3)
    c.d.line([(bx, by), (bx + ux * ln * 0.95, by + uy * ln * 0.95)], fill=(190, 230, 170), width=4)
    pts = up + dn
    return (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts))


def p6_params(rng):
    return dict(fam=rng.choice(FAMS[:4]), bg=rng.choice([(252, 251, 246), (248, 250, 252)]), pg=rng.randint(40, 90),
                nfun=rng.choice(["two", "three"]), acc=rng.choice([(30, 100, 60), (60, 70, 140), (140, 60, 40)]))


def p6(P, v):
    W, H = 2200, 1500
    c = Canvas(W, H, P["bg"])
    d, fam, ac = c.d, P["fam"], P["acc"]
    d.rectangle([0, 0, W, 130], fill=ac)
    c.text((80, 65), "Chapter 4   Plant Structure and Function", ft(fam, True, 62), (255, 255, 255), anchor="lm")
    d.rectangle([60, 190, 960, 1350], outline=(80, 80, 80), width=4)
    cx = 520
    d.rectangle([64, 1010, 956, 1346], fill=(224, 200, 158))
    d.line([(64, 1010), (956, 1010)], fill=(120, 90, 50), width=5)
    for p1_, p2_ in (((520, 1010), (420, 1250)), ((520, 1010), (520, 1290)), ((520, 1010), (620, 1250)),
                     ((470, 1130), (370, 1190)), ((570, 1130), (670, 1190))):
        d.line([p1_, p2_], fill=(100, 66, 32), width=11)
    d.line([(cx, 480), (cx, 1010)], fill=(50, 125, 50), width=28)
    lb = []
    for by in (640, 810):
        lb.append(leaf(c, cx, by, -25, 240, 105, (70, 160, 70)))
        lb.append(leaf(c, cx, by, 205, 240, 105, (70, 160, 70)))
    petal = (245, 215, 40) if v == "a" else (240, 120, 175)
    fcx, fcy = cx, 420
    for k in range(8):
        a = math.radians(k * 45)
        px, py = fcx + 88 * math.cos(a), fcy + 88 * math.sin(a)
        d.ellipse([px - 50, py - 50, px + 50, py + 50], fill=petal, outline=(120, 90, 20), width=3)
    d.ellipse([fcx - 55, fcy - 55, fcx + 55, fcy + 55], fill=(120, 70, 30), outline=(60, 30, 10), width=3)
    flower = (fcx - 140, fcy - 140, fcx + 140, fcy + 140)
    leaves = U(*lb)
    c.text((510, 1405), "Figure 4.1   A flowering plant", ft(fam, False, 36), INK, anchor="mm")
    # labels
    lf = ft(fam, True, 46)
    def label(txt, xy, anchor):
        bb = d.textbbox(xy, txt, font=lf, anchor=anchor)
        d.rectangle([bb[0] - 12, bb[1] - 8, bb[2] + 12, bb[3] + 8], fill=(255, 255, 255), outline=(40, 40, 40), width=3)
        d.text(xy, txt, font=lf, fill=(20, 20, 20), anchor=anchor)
        return (bb[0] - 14, bb[1] - 10, bb[2] + 14, bb[3] + 10)
    pl = label("petal", (800, 260), "lm")
    c.arrow((pl[0], 260), (cx + 62, fcy - 55), (200, 30, 30))
    lfb = label("leaf", (800, 690), "lm")
    c.arrow((lfb[0], 690), (cx + 125, 612), (20, 20, 200))
    sl = label("stem", (110, 890), "lm")
    rl = label("roots", (110, 1190), "lm")
    stem_tgt, root_tgt = (cx - 14, 890), (462, 1160)
    cs, cr = (150, 0, 150), (20, 130, 130)
    if v == "a":
        c.arrow((sl[2], 890), stem_tgt, cs)
        c.arrow((rl[2], 1190), root_tgt, cr)
    else:
        c.arrow((sl[2], 890), root_tgt, cs)
        c.arrow((rl[2], 1190), stem_tgt, cr)
    labarea = (90, 850, 540, 1235)
    # text
    x, y = 1040, 190
    c.text((x, y), "How plants are built", ft(fam, True, 54), ac)
    y += 90
    sents = ["The roots anchor the plant in the soil and absorb water and minerals from the ground.",
             "The stem carries water up to the leaves and holds the flower in the light.",
             "In the leaves, the plant makes its own food using sunlight in a process called photosynthesis.",
             "The flower contains the parts the plant needs to make seeds."]
    sb = []
    for s in sents:
        bb, y = c.para(x, y, 1060, s, ft(fam, False, 38), INK, 54)
        sb.append(bb)
        y += 14
    ey = y + 40
    d.rectangle([x - 20, ey - 20, W - 70, ey + 300], outline=ac, width=5)
    c.text((x, ey), "Exercise 4.1", ft(fam, True, 48), ac)
    ey += 80
    ex = ["Copy Figure 4.1 and label four parts of the plant.", "Name the process by which leaves make food.",
          f"Give {P['nfun']} functions of the roots."]
    eb = []
    for i, s in enumerate(ex, 1):
        bb, ey = c.para(x, ey, 1060, f"{i}.  {s}", ft(fam, False, 38), INK, 54)
        eb.append(bb)
        ey += 14
    pgb = c.text((W - 90, H - 50), f"Page {P['pg']}", ft(fam, False, 36), INK, anchor="rm")
    pcol = "yellow" if v == "a" else "pink"
    qs = [
        Q("text", "What is the name of the process by which leaves make food?", "photosynthesis", ["photosynthesis"], [sb[2], eb[1]]),
        Q("text", "What page number is printed on this page?", str(P["pg"]), [str(P["pg"]), f"page {P['pg']}"], [pgb]),
        Q("text", "How many functions of the roots does question 3 of the exercise ask for?", P["nfun"],
          nums({"two": 2, "three": 3}[P["nfun"]]), [eb[2]]),
        Q("mixed", "Which label is on the arrow that points to the part that absorbs water and minerals from the soil?",
          "roots" if v == "a" else "stem", ["roots", "the roots label", "root"] if v == "a" else ["stem", "the stem label"], [sb[0], labarea]),
        Q("visual", "Which label is on the arrow that points to the stem of the plant?", "stem" if v == "a" else "roots",
          ["stem", "the stem label"] if v == "a" else ["roots", "the roots label", "root"], [labarea]),
        Q("visual", "How many leaves does the drawn plant have?", "4", nums(4, "leaves"), [leaves]),
        Q("visual", "What colour are the petals of the flower in the diagram?", pcol, [pcol] + (["golden"] if v == "a" else ["light pink"]), [flower]),
        Q("text_absent", "Who is the author of this textbook?", None, [], []),
    ]
    return c, qs


PAGES = [(p1_params, p1), (p2_params, p2), (p3_params, p3), (p4_params, p4), (p5_params, p5), (p6_params, p6)]


def main():
    seed = int(os.environ.get("HW3_SEED", "50505"))
    out = os.environ.get("HW3_OUT", os.path.dirname(os.path.abspath(__file__)))
    os.makedirs(os.path.join(out, "images"), exist_ok=True)
    rows = []
    for n, (pp, pf) in enumerate(PAGES, 1):
        P = pp(random.Random(seed * 1000 + n))
        for v in "ab":
            c, qs = pf(P, v)
            iid = f"hw3-{n:03d}{v}"
            c.im.save(os.path.join(out, "images", iid + ".png"))
            for k, q in enumerate(qs, 1):
                et = q["et"]
                answerable = q["ans"] is not None
                rows.append(dict(
                    question_id=f"{iid}-q{k}", image_id=iid, image_path=f"images/{iid}.png", question=q["q"],
                    answer=q["ans"], answerable=answerable, evidence_type="text" if et == "text_absent" else et,
                    evidence_boxes=[c.n(b) for b in q["boxes"]] if answerable else [],
                    accepted_answers=list(dict.fromkeys(q["acc"])), pair_id=f"hw3-{n:03d}", source="synthetic", notes=None))
    with open(os.path.join(out, "items.jsonl"), "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    from collections import Counter
    print(len(rows), "items", dict(Counter(r["evidence_type"] for r in rows)), "unanswerable", sum(not r["answerable"] for r in rows))


if __name__ == "__main__":
    main()
