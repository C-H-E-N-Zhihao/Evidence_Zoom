"""Scoring. Pure functions over (EvalItem, PipelineResult) pairs.

Answer correctness is normalized exact match against `answer` + `accepted_answers` (a rubric/LLM judge can be
added later; it would be charged as a separate eval cost, not to the pipeline).
"""
from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from statistics import mean, median

from .schema import EvalItem, PipelineResult


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9]+", " ", s.lower())
    return " ".join(s.split())


def answer_correct(item: EvalItem, res: PipelineResult) -> bool:
    if not item.answerable:
        return res.abstained
    if res.abstained or res.answer is None:
        return False
    golds = [norm(g) for g in [item.answer, *item.accepted_answers] if g]
    pred = norm(res.answer)
    return any(pred == g or (g and re.search(rf"\b{re.escape(g)}\b", pred)) for g in golds)


def _lev(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def anls(item: EvalItem, res: PipelineResult, tau: float = 0.5) -> float:
    """Average Normalized Levenshtein Similarity, the DocVQA metric (Biten et al., 2019), for one item.

    max over gold variants of 1 - NL(pred, gold), set to 0 when NL >= tau; strings lower-cased and whitespace-collapsed.
    Our extension for unanswerable items (not in DocVQA): 1 if the pipeline abstained, else 0. Abstaining on an
    answerable item scores 0. Report it next to `accuracy` (substring match), which is more lenient on long answers.
    """
    if not item.answerable:
        return 1.0 if res.abstained else 0.0
    if res.abstained or res.answer is None:
        return 0.0
    pred = " ".join(res.answer.lower().split())
    best = 0.0
    for g in [item.answer, *item.accepted_answers]:
        if not g:
            continue
        g = " ".join(g.lower().split())
        nl = _lev(pred, g) / max(len(pred), len(g), 1)
        best = max(best, 1.0 - nl if nl < tau else 0.0)
    return best


def _to_float(text: str) -> float | None:
    try:
        if text.endswith("%"):
            return float(text.rstrip("%")) / 100.0
        return float(text)
    except ValueError:
        return None


def relaxed_accuracy(item: EvalItem, res: PipelineResult, max_relative_change: float = 0.05) -> float:
    """ChartQA relaxed accuracy, following Pix2Struct's `relaxed_correctness` (pix2struct/metrics.py).

    Parseable numbers (with an optional trailing %) match within 5 % relative change; otherwise the strings match
    ignoring case. Units and thousands separators are NOT stripped (codex-guanyu, fa568a3). Our only deviation:
    outer whitespace is stripped. Max over `answer` + `accepted_answers`. Unanswerable items: 1 if abstained.
    """
    if not item.answerable:
        return 1.0 if res.abstained else 0.0
    if res.abstained or res.answer is None:
        return 0.0
    pred = res.answer.strip()
    for g in [item.answer, *item.accepted_answers]:
        if not g:
            continue
        g = g.strip()
        pf, gf = _to_float(pred), _to_float(g)
        if pf is not None and gf:
            if abs(pf - gf) / abs(gf) <= max_relative_change:
                return 1.0
        elif pred.lower() == g.lower():
            return 1.0
    return 0.0


def iou(a: list[float], b: list[float]) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def evidence_iou(item: EvalItem, res: PipelineResult) -> float | None:
    """Best IoU between any predicted and any gold box; None when the item has no gold box."""
    if not item.evidence_boxes:
        return None
    if not res.evidence_boxes:
        return 0.0
    return max(iou(p.box, g) for p in res.evidence_boxes for g in item.evidence_boxes)


def evidence_hit(item: EvalItem, res: PipelineResult, thr: float = 0.3) -> bool | None:
    v = evidence_iou(item, res)
    return None if v is None else v >= thr


def _area(b: list[float]) -> float:
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def _inter(a: list[float], b: list[float]) -> float:
    return max(0.0, min(a[2], b[2]) - max(a[0], b[0])) * max(0.0, min(a[3], b[3]) - max(a[1], b[1]))


def zoom_coverage(item: EvalItem, res: PipelineResult) -> float | None:
    """Fraction of the gold evidence area inside the regions the pipeline zoomed into (route steps with
    step == "zoom" and a box). None when the item has no gold box or the pipeline did not zoom.

    Separates "selected the wrong region" from "selected the right region but misread it". Boxes of overlapping
    zoom steps are not de-duplicated, so the value is capped at 1 per gold box. For mosaics, the route box is the
    bounding box of the selection, so coverage is an upper bound there.
    """
    zooms = [s.box for s in res.route if s.step == "zoom" and s.box]
    if not item.evidence_boxes or not zooms:
        return None
    covered = sum(min(_area(g), sum(_inter(g, z) for z in zooms)) for g in item.evidence_boxes)
    total = sum(_area(g) for g in item.evidence_boxes)
    return covered / total if total > 0 else None


def summarize(pairs: list[tuple[EvalItem, PipelineResult]]) -> dict:
    """Overall and per-evidence-type metrics for one pipeline."""
    groups: dict[str, list] = defaultdict(list)
    for it, r in pairs:
        groups["all"].append((it, r))
        groups[it.evidence_type].append((it, r))
    out = {}
    for g, ps in groups.items():
        correct = [answer_correct(i, r) for i, r in ps]
        hits = [h for h in (evidence_hit(i, r) for i, r in ps) if h is not None]
        ious = [v for v in (evidence_iou(i, r) for i, r in ps) if v is not None]
        joint = [answer_correct(i, r) and bool(evidence_hit(i, r)) for i, r in ps if i.evidence_boxes]
        unans = [(i, r) for i, r in ps if not i.answerable]
        covs = [c for c in (zoom_coverage(i, r) for i, r in ps) if c is not None]
        zoomed = [(i, r) for i, r in ps if any(s.step == "zoom" for s in r.route)]
        costs = [r.total_cost() for _, r in ps]
        lats = [r.total_latency_ms() for _, r in ps]
        # 190 (token-saving bot): cloud = API calls (device None, provider not "local"); local = OCR/self-hosted only
        is_cloud = lambda u: u.device is None and u.provider != "local"
        tok = lambda u: u.input_image_tokens + u.input_text_tokens + u.cache_read_tokens + u.output_tokens
        cloud = [[u for u in r.usage if is_cloud(u)] for _, r in ps]
        cloud_tok = sum(tok(u) for us in cloud for u in us)
        local_tok = sum(tok(u) for _, r in ps for u in r.usage if not is_cloud(u))
        n_correct = sum(correct)
        out[g] = {
            "n": len(ps),
            "accuracy": mean(correct) if correct else None,
            "anls": mean(anls(i, r) for i, r in ps) if ps else None,
            "relaxed_accuracy": mean(relaxed_accuracy(i, r) for i, r in ps) if ps else None,
            "evidence_hit@0.3": mean(hits) if hits else None,
            "evidence_iou_mean": mean(ious) if ious else None,
            "joint_answer_evidence": mean(joint) if joint else None,
            "zoom_rate": len(zoomed) / len(ps),
            "zoom_covers_gold@0.9": mean(c >= 0.9 for c in covs) if covs else None,
            "zoom_coverage_mean": mean(covs) if covs else None,
            "acc_given_zoom_covers": (mean(answer_correct(i, r) for i, r in zoomed
                                           if (zoom_coverage(i, r) or 0) >= 0.9)
                                      if any((zoom_coverage(i, r) or 0) >= 0.9 for i, r in zoomed) else None),
            "abstain_rate": mean(r.abstained for _, r in ps),
            "correct_abstain_rate": mean(r.abstained for _, r in unans) if unans else None,
            "errors": sum(r.error is not None and r.error != "refusal" for _, r in ps),
            "cost_usd_total": sum(costs),
            "cost_usd_mean": mean(costs) if costs else 0.0,
            "latency_ms_median": median(lats) if lats else 0.0,
            "calls": sum(len(r.usage) for _, r in ps),
            "input_image_tokens": sum(u.input_image_tokens for _, r in ps for u in r.usage),
            "input_text_tokens": sum(u.input_text_tokens for _, r in ps for u in r.usage),
            "cache_read_tokens": sum(u.cache_read_tokens for _, r in ps for u in r.usage),
            "output_tokens": sum(u.output_tokens for _, r in ps for u in r.usage),
            "gpu_seconds": sum(u.latency_ms for _, r in ps for u in r.usage if u.device == "gpu") / 1000,
            "any_estimated": any(u.estimated for _, r in ps for u in r.usage),
            # 190 counts (codex token-score): every outcome counted, nothing hidden
            "correct": n_correct,
            "answered_locally": sum(1 for (_, r), us in zip(ps, cloud) if not us and not r.abstained),
            "cloud_escalations": sum(1 for us in cloud if us),
            "handoffs": sum(r.abstained for _, r in ps),  # abstain = hand off to a human
            "handoffs_on_answerable": sum(r.abstained for i, r in ps if i.answerable),
            "wrong_answers": sum(1 for (i, r), ok in zip(ps, correct) if not ok and not r.abstained),
            "cloud_tokens_total": cloud_tok,  # input image + text + cache reads + output; see input/output fields above
            "local_tokens_total": local_tok,
            "cloud_tokens_per_correct": cloud_tok / n_correct if n_correct else None,
            "cost_usd_per_correct": sum(costs) / n_correct if n_correct else None,
        }
    return out


def cost_curve(pairs: list[tuple[EvalItem, PipelineResult]], index_cost_per_image: float = 0.0) -> list[dict]:
    """Mean cumulative cost vs. number of questions asked about one image (amortization chart).

    Questions are taken in dataset order per image; `index_cost_per_image` is charged once at q=1
    (for pipelines that build a reusable index). Cache effects are already inside the measured usage.
    """
    by_img: dict[str, list[float]] = defaultdict(list)
    for it, r in pairs:
        by_img[it.image_id].append(r.total_cost())
    max_q = max((len(v) for v in by_img.values()), default=0)
    curve = []
    for q in range(1, max_q + 1):
        cums = [index_cost_per_image + sum(v[:q]) for v in by_img.values() if len(v) >= q]
        curve.append({"questions": q, "mean_cum_cost_usd": mean(cums), "n_images": len(cums)})
    return curve
