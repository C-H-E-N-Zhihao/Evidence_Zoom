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


def gpu_usd_per_hour() -> float:
    """Assumed hourly price of one self-hosted GPU, for pricing local model calls (EVAL_GPU_USD_PER_HOUR).

    Default 0: local calls are reported as $0 plus GPU-seconds. Set it to a cloud on-demand rate to show what the
    local route would cost on rented hardware; state the rate you used. One request at a time on one GPU makes
    latency ~ GPU time; batching would lower it, queueing/tunnel overhead raises it.
    """
    import os

    try:
        return float(os.environ.get("EVAL_GPU_USD_PER_HOUR", "0") or 0)
    except ValueError:
        return 0.0


def cost_usd(u: Usage) -> float:
    """Cost of one call. Local calls cost $0 (latency still counts). Unknown API models return 0.0 and are
    marked as estimated."""
    if u.provider == "local":
        rate = gpu_usd_per_hour()
        if u.device == "gpu" and rate > 0:
            u.estimated = True  # wall-clock latency x an assumed hourly rate, not a bill
            return u.latency_ms / 3.6e6 * rate
        return 0.0
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
