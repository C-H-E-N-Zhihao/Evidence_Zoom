"""Synthetic home electrical panels (breaker boards) with counterfactual pairs.

    python3 -m eval.data.breaker_panel.generate

Writes images/bp-XXX[a|b].png, items.jsonl, items_dev.jsonl and items_heldout.jsonl next to this file.
Home-insurance use case (e.g. a water-damage or fire claim photo of the distribution board): circuit labels
and ratings are printed text (OCR suffices); whether a breaker is ON or OFF is only visible from the
position of its toggle (pixels). Each base panel `bp-XXXa` has a partner `bp-XXXb` identical except that
one breaker toggle changes position (the OFF breaker moves to another circuit, or a second breaker trips).

Templates:
  A (dev)      landscape photo-like enclosure, 2 rows x 6 vertical breakers, printed label strip above
               each row, toggle up = ON ("I"), down = OFF ("O"). 2000 x 1350 px.
  B (held-out) portrait white plastic enclosure, 1 column of 8 horizontally mounted breakers, handwritten
               legend card to the right, toggle right = ON ("I"), left = OFF ("O"), slight rotation.
               1150 x 1650 px.
All names, companies and references are fictitious. Gold boxes are recorded while drawing.
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
SEED = 101

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

CIRCUITS = ["Kitchen sockets", "Oven", "Dishwasher", "Washing machine", "Lighting ground floor",
            "Lighting upstairs", "Bathroom heater", "Water boiler", "Garage", "Garden pump",
            "Bedroom sockets", "Living room", "Heat pump", "EV charger", "Home office", "Smoke alarms",
            "Freezer", "Cellar"]
RATINGS = ["B10", "B13", "B16", "C16", "C20", "C32", "B20"]
INSTALLERS = ["Elektro Brunner SA", "Voltis Installations Sarl", "Lacroix & Fils Electricite",
              "Stromwerk Keller GmbH", "Alpes Courant SA"]
UNANSWERABLE = ["When was this panel last inspected?", "What is the reading of the electricity meter?",
                "What is the name of the home owner?", "How much did the installation cost?",
                "What is the serial number of the main switch?"]


def wrap(s: str, n: int) -> list[str]:
    words, lines, cur = s.split(), [], ""
    for w_ in words:
        if cur and len(cur) + 1 + len(w_) > n:
            lines.append(cur)
            cur = w_
        else:
            cur = (cur + " " + w_).strip()
    return lines + [cur]


def render_a(p: dict) -> tuple[Image.Image, dict]:
    W, H = 2000, 1350
    img = Image.new("RGB", (W, H), (196, 192, 184))
    d = ImageDraw.Draw(img)
    bx = {}
    # wall texture: faint vertical streaks
    r = random.Random(p["seed"])
    for x in range(0, W, 7):
        v = 190 + r.randint(-4, 4)
        d.line([(x, 0), (x, H)], fill=(v, v - 3, v - 10), width=3)
    d.rounded_rectangle((168, 108, 1868, 1278), 26, fill=(120, 116, 110))  # shadow
    d.rounded_rectangle((150, 90, 1850, 1260), 26, fill=(228, 226, 220), outline=(150, 148, 140), width=4)
    bx["installer"] = text(d, (220, 128), p["installer"], font("sansb", 36), (40, 40, 40))
    text(d, (220, 178), "Distribution board", font("sans", 26), (90, 90, 90))
    lab = text(d, (1440, 132), "Panel ref.", font("sans", 26), (90, 90, 90))
    ref = text(d, (1440, 166), p["ref"], font("sansb", 34), (40, 40, 40))
    bx["ref"] = union(lab, ref)
    mod_w, gap, x_start = 150, 22, 470
    rows_y = [380, 880]
    for row in range(2):
        y = rows_y[row]
        # DIN rail and label strip
        d.rectangle((200, y + 110, 1800, y + 150), fill=(170, 170, 168))
        d.rectangle((x_start - 10, y - 128, x_start + 6 * (mod_w + gap) - gap + 10, y - 12), fill=(250, 250, 246),
                    outline=(120, 120, 120), width=2)
        if row == 0:  # main switch, always ON, double width
            mx = 230
            d.rectangle((mx, y - 128, mx + 200, y - 12), fill=(250, 250, 246), outline=(120, 120, 120), width=2)
            text(d, (mx + 100, y - 70), "MAIN 40A", font("sansb", 28), (150, 20, 20), "mm")
            _breaker_v(d, (mx, y, mx + 200, y + 260), "40A", True, main=True)
        for col in range(6):
            k = row * 6 + col
            x = x_start + col * (mod_w + gap)
            num, name = k + 1, p["labels"][k]
            t0 = text(d, (x + 8, y - 122), str(num), font("sansb", 26), (20, 20, 20))
            ls = wrap(name, 12)
            tb = [text(d, (x + 8, y - 94 + 26 * i), ln, font("narrow", 25), (20, 20, 20)) for i, ln in enumerate(ls)]
            bx[f"label{k}"] = union(t0, *tb)
            mod = _breaker_v(d, (x, y, x + mod_w, y + 260), p["ratings"][k], k not in p["off"])
            bx[f"rating{k}"] = mod["rating"]
            bx[f"mod{k}"] = mod["box"]
            bx[f"brk{k}"] = union(bx[f"label{k}"], mod["box"])
    bx["all"] = union(*(bx[f"mod{k}"] for k in range(12)))
    return img, bx


def _breaker_v(d, box, rating, on, main=False) -> dict:
    x0, y0, x1, y1 = box
    d.rectangle(box, fill=(246, 246, 242), outline=(140, 140, 140), width=2)
    cx = (x0 + x1) / 2
    rb = text(d, (cx, y0 + 30), rating, font("sansb", 30), (30, 30, 30), "mm")
    text(d, (cx, y0 + 66), "I", font("sansb", 22), (60, 60, 60), "mm")
    text(d, (cx, y0 + 226), "O", font("sansb", 22), (60, 60, 60), "mm")
    sw = 70 if main else 54
    d.rectangle((cx - sw / 2, y0 + 80, cx + sw / 2, y0 + 210), fill=(55, 55, 58))
    hy = y0 + 84 if on else y0 + 154
    color = (200, 40, 40) if main else (236, 237, 241)
    d.rectangle((cx - sw / 2 + 4, hy, cx + sw / 2 - 4, hy + 52), fill=color)
    d.line((cx - sw / 2 + 8, hy + 46, cx + sw / 2 - 8, hy + 46), fill=(150, 150, 155), width=3)
    text(d, (cx, y1 - 14), "230V~ 6kA", font("sans", 15), (110, 110, 110), "mm")
    return {"rating": rb, "box": list(box)}


def render_b(p: dict) -> tuple[Image.Image, dict]:
    W, H = 1150, 1650
    img = Image.new("RGB", (W, H), (172, 160, 142))
    d = ImageDraw.Draw(img)
    bx = {}
    d.rounded_rectangle((112, 112, 1048, 1572), 40, fill=(110, 100, 88))
    d.rounded_rectangle((100, 100, 1036, 1560), 40, fill=(242, 242, 238), outline=(200, 200, 196), width=3)
    # installer sticker
    d.rectangle((150, 140, 986, 270), fill=(255, 238, 150), outline=(200, 180, 90), width=2)
    bx["installer"] = text(d, (170, 156), p["installer"], font("serifb", 32), (30, 30, 30))
    lab = text(d, (170, 212), "Ref:", font("serif", 28), (30, 30, 30))
    ref = text(d, (240, 212), p["ref"], font("serif", 28), (30, 30, 30))
    bx["ref"] = union(lab, ref)
    # legend card
    d.rectangle((560, 310, 990, 1500), fill=(252, 251, 245), outline=(160, 160, 160), width=2)
    for k in range(8):
        y = 330 + k * 145
        d.rectangle((160, y - 6, 540, y + 116), fill=(205, 205, 202))  # rail behind module
        mod = (190, y, 510, y + 110)
        x0, y0, x1, y1 = mod
        d.rectangle(mod, fill=(248, 248, 244), outline=(140, 140, 140), width=2)
        rb = text(d, (x0 + 14, y0 + 14), p["ratings"][k], font("sansb", 26), (30, 30, 30))
        fb = text(d, (x0 + 14, y0 + 62), f"F{k + 1}", font("sans", 24), (80, 80, 80))
        text(d, (x0 + 116, y0 + 55), "O", font("sansb", 22), (60, 60, 60), "mm")
        text(d, (x1 - 22, y0 + 55), "I", font("sansb", 22), (60, 60, 60), "mm")
        d.rectangle((x0 + 136, y0 + 32, x1 - 44, y0 + 78), fill=(60, 60, 62))
        on = k not in p["off"]
        hx = x1 - 48 - 58 if on else x0 + 140
        d.rectangle((hx, y0 + 36, hx + 58, y0 + 74), fill=(238, 128, 40))
        d.line((hx + 50, y0 + 40, hx + 50, y0 + 70), fill=(170, 80, 20), width=3)
        lb1 = text(d, (585, y + 22), f"F{k + 1}", font("note", 34), (20, 30, 120))
        lb2 = text(d, (660, y + 22), p["labels"][k], font("note", 34), (20, 30, 120))
        bx[f"label{k}"] = union(lb1, lb2)
        bx[f"rating{k}"] = union(rb, fb)
        bx[f"mod{k}"] = list(mod)
        bx[f"brk{k}"] = union(bx[f"label{k}"], list(mod))
    bx["all"] = union(*(bx[f"mod{k}"] for k in range(8)))
    return img, bx


def make_panel(rng: random.Random, template: str, idx: int) -> dict:
    n = 12 if template == "A" else 8
    return {"template": template, "labels": rng.sample(CIRCUITS, n), "ratings": [rng.choice(RATINGS) for _ in range(n)],
            "installer": rng.choice(INSTALLERS),
            "ref": f"TD-{rng.randint(1, 9)}-{rng.randint(1000, 9999)}", "off": [rng.randrange(n)],
            "seed": SEED * 1000 + idx, "angle": 0.0 if template == "A" else rng.choice([-1.6, 1.3, -0.9]),
            "unans": UNANSWERABLE[idx % len(UNANSWERABLE)]}


def counterfactual(rng: random.Random, base: dict, idx: int) -> tuple[dict, int, str]:
    n = len(base["labels"])
    j = rng.choice([k for k in range(n) if k not in base["off"]])
    cf = dict(base)
    if idx % 2:
        cf["off"] = [j]
        what = f"OFF breaker moved from circuit {base['off'][0] + 1} to circuit {j + 1}"
    else:
        cf["off"] = sorted(base["off"] + [j])
        what = f"circuit {j + 1} additionally switched OFF"
    return cf, j, what


def items_for(p: dict, image_id: str, pair_id: str, target: int, note: str, w: int, h: int, bx: dict) -> list[dict]:
    q = item_factory(image_id, pair_id, note, w, h, p["angle"])
    L = p["labels"]
    n = len(L)
    rng = random.Random(p["seed"])  # same choices for both images of a pair
    r_k = rng.choice([k for k in range(n) if k != target])
    if p["template"] == "A":
        nb_k = rng.choice([k for k in range(n) if k % 6 != 5])
        nb_q, nb_ans = f"Which circuit is directly to the right of '{L[nb_k]}' on the panel?", nb_k + 1
    else:
        nb_k = rng.choice(range(n - 1))
        nb_q, nb_ans = f"Which circuit is listed directly below '{L[nb_k]}'?", nb_k + 1
    off = sorted(p["off"])
    names = [L[k] for k in off]
    off_gold, off_acc = multi(names)
    if len(off) == 1:
        off_acc += [f"{off[0] + 1} {names[0]}", f"circuit {off[0] + 1}"]
    rating = p["ratings"][r_k]
    t_off = target in p["off"]
    count = len(off)
    return [
        q(1, "Which company installed this electrical panel?", p["installer"], "text", [bx["installer"]]),
        q(2, "What is the panel reference number?", p["ref"], "text", [bx["ref"]]),
        q(3, f"What current rating is printed on the breaker for '{L[r_k]}'?", rating, "layout",
          [bx[f"label{r_k}"], bx[f"rating{r_k}"]], [rating[1:] + "A", rating[1:] + " A", f"{rating[0]} {rating[1:]}"]),
        q(4, nb_q, L[nb_ans], "layout", [bx[f"label{nb_k}"], bx[f"label{nb_ans}"]],
          [f"{nb_ans + 1} {L[nb_ans]}", f"F{nb_ans + 1} {L[nb_ans]}"]),
        q(5, "Which circuit breakers are switched off (tripped)? Give their labels.", off_gold, "visual",
          [bx[f"brk{k}"] for k in off], off_acc),
        q(6, f"Is the breaker for '{L[target]}' switched on or off?", "off" if t_off else "on", "visual",
          [bx[f"brk{target}"]], ["switched off", "tripped", "OFF"] if t_off else ["switched on", "ON"]),
        q(7, "How many circuit breakers (not counting the main switch) are switched off?", str(count), "visual",
          [bx["all"]], [["zero", "one", "two", "three"][count]]),
        q(8, p["unans"], None, "text"),
    ]


def main() -> None:
    rng = random.Random(SEED)
    (HERE / "images").mkdir(exist_ok=True)
    lines = []
    for idx, template in enumerate(["A", "A", "A", "B", "B"], start=1):
        base = make_panel(rng, template, idx)
        cf, target, what = counterfactual(rng, base, idx)
        split = "dev" if template == "A" else "held-out"
        for suffix, p, extra in (("a", base, "base"), ("b", cf, f"counterfactual: {what}")):
            image_id = f"bp-{idx:03d}{suffix}"
            img, bx = (render_a if template == "A" else render_b)(p)
            img = finish(img, p["seed"], p["angle"])
            img.save(HERE / "images" / f"{image_id}.png")
            note = f"template {template} ({split}); {extra}"
            lines += items_for(p, image_id, f"bp-{idx:03d}", target, note, img.width, img.height, bx)
    write_items(HERE, lines)
    print(f"wrote {len(lines) // 8} images and {len(lines)} items to {HERE}")


if __name__ == "__main__":
    main()
