"""Synthetic accident-statement forms with free gold labels and counterfactual pairs.

    python -m eval.data.accident_statement.generate [--n 6] [--seed 0]

Writes images/eas-XXX[a|b].png and items.jsonl (format: eval/data/README.md) next to this file.
Each base form `eas-XXXa` has a counterfactual partner `eas-XXXb` that differs in exactly one
visual detail (one of driver B's ticks moves, or the sketch roles swap), sharing `pair_id`.

Not the official form: a simplified stand-in with the same evidence types (typed fields,
two columns of circumstance checkboxes, a sketch panel). All names/insurers/IDs are fictitious.
Gold boxes are recorded while drawing, normalized 0-1 on the rendered image.
"""
from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass, field, replace
from itertools import permutations
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
W, H = 1700, 2200
BLUE, ORANGE = "#2b6cb0", "#c05621"

CIRCUMSTANCES = [
    "parked / stationary", "leaving a parking place", "entering a parking place",
    "emerging from a car park or private ground", "entering a car park",
    "entering a roundabout", "circulating in a roundabout",
    "striking the rear of the other vehicle", "going in the same direction, different lane",
    "changing lanes", "overtaking", "turning to the right", "turning to the left",
    "reversing", "encroaching on the opposite lane", "coming from the right",
    "had not observed a priority sign",
]
INSURERS = ["Helvetia Mutual", "Lemanic Assurance", "Jura Insurance Co.", "Alpine Shield",
            "Rhone Valley Mutual", "Matterhorn Cover"]
CANTONS = ["VD", "GE", "VS", "FR", "NE", "BE", "ZH"]
SURNAMES = ["Keller", "Rossi", "Favre", "Meier", "Dubois", "Bianchi", "Schmid", "Girard"]


@dataclass
class Vehicle:
    insurer: str
    policy: str
    registration: str
    driver: str
    ticks: tuple[int, ...]


@dataclass
class Form:
    form_id: str
    a: Vehicle
    b: Vehicle
    rear_hitter: str = "A"  # which vehicle struck the rear of the other in the sketch
    boxes: dict[str, list[float]] = field(default_factory=dict)  # filled by render()


def _font(size: int):
    for name in ("/System/Library/Fonts/Helvetica.ttc",
                 "/System/Library/Fonts/Supplemental/Arial.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _n(x0, y0, x1, y1) -> list[float]:
    return [round(x0 / W, 4), round(y0 / H, 4), round(x1 / W, 4), round(y1 / H, 4)]


def render(form: Form) -> Image.Image:
    im = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(im)
    f_title, f, f_small = _font(46), _font(28), _font(22)
    bx = form.boxes

    d.text((80, 60), "Accident Statement (demo form)", fill="black", font=f_title)
    d.text((80, 125), "Simplified stand-in for evaluation - not an official document",
           fill="#666", font=f_small)

    for key, label, x, colour, v in (("A", "VEHICLE A", 80, BLUE, form.a),
                                     ("B", "VEHICLE B", 900, ORANGE, form.b)):
        d.rectangle([x, 190, x + 720, 560], outline=colour, width=4)
        bx[f"{key}.panel"] = _n(x, 190, x + 720, 560)
        d.text((x + 20, 205), label, fill=colour, font=f)
        for j, (name, k, val) in enumerate((("insurer", "Insurer", v.insurer),
                                             ("policy", "Policy no.", v.policy),
                                             ("registration", "Registration", v.registration),
                                             ("driver", "Driver", v.driver))):
            y = 270 + j * 70
            d.text((x + 20, y), f"{k}:", fill="#333", font=f_small)
            d.text((x + 220, y - 4), val, fill="black", font=f)
            tw = d.textlength(val, font=f)
            bx[f"{key}.{name}"] = _n(x + 215, y - 8, x + 225 + tw, y + 34)
            d.line([x + 215, y + 32, x + 700, y + 32], fill="#bbb", width=1)

    top = 610
    d.text((80, top), "12. CIRCUMSTANCES  (tick the boxes that apply)", fill="black", font=f)
    d.text((112, top + 50), "A", fill=BLUE, font=f)
    d.text((1548, top + 50), "B", fill=ORANGE, font=f)
    last_y = top
    for n, text in enumerate(CIRCUMSTANCES, start=1):
        y = top + 100 + (n - 1) * 52
        last_y = y + 36
        for key, x0, ticks, colour in (("A", 100, form.a.ticks, BLUE), ("B", 1540, form.b.ticks, ORANGE)):
            d.rectangle([x0, y, x0 + 36, y + 36], outline="black", width=2)
            bx[f"{key}.tick{n}"] = _n(x0 - 4, y - 4, x0 + 40, y + 40)
            if n in ticks:
                d.line([x0 + 6, y + 18, x0 + 15, y + 30], fill=colour, width=5)
                d.line([x0 + 15, y + 30, x0 + 33, y + 4], fill=colour, width=5)
        d.text((180, y + 4), f"{n:>2}.  {text}", fill="black", font=f_small)
    bx["A.tickcol"] = _n(90, top + 90, 146, last_y + 10)
    bx["B.tickcol"] = _n(1530, top + 90, 1586, last_y + 10)

    sy = top + 100 + 17 * 52 + 40
    d.text((80, sy), "13. SKETCH OF THE ACCIDENT", fill="black", font=f)
    panel = [80, sy + 50, W - 80, H - 80]
    d.rectangle(panel, outline="black", width=2)
    bx["sketch"] = _n(*panel)
    cx = (panel[0] + panel[2]) // 2
    d.rectangle([panel[0] + 40, sy + 200, panel[2] - 40, sy + 360], fill="#e2e8f0")
    for x in range(panel[0] + 60, panel[2] - 60, 120):
        d.line([x, sy + 280, x + 60, sy + 280], fill="white", width=6)
    # Travel is left -> right. The hitter is behind (left), the hit vehicle ahead (right).
    behind, ahead = (("A", BLUE), ("B", ORANGE)) if form.rear_hitter == "A" else (("B", ORANGE), ("A", BLUE))
    d.rectangle([cx + 40, sy + 300, cx + 240, sy + 350], outline=ahead[1], width=5)
    d.text((cx + 125, sy + 308), ahead[0], fill=ahead[1], font=f)
    d.rectangle([cx - 260, sy + 300, cx - 60, sy + 350], outline=behind[1], width=5)
    d.text((cx - 175, sy + 308), behind[0], fill=behind[1], font=f)
    d.line([cx - 300, sy + 325, cx - 270, sy + 325], fill=behind[1], width=4)
    d.polygon([(cx - 30, sy + 315), (cx + 30, sy + 325), (cx - 30, sy + 335)], fill="red")
    bx["sketch.impact"] = _n(cx - 270, sy + 290, cx + 250, sy + 360)
    d.text((panel[0] + 30, panel[3] - 50), "direction of travel  -->", fill="#555", font=f_small)
    return im


def _vehicle(rng: random.Random, insurer: str, ticks: tuple[int, ...]) -> Vehicle:
    prefix = "".join(w[0] for w in insurer.split()[:2]).upper()
    return Vehicle(
        insurer=insurer,
        policy=f"{prefix}-{rng.randint(1000, 9999)}-{rng.randint(1000, 9999)}",
        registration=f"{rng.choice(CANTONS)} {rng.randint(10, 999)} {rng.randint(100, 999)}",
        driver=f"{rng.choice('ABCDEFGHJKLMNPRS')}. {rng.choice(SURNAMES)}",
        ticks=ticks,
    )


def _ticks_answer(ticks: tuple[int, ...]) -> tuple[str, list[str]]:
    if not ticks:
        return "none", ["no boxes", "no box", "0"]
    s = sorted(ticks)
    gold = ", ".join(map(str, s))
    acc = {" ".join(map(str, p)) for p in permutations(s)}
    acc |= {" and ".join(map(str, p)) for p in permutations(s)}
    acc.discard(gold)
    return gold, sorted(acc)


def make_form(rng: random.Random, form_id: str) -> Form:
    ia, ib = rng.sample(INSURERS, 2)
    rear = rng.choice("AB")
    # Ticks consistent with a rear-end collision on a straight road, plus noise.
    hitter_ticks = {8} | set(rng.sample([9, 10, 11], rng.randint(0, 1)))
    other_ticks = set(rng.sample([1, 9, 10, 15, 16], rng.randint(0, 2)))
    ta, tb = (hitter_ticks, other_ticks) if rear == "A" else (other_ticks, hitter_ticks)
    va, vb = _vehicle(rng, ia, tuple(sorted(ta))), _vehicle(rng, ib, tuple(sorted(tb)))
    while vb.driver.split()[-1] == va.driver.split()[-1]:
        vb.driver = f"{rng.choice('ABCDEFGHJKLMNPRS')}. {rng.choice(SURNAMES)}"
    return Form(form_id, va, vb, rear)


def counterfactual(rng: random.Random, base: Form, form_id: str) -> tuple[Form, str]:
    """Change exactly one visual detail. Text fields stay identical."""
    if rng.random() < 0.5:
        ticks = set(base.b.ticks)
        free = [n for n in range(1, 18) if n not in ticks]
        if ticks and rng.random() < 0.5:
            old = rng.choice(sorted(ticks))
            ticks.remove(old)
            ticks.add(rng.choice(free))
            what = f"moved one of B's ticks from {old}"
        else:
            ticks.add(rng.choice(free))
            what = "added one tick for B"
        return replace(base, form_id=form_id, b=replace(base.b, ticks=tuple(sorted(ticks))), boxes={}), what
    return replace(base, form_id=form_id, rear_hitter="B" if base.rear_hitter == "A" else "A",
                   boxes={}), "swapped sketch roles"


def items_for(form: Form, pair_id: str, note: str | None) -> list[dict]:
    b = form.boxes
    path = f"images/{form.form_id}.png"
    q = lambda qid, question, answer, etype, boxes, acc=(), answerable=True: {
        "question_id": f"{form.form_id}-{qid}", "image_id": form.form_id, "image_path": path,
        "question": question, "answer": answer, "answerable": answerable, "evidence_type": etype,
        "evidence_boxes": boxes, "accepted_answers": list(acc), "pair_id": pair_id,
        "source": "synthetic", "notes": note,
    }
    tb_gold, tb_acc = _ticks_answer(form.b.ticks)
    a8 = 8 in form.a.ticks
    hit = "B" if form.rear_hitter == "A" else "A"
    return [
        q("q1", "What is vehicle A's insurance policy number?", form.a.policy, "text", [b["A.policy"]]),
        q("q2", "What is the registration number of vehicle B?", form.b.registration, "text",
          [b["B.registration"]]),
        q("q3", f"Which vehicle is insured by {form.b.insurer}?", "B", "layout", [b["B.insurer"]],
          ["vehicle B"]),
        q("q4", "Which circumstance boxes did driver B tick? Answer with the box numbers.", tb_gold,
          "visual", [b[f"B.tick{n}"] for n in form.b.ticks] or [b["B.tickcol"]], tb_acc),
        q("q5", "Did driver A tick circumstance 8 (striking the rear of the other vehicle)? Answer yes or no.",
          "yes" if a8 else "no", "visual", [b["A.tick8"]]),
        q("q6", "In the sketch, which vehicle was hit from behind? Answer A or B.", hit, "visual",
          [b["sketch.impact"]], [f"vehicle {hit}"]),
        q("q7", "What is driver A's driving licence number?", None, "text", [], (), answerable=False),
        q("q8", "Who is vehicle A's insurer?", form.a.insurer, "text", [b["A.insurer"]]),
    ]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=6, help="number of base forms (each gets a partner)")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    (HERE / "images").mkdir(exist_ok=True)
    lines = []
    for i in range(1, a.n + 1):
        base = make_form(rng, f"eas-{i:03d}a")
        cf, what = counterfactual(rng, base, f"eas-{i:03d}b")
        for form, note in ((base, None), (cf, f"counterfactual of {base.form_id}: {what}")):
            render(form).save(HERE / "images" / f"{form.form_id}.png")
            lines += items_for(form, f"eas-{i:03d}", note)
    (HERE / "items.jsonl").write_text("\n".join(json.dumps(l) for l in lines) + "\n")
    print(f"wrote {2 * a.n} images and {len(lines)} items to {HERE}")


if __name__ == "__main__":
    main()
