"""Shared contract between pipelines, the app and the eval harness.

Stdlib only, so `app/` and `pipeline/` can import it without extra dependencies:

    from eval.schema import PipelineResult, EvidenceBox, RouteStep, Usage

Coordinates: every box is [x0, y0, x1, y1], normalized to 0-1 on the ORIGINAL full-resolution image
(page `page`), origin top-left. Pipelines that work on crops must map boxes back before returning.
See eval/INTERFACE.md for the field semantics.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal, Optional

SCHEMA_VERSION = "0.1"

Box = list[float]  # [x0, y0, x1, y1], normalized 0-1 on the original image
EvidenceSource = Literal["ocr", "native_text", "overview", "zoom", "full_image", "gold_crop", "model_box"]
StepKind = Literal["ocr", "native_text", "overview", "zoom", "answer", "fallback", "abstain", "index", "route"]
EvidenceType = Literal["text", "layout", "visual", "mixed"]


@dataclass
class EvidenceBox:
    box: Box
    page: int = 0
    source: EvidenceSource = "model_box"
    label: Optional[str] = None


@dataclass
class RouteStep:
    step: StepKind
    target: Optional[str] = None  # e.g. grid cell "B3", or None
    box: Optional[Box] = None  # region inspected at this step (same convention as EvidenceBox.box)
    note: Optional[str] = None


@dataclass
class Usage:
    """One billed (or estimated) call. One record per API call, retries and fallbacks included."""

    step_index: int  # index into PipelineResult.route
    provider: str  # "anthropic", "openrouter", "local", ...
    model: str  # model that actually served the call (after any server-side fallback)
    input_text_tokens: int = 0
    input_image_tokens: int = 0
    output_tokens: int = 0  # includes thinking tokens when the provider bills them as output
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    estimated: bool = False  # True if any number above is not from the provider's response
    image_px: Optional[list[list[int]]] = None  # [[w, h], ...] of the images actually sent
    retry: bool = False
    note: Optional[str] = None


@dataclass
class PipelineResult:
    answer: Optional[str]  # None = abstained
    abstained: bool = False
    evidence_boxes: list[EvidenceBox] = field(default_factory=list)
    route: list[RouteStep] = field(default_factory=list)
    usage: list[Usage] = field(default_factory=list)
    pipeline: str = ""  # e.g. "full_image", "ocr_router@v1"
    question_id: Optional[str] = None
    image_id: Optional[str] = None
    error: Optional[str] = None
    schema_version: str = SCHEMA_VERSION

    # ---- helpers -------------------------------------------------------------------------
    def total_cost(self) -> float:
        return sum(u.cost_usd for u in self.usage)

    def total_latency_ms(self) -> float:
        return sum(u.latency_ms for u in self.usage)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "PipelineResult":
        d = dict(d)
        d["evidence_boxes"] = [EvidenceBox(**b) for b in d.get("evidence_boxes", [])]
        d["route"] = [RouteStep(**s) for s in d.get("route", [])]
        d["usage"] = [Usage(**u) for u in d.get("usage", [])]
        return cls(**d)


@dataclass
class EvalItem:
    """One labelled question. Stored one per line in eval/data/<set>/items.jsonl."""

    question_id: str
    image_id: str
    image_path: str  # relative to the items.jsonl file
    question: str
    answer: Optional[str]  # gold answer; None when unanswerable
    answerable: bool = True
    evidence_type: EvidenceType = "text"
    evidence_boxes: list[Box] = field(default_factory=list)  # gold, normalized, original image
    accepted_answers: list[str] = field(default_factory=list)  # extra exact-match variants
    pair_id: Optional[str] = None  # links counterfactual pairs (same form, different tick)
    source: str = "synthetic"  # "synthetic" | "real"
    notes: Optional[str] = None
