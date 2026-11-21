"""Thin Claude wrapper that returns (text, Usage) for every call.

Credentials: ANTHROPIC_API_KEY from the environment (never commit it). Keep it in a git-ignored .env.

Token split: the API reports one `input_tokens` number for text + images. When the caller passes
`image_token_hint` (from billing_probe.py's measured table), we split it into image and text parts and set
`note="image/text split from probe"`. Cost does not depend on the split.
"""
from __future__ import annotations

import base64
import io
import time
from typing import Optional

from PIL import Image

from ..pricing import cost_usd
from ..schema import Usage

DEFAULT_MODEL = "claude-opus-5-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"

_client = None


def client():
    """Lazy import, so the mock pipeline and metrics run without the anthropic package installed."""
    global _client
    if _client is None:
        import anthropic

        _client = anthropic.Anthropic()
    return _client


def image_block(img: Image.Image, fmt: str = "PNG", cache: bool = False) -> dict:
    """Encode a PIL image as-is (no resizing here: the caller decides the pixel budget)."""
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format=fmt)
    block = {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": f"image/{fmt.lower()}",
            "data": base64.standard_b64encode(buf.getvalue()).decode("utf-8"),
        },
    }
    if cache:
        block["cache_control"] = {"type": "ephemeral"}
    return block


def call(
    content: list[dict],
    *,
    step_index: int,
    system: Optional[str] = None,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 2048,
    effort: str = "low",
    images_px: Optional[list[list[int]]] = None,
    image_token_hint: Optional[int] = None,
    fallbacks: bool = True,
) -> tuple[str, Usage, str]:
    """One user turn. Returns (text, usage, stop_reason).

    `fallbacks=True` enables Anthropic's server-side refusal fallback; the served model is read from the
    response so the price matches the model that actually ran.
    """
    kwargs: dict = dict(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": content}],
        output_config={"effort": effort},
    )
    if system:
        kwargs["system"] = system
    t0 = time.perf_counter()
    if fallbacks:
        resp = client().beta.messages.create(betas=[FALLBACK_BETA], fallbacks="default", **kwargs)
    else:
        resp = client().messages.create(**kwargs)
    latency_ms = (time.perf_counter() - t0) * 1000

    text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
    u = resp.usage
    in_tok = u.input_tokens or 0
    img_tok = min(image_token_hint, in_tok) if image_token_hint is not None else 0
    usage = Usage(
        step_index=step_index,
        provider="anthropic",
        model=resp.model,
        input_text_tokens=in_tok - img_tok,
        input_image_tokens=img_tok,
        output_tokens=u.output_tokens or 0,
        cache_read_tokens=getattr(u, "cache_read_input_tokens", 0) or 0,
        cache_write_tokens=getattr(u, "cache_creation_input_tokens", 0) or 0,
        latency_ms=latency_ms,
        image_px=images_px,
        note="image/text split from probe" if image_token_hint is not None else None,
    )
    usage.cost_usd = cost_usd(usage)
    return text, usage, resp.stop_reason


def count_tokens(content: list[dict], model: str = DEFAULT_MODEL) -> int:
    """Free token count for a single user turn (used by billing_probe.py)."""
    r = client().messages.count_tokens(model=model, messages=[{"role": "user", "content": content}])
    return r.input_tokens
