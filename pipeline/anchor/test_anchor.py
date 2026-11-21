"""$0 checks for pipeline.anchor (needs the macOS OCR helper; no model).  Run: python -m pipeline.anchor.test_anchor"""
import json
from pathlib import Path

from PIL import Image

from eval.schema import Usage
from pipeline import anchor

IMG = Path("eval/data/accident_statement/images/eas-002a.png")


def fake(reply):
    def call(content, step_index, system, model, images_px):
        assert content[0] and "What to inspect:" in content[1]["text"], content[1]["text"]
        return json.dumps(reply), Usage(step_index, "fake", model, input_image_tokens=1), "end_turn"
    return call


def run():
    img = Image.open(IMG).convert("RGB")
    q = "Which circumstance boxes did driver B tick? Answer with the box numbers."
    r = anchor.answer(img, q, call=fake({"answer": "8", "box": [0.0, 0.48, 1.0, 0.52]}), model="m")
    steps = [s.step for s in r.route]
    assert steps == ["zoom", "answer"], steps
    assert r.answer == "8" and r.usage[0].provider == "local" and r.usage[1].provider == "fake"
    assert r.route[0].target == "anchor:ticks" and r.evidence_boxes, r.evidence_boxes
    # the box drawn across both mosaic columns maps back to two page boxes: B's column and the row numbers
    xs = sorted(round(b.box[0], 2) for b in r.evidence_boxes)
    assert len(xs) == 2 and xs[0] < 0.2 and xs[1] > 0.85, xs

    r = anchor.answer(img, "In the sketch, which vehicle was hit from behind? Answer A or B.", call=fake({"answer": "A"}))
    assert r.route[0].target == "anchor:sketch" and r.answer == "A"

    r = anchor.answer(img, "What colour is vehicle A?", call=fake({"answer": "x"}))
    assert [s.step for s in r.route] == ["fallback"] and r.answer is None
    # deskew: on a page tilted by 4°, the answer box must land on B's row-8 tick of the TILTED page
    import math
    tilted = img.rotate(4, resample=Image.BICUBIC, expand=False, fillcolor=(255, 255, 255))
    r = anchor.answer(tilted, q, call=fake({"answer": "8", "box": [0.55, 0.475, 1.0, 0.505]}), model="m")
    assert "deskew" in r.route[0].target and r.answer == "8", r.route[0].target
    w, h = img.size
    gx, gy = 0.9165 * w - w / 2, 0.4964 * h - h / 2  # gold B tick (row 8) centre, clean page, from the centre
    a = math.radians(4)
    ex, ey = (w / 2 + gx * math.cos(a) + gy * math.sin(a)) / w, (h / 2 - gx * math.sin(a) + gy * math.cos(a)) / h
    b = max(r.evidence_boxes, key=lambda e: e.box[0]).box
    assert abs((b[0] + b[2]) / 2 - ex) < 0.02 and abs((b[1] + b[3]) / 2 - ey) < 0.02, (b, ex, ey)
    print("anchor: 4 checks passed")


if __name__ == "__main__":
    run()
