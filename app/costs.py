"""Cost estimates for the counterfactual full-image baseline shown in the UI.

ALL numbers here are ESTIMATES (unverified, see message 008 / guanyu's billing
check). Replace with measured token counts once a backend is chosen.
"""
import os

# Claude-style image billing: ~ (w*h)/750 tokens after downscaling so the long
# side <= 1568 px and total pixels <= ~1.15 MP.  Unverified.
MAX_LONG_SIDE = 1568
MAX_PIXELS = 1_150_000

PRICE_IN_PER_MTOK = float(os.getenv("PRICE_IN_PER_MTOK", "3.0"))
PRICE_OUT_PER_MTOK = float(os.getenv("PRICE_OUT_PER_MTOK", "15.0"))
CACHE_READ_FACTOR = float(os.getenv("CACHE_READ_FACTOR", "0.1"))
CACHE_WRITE_FACTOR = float(os.getenv("CACHE_WRITE_FACTOR", "1.25"))


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


def cost_usd(input_tokens: float, output_tokens: float) -> float:
    return (input_tokens * PRICE_IN_PER_MTOK + output_tokens * PRICE_OUT_PER_MTOK) / 1e6


def full_image_baseline(w: int, h: int, question_tokens: int, output_tokens: int,
                        question_index: int) -> dict:
    """Cost of answering this question by sending the full image.

    question_index is 0 for the first question on this image; the cached
    variant pays a cache write on the first question and cache reads after.
    """
    img = image_tokens(w, h)
    uncached = cost_usd(img + question_tokens, output_tokens)
    factor = CACHE_WRITE_FACTOR if question_index == 0 else CACHE_READ_FACTOR
    cached = cost_usd(img * factor + question_tokens, output_tokens)
    return {
        "image_tokens": img,
        "uncached_usd": uncached,
        "cached_usd": cached,
        "estimated": True,
    }
