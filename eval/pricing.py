"""Per-model prices and cost computation.

Prices are USD per 1M tokens, Anthropic first-party list prices as of 2026-11-03 (claude-api skill table).
Cache write = 1.25x input, cache read = 0.1x input unless the model lists its own cache-read price.
Verify against the provider's pricing page before quoting numbers in the pitch.
"""
from __future__ import annotations

from .schema import Usage

# model -> (input, output, cache_read or None)
PRICES: dict[str, tuple[float, float, float | None]] = {
    "claude-fable-5-2": (8.00, 40.00, 0.20),
    "claude-opus-5-5": (4.00, 20.00, 0.20),
    "claude-opus-5": (5.00, 25.00, None),
    "claude-opus-4-8": (5.00, 25.00, None),
    "claude-sonnet-5-5": (2.00, 10.00, 0.10),
    "claude-sonnet-5": (2.00, 10.00, None),
    "claude-haiku-5-5": (0.10, 0.50, None),  # prompts <= 100K tokens
}
CACHE_WRITE_MULT = 1.25
CACHE_READ_MULT = 0.10


def cost_usd(u: Usage) -> float:
    """Cost of one call. Unknown models return 0.0 and mark the record as estimated."""
    if u.model not in PRICES:
        u.estimated = True
        u.note = (u.note or "") + f" [no price for {u.model}]"
        return 0.0
    p_in, p_out, p_cr = PRICES[u.model]
    p_cr = p_cr if p_cr is not None else p_in * CACHE_READ_MULT
    uncached_in = u.input_text_tokens + u.input_image_tokens
    return (
        uncached_in * p_in
        + u.cache_write_tokens * p_in * CACHE_WRITE_MULT
        + u.cache_read_tokens * p_cr
        + u.output_tokens * p_out
    ) / 1e6
