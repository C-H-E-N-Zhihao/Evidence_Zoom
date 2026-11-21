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
    print("anchor: 3 checks passed")


if __name__ == "__main__":
    run()
