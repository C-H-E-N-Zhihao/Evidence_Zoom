"""Counterfactual full-image baseline for the UI cost meter.

Prices come from eval/pricing.py so app and eval show the same numbers.
Image-token counts are still ESTIMATES, but CALIBRATED on billed usage (eval/results/token_calibration.json,
paid sweep 2026-11-21, `python -m eval.calibrate_tokens`): Claude 5.5 via OpenRouter bills ~1 token per
800 px with NO downscale up to 1700x2200 (billed 4,920 tokens for that page; the old w*h/750-after-1568-px
estimate gave 1,531). Text: ~247 tokens of prompt per call (Sonnet fit intercept, residual < 1%).
"""
import os

from eval.pricing import cost_usd as _price
from eval.schema import Usage

# Full-page reference model: the strong model of the billed comparison (paid sweep: Sonnet 5.5 page vs router).
MODEL = os.getenv("APP_MODEL", "claude-sonnet-5-5")
PIXELS_PER_TOKEN = 800.0  # token_calibration.json: Sonnet 800.4, Haiku 815.1
TEXT_BASE_TOKENS = 247  # token_calibration.json: Sonnet text_base 247.3 (system prompt + question + wrapper)


def billed_size(w: int, h: int) -> tuple[int, int]:
    """No downscale observed in billing up to 1700x2200 (3.74 MP); larger images are unverified."""
    return int(w), int(h)


def image_tokens(w: int, h: int) -> int:
    bw, bh = billed_size(w, h)
    return max(1, round(bw * bh / PIXELS_PER_TOKEN))


def price(u: Usage) -> float:
    u.cost_usd = _price(u)
    return u.cost_usd


def full_image_baseline(w: int, h: int, question_tokens: int, output_tokens: int,
                        question_index: int) -> dict:
    """Cost of answering this question by sending the full image instead.

    Cached variant: cache write on the first question about this image, reads after.
    """
    img = image_tokens(w, h)
    q = max(8, question_tokens)  # the question itself
    prompt = max(TEXT_BASE_TOKENS, q)  # system prompt + question + wrapper, calibrated
    unc = Usage(0, "anthropic", MODEL, input_text_tokens=prompt,
                input_image_tokens=img, output_tokens=output_tokens, estimated=True)
    # Cached: image AND system prompt sit in the cache (billed sweep: cache_read 4,895 = page + prompt, only the
    # ~25 question tokens uncached, $0.00098/q on Sonnet); write on the first question about an image.
    cached = img + prompt - q
    cac = Usage(0, "anthropic", MODEL, input_text_tokens=q, output_tokens=output_tokens, estimated=True,
                cache_write_tokens=cached if question_index == 0 else 0,
                cache_read_tokens=cached if question_index > 0 else 0)
    return {"image_tokens": img, "uncached_usd": price(unc), "cached_usd": price(cac),
            "model": MODEL, "estimated": True}
