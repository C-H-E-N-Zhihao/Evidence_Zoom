"""Counterfactual full-image baseline for the UI cost meter.

Prices come from eval/pricing.py so app and eval show the same numbers.
Image-token counts are ESTIMATES (~ w*h/750 after downscaling) until
eval/billing_probe.py has measured the real backend.
"""
import os

from eval.pricing import cost_usd as _price
from eval.schema import Usage

MODEL = os.getenv("APP_MODEL", "claude-opus-5-5")
MAX_LONG_SIDE = 1568
MAX_PIXELS = 1_150_000


def billed_size(w: int, h: int) -> tuple[int, int]:
    scale = min(1.0, MAX_LONG_SIDE / max(w, h))
    w2, h2 = w * scale, h * scale
    if w2 * h2 > MAX_PIXELS:
        s = (MAX_PIXELS / (w2 * h2)) ** 0.5
        w2, h2 = w2 * s, h2 * s
    return int(w2), int(h2)


def image_tokens(w: int, h: int) -> int:
    bw, bh = billed_size(w, h)
    return max(1, round(bw * bh / 750))


def price(u: Usage) -> float:
    u.cost_usd = _price(u)
    return u.cost_usd


def full_image_baseline(w: int, h: int, question_tokens: int, output_tokens: int,
                        question_index: int) -> dict:
    """Cost of answering this question by sending the full image instead.

    Cached variant: cache write on the first question about this image, reads after.
    """
    img = image_tokens(w, h)
    unc = Usage(0, "anthropic", MODEL, input_text_tokens=question_tokens,
                input_image_tokens=img, output_tokens=output_tokens, estimated=True)
    cac = Usage(0, "anthropic", MODEL, input_text_tokens=question_tokens,
                output_tokens=output_tokens, estimated=True,
                cache_write_tokens=img if question_index == 0 else 0,
                cache_read_tokens=img if question_index > 0 else 0)
    return {"image_tokens": img, "uncached_usd": price(unc), "cached_usd": price(cac),
            "model": MODEL, "estimated": True}
