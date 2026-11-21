"""OpenRouter backend (one key, many vision models; AXA gives $10 credit per team).

Same contract as anthropic_backend.call(): returns (text, Usage, stop_reason).
Credentials: OPENROUTER_API_KEY from the environment (never commit it).
Also works for any OpenAI-compatible server, e.g. a local vLLM on RCP: set OPENAI_BASE_URL (and optionally
OPENAI_API_KEY) and use provider "local" so cost is $0 (see eval/backends/__init__.py).

Cost: OpenRouter reports the billed cost of each generation when usage accounting is requested
(`usage: {include: true}`). We read `usage.cost` when present (estimated=False); otherwise cost falls back to
eval/pricing.py and the record is marked estimated. Image tokens are not reported separately by most providers:
`input_image_tokens` is filled only from a probe hint, as in the Anthropic backend.
NOTE: field names follow OpenRouter's documented usage-accounting response; verify on the first real call.
"""
from __future__ import annotations

import base64
import io
import json
import os
import time
import urllib.request
from typing import Optional

from PIL import Image

from ..pricing import cost_usd
from ..schema import Usage

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def image_block(img: Image.Image, fmt: str = "PNG", detail: Optional[str] = None, cache: bool = False) -> dict:
    """OpenAI-style image part. `detail` ("low"/"high") matters for OpenAI models; others ignore it.
    NOTE: `cache` is IGNORED here (no cache_control is sent), so `full_image_cached@or:...` is billed uncached;
    eval.report flags such rows. Do not quote them as the cached baseline."""
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format=fmt)
    url = f"data:image/{fmt.lower()};base64," + base64.standard_b64encode(buf.getvalue()).decode()
    part: dict = {"type": "image_url", "image_url": {"url": url}}
    if detail:
        part["image_url"]["detail"] = detail
    return part


def _endpoint(local: bool) -> tuple[str, dict]:
    if local:
        base = os.environ.get("OPENAI_BASE_URL", "http://localhost:8000/v1").rstrip("/")
        headers = {"Authorization": f"Bearer {os.environ.get('OPENAI_API_KEY', 'none')}"}
        return base + "/chat/completions", headers
    return OPENROUTER_URL, {"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
                            "X-Title": "evidence-zoom-eval"}


def call(
    content: list[dict],
    *,
    step_index: int,
    system: Optional[str] = None,
    model: str,
    max_tokens: int = 1024,
    images_px: Optional[list[list[int]]] = None,
    image_token_hint: Optional[int] = None,
    local: bool = False,
    timeout_s: float = 120.0,
    **_ignored,
) -> tuple[str, Usage, str]:
    messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": content}]
    body: dict = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": 0}
    if not local:
        body["usage"] = {"include": True}
    url, headers = _endpoint(local)
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **headers})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout_s) as r:
        resp = json.loads(r.read())
    latency_ms = (time.perf_counter() - t0) * 1000
    if "error" in resp:
        raise RuntimeError(f"{resp['error']}")

    choice = resp["choices"][0]
    text = choice["message"].get("content") or ""
    u = resp.get("usage") or {}
    in_tok = int(u.get("prompt_tokens") or 0)
    img_tok = min(image_token_hint, in_tok) if image_token_hint is not None else 0
    cached = int((u.get("prompt_tokens_details") or {}).get("cached_tokens") or 0)
    usage = Usage(
        step_index=step_index,
        provider="local" if local else "openrouter",
        model=resp.get("model") or model,
        input_text_tokens=in_tok - img_tok - cached,
        input_image_tokens=img_tok,
        output_tokens=int(u.get("completion_tokens") or 0),
        cache_read_tokens=cached,
        latency_ms=latency_ms,
        image_px=images_px,
        note="image/text split from probe" if image_token_hint is not None else None,
        device="gpu" if local else None,
    )
    if local:
        usage.cost_usd = cost_usd(usage)  # $0 unless EVAL_GPU_USD_PER_HOUR is set (then estimated GPU time)
    elif u.get("cost") is not None:
        usage.cost_usd = float(u["cost"])
    else:
        usage.cost_usd = cost_usd(usage)
        usage.estimated = True
    stop = {"stop": "end_turn", "length": "max_tokens", "content_filter": "refusal"}.get(
        choice.get("finish_reason"), choice.get("finish_reason") or "")
    return text, usage, stop
