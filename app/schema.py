"""Shared result contract (draft, see agent-messages/2026-11-21-008).

Every pipeline exposes  answer(image: PIL.Image.Image, question: str) -> Result.
Boxes are normalized [x0, y0, x1, y1] in 0-1 coordinates on the ORIGINAL image.
If eval/ or pipeline/ publishes a canonical schema, import it here instead.
"""
from typing import Literal, Optional, TypedDict

Box = list[float]  # [x0, y0, x1, y1], normalized


class EvidenceBox(TypedDict, total=False):
    page: int
    box: Box
    source: Literal["ocr", "overview", "zoom"]
    label: str


class RouteStep(TypedDict, total=False):
    step: Literal["ocr", "overview", "zoom", "answer", "fallback"]
    target: Optional[str]  # e.g. grid cell "B3"
    box: Optional[Box]
    note: str


class Usage(TypedDict, total=False):
    step_index: int
    provider: str
    model: str
    input_text_tokens: int
    input_image_tokens: int
    output_tokens: int
    cached_tokens: int
    latency_ms: float
    cost_usd: float
    estimated: bool  # True unless taken from a provider billing response


class Result(TypedDict, total=False):
    answer: Optional[str]
    abstained: bool
    evidence_boxes: list[EvidenceBox]
    route: list[RouteStep]
    usage: list[Usage]
