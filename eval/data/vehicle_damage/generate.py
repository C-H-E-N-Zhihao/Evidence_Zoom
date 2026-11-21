"""Synthetic vehicle damage inspection sheets (car diagram with damage marks) with counterfactual pairs.

    python3 -m eval.data.vehicle_damage.generate

Writes images/dmg-XXX[a|b].png, items.jsonl, items_dev.jsonl and items_heldout.jsonl next to this file.
Motor-claim use case: an inspector marks damage on a printed car outline. Claim data are typed text; the
panel numbers/letters and their names are printed (key table), but which panels are damaged, and how,
exists only as drawn marks on the diagram. Every panel name is printed in the key on every sheet.
Each base sheet `dmg-XXXa` has a partner `dmg-XXXb` identical except for ONE detail: one damage mark moves
to another panel, or one mark changes type (scratch <-> dent).

Templates:
  A (dev)      portrait, top view of the car with 15 numbered panels, key table on the right, red
               "X" = scratch, red hatching = dent. 1500 x 2000 px.
  B (held-out) landscape, left and right side profiles with 12 lettered zones, key below, red filled
               dot = dent, red zig-zag = scratch, slight rotation. 2000 x 1250 px.
All claims, plates and vehicles are fictitious. Gold boxes are recorded while drawing.
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
SEED = 404

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

MODELS = ["Volta Comet 1.4", "Rheno Alto Hybrid", "Kestrel S5 Touring", "Marlin Duo e-Drive", "Aurel 300 CDI",
          "Nova Brisk 1.2"]
INSPECTORS = ["M. Favre", "S. Odermatt", "P. Zanetti", "C. Lenoir"]
RED = (205, 25, 30)
# template A: top view; (name, x-range in body widths, y-range in body lengths), car points up
PANELS_A = [("Front bumper", (0.05, 0.95), (0.00, 0.06)), ("Bonnet", (0.18, 0.82), (0.06, 0.30)),
            ("Windscreen", (0.18, 0.82), (0.30, 0.40)), ("Roof", (0.18, 0.82), (0.40, 0.68)),
            ("Rear window", (0.18, 0.82), (0.68, 0.76)), ("Boot lid", (0.18, 0.82), (0.76, 0.94)),
            ("Rear bumper", (0.05, 0.95), (0.94, 1.00)),
            ("Front left wing", (0.0, 0.18), (0.06, 0.30)), ("Front left door", (0.0, 0.18), (0.30, 0.52)),
            ("Rear left door", (0.0, 0.18), (0.52, 0.72)), ("Rear left wing", (0.0, 0.18), (0.72, 0.94)),
            ("Front right wing", (0.82, 1.0), (0.06, 0.30)), ("Front right door", (0.82, 1.0), (0.30, 0.52)),
            ("Rear right door", (0.82, 1.0), (0.52, 0.72)), ("Rear right wing", (0.82, 1.0), (0.72, 0.94))]
GLASS = {"Windscreen", "Rear window"}
# template B: side zones, (name, x-range as fraction of length measured from the car's FRONT)
ZONES_B = [("Front bumper", 0.0, 0.08), ("Front wing", 0.08, 0.30), ("Front door", 0.30, 0.55),
           ("Rear door", 0.55, 0.78), ("Rear wing", 0.78, 0.93), ("Rear bumper", 0.93, 1.0)]
UNANSWERABLE = ["What is the estimated repair cost?", "Who was driving the vehicle at the time of the accident?",
                "What is the vehicle identification number (VIN)?", "What colour is the vehicle?",
                "Where did the accident happen?"]


def panel_names(template: str) -> list[str]:
    if template == "A":
        return [n for n, _, _ in PANELS_A]
    return [f"{side} {n.lower()}" for side in ("Left", "Right") for n, _, _ in ZONES_B]


def damageable(template: str) -> list[int]:
    return [i for i, n in enumerate(panel_names(template)) if n not in GLASS]


def make_sheet(rng: random.Random, template: str, idx: int) -> dict:
    dmg = rng.sample(damageable(template), 2)
    return {"template": template, "claim": f"MC-{rng.randint(2025, 2026)}-{rng.randint(100000, 999999)}",
            "plate": f"{rng.choice(['ZH', 'VD', 'GE', 'LU', 'SG', 'NE'])} {rng.randint(1000, 499999)}",
            "model": rng.choice(MODELS), "odo": f"{rng.randint(8, 210)}'{rng.randint(0, 999):03d}",
            "date": f"{rng.randint(1, 28):02d}.{rng.randint(1, 11):02d}.2026", "inspector": rng.choice(INSPECTORS),
            "damage": {d: rng.choice(["scratch", "dent"]) for d in dmg},
            "seed": SEED * 1000 + idx, "angle": 0.0 if template == "A" else rng.choice([1.3, -1.2]),
            "unans": UNANSWERABLE[idx % len(UNANSWERABLE)]}


def hatch(img: Image.Image, rect, color=RED, step=13, width=4) -> None:
    x0, y0, x1, y1 = [int(v) for v in rect]
    layer = Image.new("RGBA", (x1 - x0, y1 - y0), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    w, h = x1 - x0, y1 - y0
    for c in range(-h, w, step):
        d.line((c, h, c + h, 0), fill=color + (235,), width=width)
    d.rectangle((1, 1, w - 2, h - 2), outline=color + (255,), width=3)
    img.paste(layer, (x0, y0), layer)


def x_mark(d, c, r, color=RED, width=7) -> None:
    d.line((c[0] - r, c[1] - r, c[0] + r, c[1] + r), fill=color, width=width)
    d.line((c[0] + r, c[1] - r, c[0] - r, c[1] + r), fill=color, width=width)


def render_a(p: dict) -> tuple[Image.Image, dict]:
    W, H = 1500, 2000
    img = Image.new("RGB", (W, H), (251, 251, 248))
    d = ImageDraw.Draw(img)
    bx = {}
    text(d, (70, 60), "Vehicle Inspection Report", font("sansb", 54), (25, 25, 25))
    text(d, (70, 132), "Lemanic Assurance  -  motor claims expertise", font("sans", 28), (100, 100, 100))
    d.line((70, 185, 1430, 185), fill=(40, 40, 40), width=3)
    fields = [("claim", "Claim no."), ("plate", "Registration"), ("model", "Make / model"), ("odo", "Odometer (km)"),
              ("date", "Inspection date"), ("inspector", "Inspector")]
    for i, (k, lab) in enumerate(fields):
        x, y = (70 if i % 2 == 0 else 760), 215 + (i // 2) * 80
        a = text(d, (x, y), lab, font("sans", 24), (110, 110, 110))
        b = text(d, (x, y + 30), p[k], font("sansb", 32), (20, 20, 20))
        bx[k] = union(a, b)
    # car, top view
    cw, cl, x0, top = 400, 1040, 330, 520
    text(d, (x0 + cw / 2, top - 50), "FRONT", font("sansb", 26), (90, 90, 90), "mm")
    text(d, (x0 + cw / 2, top + cl + 40), "REAR", font("sansb", 26), (90, 90, 90), "mm")
    for wy in (0.12, 0.78):  # wheels
        for wx in (x0 - 34, x0 + cw + 4):
            d.rounded_rectangle((wx, top + wy * cl, wx + 30, top + (wy + 0.12) * cl), 8, fill=(60, 60, 60))
    d.rounded_rectangle((x0, top, x0 + cw, top + cl), 70, fill=(236, 238, 242), outline=(40, 40, 40), width=4)
    rects = {}
    for i, (name, (fx0, fx1), (fy0, fy1)) in enumerate(PANELS_A):
        r = (x0 + fx0 * cw, top + fy0 * cl, x0 + fx1 * cw, top + fy1 * cl)
        rects[i] = r
        fill = (205, 222, 236) if name in GLASS else None
        d.rectangle(r, outline=(70, 70, 70), width=2, fill=fill)
    for i, r in rects.items():
        side = PANELS_A[i][1][1] - PANELS_A[i][1][0] < 0.3
        cx = (r[0] + r[2]) / 2
        cy = r[1] + 30 if side else (r[1] + r[3]) / 2
        if PANELS_A[i][2][1] - PANELS_A[i][2][0] <= 0.06:  # bumpers: number at the left end
            cx, cy = r[0] + 40, (r[1] + r[3]) / 2
        elif not side:
            cx = r[0] + 40
        d.ellipse((cx - 19, cy - 19, cx + 19, cy + 19), fill="white", outline=(40, 40, 40), width=2)
        nb = text(d, (cx, cy), str(i + 1), font("sansb", 22), (20, 20, 20), "mm")
        bx[f"panel{i}"] = list(r)
        # damage mark region: away from the number
        if side:
            mr = (r[0] + 8, r[1] + 62, r[2] - 8, r[3] - 10)
        elif PANELS_A[i][2][1] - PANELS_A[i][2][0] <= 0.06:
            mr = (r[0] + 120, r[1] + 6, r[2] - 120, r[3] - 6)
        else:
            mr = (r[0] + 100, r[1] + 14, r[2] - 40, r[3] - 14)
        if i in p["damage"]:
            if p["damage"][i] == "dent":
                hatch(img, mr)
            else:
                c = ((mr[0] + mr[2]) / 2, (mr[1] + mr[3]) / 2)
                x_mark(d, c, min(28, (mr[2] - mr[0]) / 2 - 2, (mr[3] - mr[1]) / 2 + 6))
    d.polygon([(x0 - 10, top + 0.32 * cl), (x0, top + 0.30 * cl), (x0, top + 0.35 * cl)], fill=(60, 60, 60))
    d.polygon([(x0 + cw + 10, top + 0.32 * cl), (x0 + cw, top + 0.30 * cl), (x0 + cw, top + 0.35 * cl)], fill=(60, 60, 60))
    # key table
    kx, ky = 900, 500
    text(d, (kx, ky), "Panel key", font("sansb", 30))
    ky += 50
    for i, (name, _, _) in enumerate(PANELS_A):
        y = ky + i * 50
        d.rectangle((kx, y, 1430, y + 50), outline=(170, 170, 170), width=1)
        a = text(d, (kx + 18, y + 12), str(i + 1), font("sansb", 26))
        b = text(d, (kx + 80, y + 12), name, font("sans", 26))
        bx[f"key{i}"] = [kx, y, 1430, y + 50]
    # legend
    ly = ky + 15 * 50 + 50
    text(d, (kx, ly), "Legend", font("sansb", 30))
    x_mark(d, (kx + 30, ly + 75), 20)
    text(d, (kx + 70, ly + 62), "Scratch", font("sans", 28))
    hatch(img, (kx + 10, ly + 115, kx + 50, ly + 155))
    text(d, (kx + 70, ly + 120), "Dent", font("sans", 28))
    text(d, (70, 1880), "Marks entered by the inspector on site. Photos attached separately.", font("sans", 24),
         (110, 110, 110))
    return img, bx


def _car_profile(d, img, bx, p, x0, y0, L, Hh, facing_left: bool, side: str, letters: str, k0: int) -> None:
    fx = (lambda f: x0 + f * L) if facing_left else (lambda f: x0 + (1 - f) * L)
    fy = lambda f: y0 + f * Hh
    body = [(0, 0.55), (0.03, 0.36), (0.24, 0.28), (0.36, 0.04), (0.70, 0.02), (0.86, 0.30), (0.99, 0.36), (1.0, 0.62),
            (0.98, 0.82), (0.0, 0.82)]
    d.polygon([(fx(a), fy(b)) for a, b in body], fill=(238, 240, 244), outline=(40, 40, 40), width=4)
    win = [(0.38, 0.09), (0.68, 0.07), (0.81, 0.30), (0.33, 0.30)]
    d.polygon([(fx(a), fy(b)) for a, b in win], fill=(205, 222, 236), outline=(60, 60, 60), width=2)
    for wf in (0.19, 0.80):
        cx, cy, r = fx(wf), fy(0.84), 0.17 * Hh
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(55, 55, 55))
        d.ellipse((cx - r / 2, cy - r / 2, cx + r / 2, cy + r / 2), fill=(170, 170, 170))
    for j, (name, a, b) in enumerate(ZONES_B):
        k = k0 + j
        xa, xb = sorted((fx(a), fx(b)))
        if j:
            xd = fx(a)
            for yy in range(int(fy(0.32)), int(fy(0.80)), 14):
                d.line((xd, yy, xd, yy + 7), fill=(90, 90, 90), width=2)
        cx = (xa + xb) / 2
        lb = (cx - 17, fy(1.12) - 17, cx + 17, fy(1.12) + 17)
        d.rectangle(lb, fill="white", outline=(40, 40, 40), width=2)
        tl = text(d, (cx, fy(1.12)), letters[j], font("narrowb", 26), (20, 20, 20), "mm")
        d.line((cx, fy(0.83), cx, lb[1]), fill=(150, 150, 150), width=1)
        zone = [xa, fy(0.28), xb, fy(0.82)]
        bx[f"panel{k}"] = union(zone, list(lb))
        if k in p["damage"]:
            mc = (cx, fy(0.50))
            if p["damage"][k] == "dent":
                d.ellipse((mc[0] - 17, mc[1] - 17, mc[0] + 17, mc[1] + 17), fill=RED)
            else:
                hw = min(30, (xb - xa) / 2 - 4)
                pts = [(mc[0] - hw + i * hw / 2.5, mc[1] + (12 if i % 2 else -12)) for i in range(6)]
                d.line(pts, fill=RED, width=6, joint="curve")
    text(d, (x0 + L / 2, y0 - 40), f"{side.upper()} SIDE", font("narrowb", 30), (60, 60, 60), "mm")


def render_b(p: dict) -> tuple[Image.Image, dict]:
    W, H = 2000, 1250
    img = Image.new("RGB", (W, H), (246, 244, 238))
    d = ImageDraw.Draw(img)
    bx = {}
    text(d, (60, 40), "DAMAGE REPORT", font("serifb", 46), (120, 20, 20))
    text(d, (1940, 52), "Expert sheet / constat d'expertise", font("serif", 28), (90, 90, 90), "ra")
    # field strip
    fields = [("claim", "CLAIM"), ("plate", "PLATE"), ("model", "VEHICLE"), ("odo", "KM"), ("date", "DATE"),
              ("inspector", "EXPERT")]
    xs = [60, 400, 680, 1110, 1360, 1640, 1940]
    for i, (k, lab) in enumerate(fields):
        d.rectangle((xs[i], 120, xs[i + 1] - 10, 210), outline=(100, 100, 100), width=2)
        a = text(d, (xs[i] + 12, 128), lab, font("narrow", 22), (110, 110, 110))
        b = text(d, (xs[i] + 12, 162), p[k], font("narrowb", 30), (20, 20, 20))
        bx[k] = union(a, b)
    _car_profile(d, img, bx, p, 120, 330, 780, 300, True, "left", "ABCDEF", 0)
    _car_profile(d, img, bx, p, 1100, 330, 780, 300, False, "right", "GHIJKL", 6)
    # key and legend
    ky = 800
    names = panel_names("B")
    for col, (x, letters, k0) in enumerate(((120, "ABCDEF", 0), (860, "GHIJKL", 6))):
        for j in range(6):
            y = ky + (j % 3) * 46
            xx = x + (j // 3) * 370
            a = text(d, (xx, y), letters[j], font("narrowb", 28))
            b = text(d, (xx + 40, y), names[k0 + j], font("narrow", 28))
            bx[f"key{k0 + j}"] = union(a, b)
    text(d, (1640, 800), "Legend", font("narrowb", 28))
    d.ellipse((1640, 852, 1672, 884), fill=RED)
    text(d, (1690, 850), "dent", font("narrow", 28))
    d.line([(1640 + i * 8, 920 + (8 if i % 2 else -8)) for i in range(5)], fill=RED, width=5)
    text(d, (1690, 905), "scratch", font("narrow", 28))
    d.line((60, 1000, 1940, 1000), fill=(150, 150, 150), width=1)
    text(d, (60, 1030), "Remarks: vehicle inspected in daylight; zones seen from outside the vehicle.", font("serif", 26),
         (80, 80, 80))
    d.line((1400, 1170, 1900, 1170), fill=(60, 60, 60), width=2)
    text(d, (1400, 1180), "Expert signature", font("narrow", 22), (100, 100, 100))
    signature(d, (1440, 1090, 1860, 1160), random.Random(p["seed"]), (30, 30, 30))
    return img, bx


def counterfactual(rng: random.Random, base: dict, idx: int) -> tuple[dict, int, int, str]:
    """Returns (cf, q6_panel, q7_panel, description)."""
    names = panel_names(base["template"])
    dmg = list(base["damage"])
    cf = dict(base)
    if idx % 2:
        src = rng.choice(dmg)
        dst = rng.choice([k for k in damageable(base["template"]) if k not in dmg])
        cf["damage"] = {(dst if k == src else k): t for k, t in base["damage"].items()}
        keep = [k for k in dmg if k != src][0]
        return cf, keep, dst, f"{base['damage'][src]} mark moved from {names[src]} to {names[dst]}"
    k = rng.choice(dmg)
    new = "dent" if base["damage"][k] == "scratch" else "scratch"
    cf["damage"] = dict(base["damage"])
    cf["damage"][k] = new
    other = rng.choice([j for j in damageable(base["template"]) if j not in dmg])
    return cf, k, other, f"mark on {names[k]} changed from {base['damage'][k]} to {new}"


def items_for(p: dict, image_id: str, pair_id: str, q6k: int, q7k: int, note: str, w: int, h: int, bx: dict) -> list[dict]:
    q = item_factory(image_id, pair_id, note, w, h, p["angle"])
    names = panel_names(p["template"])
    rng = random.Random(p["seed"])
    kk = rng.randrange(len(names))
    dmg = sorted(p["damage"])
    gold, acc = multi([names[k] for k in dmg])
    odo = p["odo"]
    if p["template"] == "A":
        q4 = f"Which panel is numbered {kk + 1} on the diagram?"
        q4_acc = [names[kk].lower()]
    else:
        letter = "ABCDEFGHIJKL"[kk]
        q4 = f"Which zone is marked with the letter {letter} on the diagram?"
        q4_acc = [names[kk].lower()]
    t6 = p["damage"][q6k]
    return [
        q(1, "What is the claim number on the inspection sheet?", p["claim"], "text", [bx["claim"]]),
        q(2, "What is the registration plate of the inspected vehicle?", p["plate"], "text", [bx["plate"]]),
        q(3, "What odometer reading (km) is recorded?", odo, "text", [bx["odo"]],
          [odo.replace("'", ""), odo.replace("'", ",") , odo + " km", odo.replace("'", "") + " km"]),
        q(4, q4, names[kk], "layout", [bx[f"key{kk}"]], q4_acc),
        q(5, "Which panels are marked as damaged on the diagram? Give the panel names from the key.", gold, "visual",
          [b for k in dmg for b in (bx[f"panel{k}"], bx[f"key{k}"])], acc),
        q(6, f"What type of damage is marked on the {names[q6k].lower()}? Answer scratch or dent.", t6, "visual",
          [bx[f"panel{q6k}"]], ["a " + t6]),
        q(7, f"Is the {names[q7k].lower()} marked as damaged? Answer yes or no.", "yes" if q7k in p["damage"] else "no",
          "visual", [bx[f"panel{q7k}"]]),
        q(8, p["unans"], None, "text"),
    ]


def main() -> None:
    rng = random.Random(SEED)
    (HERE / "images").mkdir(exist_ok=True)
    lines = []
    for idx, template in enumerate(["A", "A", "A", "B", "B"], start=1):
        base = make_sheet(rng, template, idx)
        cf, q6k, q7k, what = counterfactual(rng, base, idx)
        split = "dev" if template == "A" else "held-out"
        for suffix, p, extra in (("a", base, "base"), ("b", cf, f"counterfactual: {what}")):
            image_id = f"dmg-{idx:03d}{suffix}"
            img, bx = (render_a if template == "A" else render_b)(p)
            img = finish(img, p["seed"], p["angle"])
            img.save(HERE / "images" / f"{image_id}.png")
            lines += items_for(p, image_id, f"dmg-{idx:03d}", q6k, q7k, f"template {template} ({split}); {extra}",
                               img.width, img.height, bx)
    write_items(HERE, lines)
    print(f"wrote {len(lines) // 8} images and {len(lines)} items to {HERE}")


if __name__ == "__main__":
    main()
