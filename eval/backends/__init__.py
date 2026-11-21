"""Backend selection by model string.

    "claude-opus-5-5"                 -> Anthropic API      (ANTHROPIC_API_KEY)
    "or:google/gemini-2.5-flash"      -> OpenRouter         (OPENROUTER_API_KEY)  [model id as listed on openrouter.ai]
    "local:Qwen/Qwen2.5-VL-7B-Instruct" -> OpenAI-compatible server, e.g. vLLM on RCP (OPENAI_BASE_URL), cost $0

Every backend exposes image_block(img, cache=...) and call(content, step_index=..., system=..., model=...,
images_px=...) -> (text, Usage, stop_reason).
"""
from __future__ import annotations

from types import SimpleNamespace


def get(model: str):
    """Return (backend_module_like, bare_model_id)."""
    if model.startswith("or:") or model.startswith("local:"):
        from . import openrouter_backend as orb

        local = model.startswith("local:")
        bare = model.split(":", 1)[1]
        ns = SimpleNamespace(
            image_block=lambda img, cache=False, **kw: orb.image_block(img, cache=cache, **kw),
            call=lambda content, **kw: orb.call(content, **{**kw, "model": bare, "local": local}),
        )
        return ns, bare
    from . import anthropic_backend as ab

    return ab, model
