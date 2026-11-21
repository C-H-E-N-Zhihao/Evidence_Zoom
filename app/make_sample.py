"""Render a simplified accident-statement-style form for the demo.

Not the official form: a stand-in with the same evidence types (typed fields,
two columns of circumstance checkboxes, a sketch panel).
Run:  .venv/bin/python -m app.make_sample
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).parent / "static" / "sample.png"
W, H = 1700, 2200

CIRCUMSTANCES = [
    "parked / stationary", "leaving a parking place", "entering a parking place",
    "emerging from a car park or private ground", "entering a car park",
    "entering a roundabout", "circulating in a roundabout",
    "striking the rear of the other vehicle", "going in the same direction, different lane",
    "changing lanes", "overtaking", "turning to the right", "turning to the left",
    "reversing", "encroaching on the opposite lane", "coming from the right",
    "had not observed a priority sign",
]


def font(size: int):
    for name in ("/System/Library/Fonts/Helvetica.ttc",
                 "/System/Library/Fonts/Supplemental/Arial.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def main(ticks_a=(8,), ticks_b=(10, 15)):
    im = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(im)
    f_title, f, f_small = font(46), font(28), font(22)

    d.text((80, 60), "Accident Statement (demo form)", fill="black", font=f_title)
    d.text((80, 125), "Simplified stand-in for evaluation - not an official document",
           fill="#666", font=f_small)

    # Vehicle panels with typed fields.
    for i, (label, x, colour, fields) in enumerate([
        ("VEHICLE A", 80, "#2b6cb0", [("Insurer", "Helvetia Mutual"),
                                       ("Policy no.", "HM-7731-0042-CH"),
                                       ("Registration", "VD 482 113"),
                                       ("Driver", "M. Keller")]),
        ("VEHICLE B", 900, "#c05621", [("Insurer", "Lemanic Assurance"),
                                        ("Policy no.", "LA-2290-5518"),
                                        ("Registration", "GE 77 905"),
                                        ("Driver", "S. Rossi")]),
    ]):
        d.rectangle([x, 190, x + 720, 560], outline=colour, width=4)
        d.text((x + 20, 205), label, fill=colour, font=f)
        for j, (k, v) in enumerate(fields):
            y = 270 + j * 70
            d.text((x + 20, y), f"{k}:", fill="#333", font=f_small)
            d.text((x + 220, y - 4), v, fill="black", font=f)
            d.line([x + 215, y + 32, x + 700, y + 32], fill="#bbb", width=1)

    # Section 12: circumstances, two tick columns A | label | B.
    top = 610
    d.text((80, top), "12. CIRCUMSTANCES  (tick the boxes that apply)",
           fill="black", font=f)
    d.text((112, top + 50), "A", fill="#2b6cb0", font=f)
    d.text((1548, top + 50), "B", fill="#c05621", font=f)
    for n, text in enumerate(CIRCUMSTANCES, start=1):
        y = top + 100 + (n - 1) * 52
        for bx, ticks, colour in ((100, ticks_a, "#2b6cb0"), (1540, ticks_b, "#c05621")):
            d.rectangle([bx, y, bx + 36, y + 36], outline="black", width=2)
            if n in ticks:  # hand-drawn-ish tick
                d.line([bx + 6, y + 18, bx + 15, y + 30], fill=colour, width=5)
                d.line([bx + 15, y + 30, bx + 33, y + 4], fill=colour, width=5)
        d.text((180, y + 4), f"{n:>2}.  {text}", fill="black", font=f_small)

    # Section 13: sketch.
    sy = top + 100 + 17 * 52 + 40
    d.text((80, sy), "13. SKETCH OF THE ACCIDENT", fill="black", font=f)
    box = [80, sy + 50, W - 80, H - 80]
    d.rectangle(box, outline="black", width=2)
    cx = (box[0] + box[2]) // 2
    d.rectangle([box[0] + 40, sy + 200, box[2] - 40, sy + 360], fill="#e2e8f0")  # road
    for x in range(box[0] + 60, box[2] - 60, 120):
        d.line([x, sy + 280, x + 60, sy + 280], fill="white", width=6)
    # B ahead, A behind in the same lane, impact at B's rear.
    d.rectangle([cx + 40, sy + 300, cx + 240, sy + 350], outline="#c05621", width=5)
    d.text((cx + 125, sy + 308), "B", fill="#c05621", font=f)
    d.rectangle([cx - 260, sy + 300, cx - 60, sy + 350], outline="#2b6cb0", width=5)
    d.text((cx - 175, sy + 308), "A", fill="#2b6cb0", font=f)
    d.line([cx - 300, sy + 325, cx - 270, sy + 325], fill="#2b6cb0", width=4)  # arrow
    d.polygon([(cx - 30, sy + 315), (cx + 30, sy + 325), (cx - 30, sy + 335)],
              fill="red")  # impact marker
    d.text((box[0] + 30, box[3] - 50), "direction of travel  -->", fill="#555", font=f_small)

    OUT.parent.mkdir(exist_ok=True)
    im.save(OUT)
    print(f"wrote {OUT} ({W}x{H}); A ticks {ticks_a}, B ticks {ticks_b}")


if __name__ == "__main__":
    main()
