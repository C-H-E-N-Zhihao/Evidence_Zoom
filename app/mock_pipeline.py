"""Mock pipeline returning the shared schema, so the UI can be built before
the real OCR / overview / zoom pipeline exists. Answers are FAKE.

Routing heuristic (mock only): questions that look textual stop at OCR;
everything else goes overview -> zoom on a grid cell -> answer.
"""
import hashlib
import random
import re
import time

from PIL import Image

from .costs import cost_usd, image_tokens
from .schema import Result

GRID = 4  # overview grid is GRID x GRID, cells A1..D4
TEXTUAL = re.compile(r"\b(number|id|date|name|policy|registration|address|plate|"
                     r"phone|written|insurer)\b", re.I)


def cell_box(col: int, row: int, n: int = GRID) -> list[float]:
    return [col / n, row / n, (col + 1) / n, (row + 1) / n]


def cell_name(col: int, row: int) -> str:
    return f"{'ABCDEFGH'[col]}{row + 1}"


def answer(image: Image.Image, question: str) -> Result:
    t0 = time.perf_counter()
    w, h = image.size
    rng = random.Random(hashlib.sha256(question.encode()).digest())
    q_tokens = max(8, len(question) // 4)
    textual = bool(TEXTUAL.search(question))

    route, usage, evidence = [], [], []

    # Step 0: OCR (local, no API cost in this mock).
    route.append({"step": "ocr", "target": None, "box": None,
                  "note": "OCR + layout over the full page (local)"})
    usage.append({"step_index": 0, "provider": "local", "model": "mock-ocr",
                  "input_text_tokens": 0, "input_image_tokens": 0,
                  "output_tokens": 0, "cached_tokens": 0,
                  "latency_ms": 40.0, "cost_usd": 0.0, "estimated": True})

    if textual:
        # Text router call: question + OCR text, answers directly.
        ocr_tokens = 600
        out = 40
        box = [round(rng.uniform(0.05, 0.5), 3), round(rng.uniform(0.05, 0.8), 3)]
        box += [round(box[0] + 0.3, 3), round(box[1] + 0.05, 3)]
        evidence.append({"page": 0, "box": box, "source": "ocr",
                         "label": "OCR span"})
        route.append({"step": "answer", "target": None, "box": box,
                      "note": "OCR was sufficient; no image tokens spent"})
        usage.append({"step_index": 1, "provider": "mock", "model": "mock-text",
                      "input_text_tokens": ocr_tokens + q_tokens,
                      "input_image_tokens": 0, "output_tokens": out,
                      "cached_tokens": 0, "latency_ms": 450.0,
                      "cost_usd": cost_usd(ocr_tokens + q_tokens, out),
                      "estimated": True})
        ans = "[mock] HM-0000-1234 (read from OCR)"
    else:
        # Router decides OCR is insufficient -> overview with labelled grid.
        ov_side = 384
        ov_tokens = image_tokens(ov_side, round(ov_side * h / w))
        route.append({"step": "overview", "target": None, "box": [0, 0, 1, 1],
                      "note": f"{ov_side}px overview with {GRID}x{GRID} labelled grid"})
        usage.append({"step_index": 1, "provider": "mock", "model": "mock-vlm",
                      "input_text_tokens": 300 + q_tokens,
                      "input_image_tokens": ov_tokens, "output_tokens": 20,
                      "cached_tokens": 0, "latency_ms": 900.0,
                      "cost_usd": cost_usd(300 + q_tokens + ov_tokens, 20),
                      "estimated": True})
        col, row = rng.randrange(GRID), rng.randrange(GRID)
        cbox = cell_box(col, row)
        name = cell_name(col, row)
        crop_w, crop_h = round(w / GRID), round(h / GRID)
        crop_tokens = image_tokens(crop_w, crop_h)
        route.append({"step": "zoom", "target": name, "box": cbox,
                      "note": f"native-resolution crop {crop_w}x{crop_h}px"})
        usage.append({"step_index": 2, "provider": "mock", "model": "mock-vlm",
                      "input_text_tokens": 120 + q_tokens,
                      "input_image_tokens": crop_tokens, "output_tokens": 60,
                      "cached_tokens": 0, "latency_ms": 1100.0,
                      "cost_usd": cost_usd(120 + q_tokens + crop_tokens, 60),
                      "estimated": True})
        # Evidence: a sub-box inside the zoomed cell.
        cw, ch = cbox[2] - cbox[0], cbox[3] - cbox[1]
        ex0 = cbox[0] + cw * rng.uniform(0.1, 0.5)
        ey0 = cbox[1] + ch * rng.uniform(0.1, 0.5)
        ebox = [round(ex0, 3), round(ey0, 3),
                round(ex0 + cw * 0.35, 3), round(ey0 + ch * 0.3, 3)]
        evidence.append({"page": 0, "box": ebox, "source": "zoom",
                         "label": f"inside {name}"})
        route.append({"step": "answer", "target": name, "box": ebox,
                      "note": "answered from zoomed crop"})
        ans = f"[mock] answer grounded in cell {name}"

    usage[0]["latency_ms"] = round((time.perf_counter() - t0) * 1000 + 40, 1)
    return {"answer": ans, "abstained": False, "evidence_boxes": evidence,
            "route": route, "usage": usage}
