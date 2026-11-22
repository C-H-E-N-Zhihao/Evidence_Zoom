"""General vision assistant route: OCR text first, pixels only when needed (owner: claude-andrew-b, message 145).

For any image (homework, worksheets, textbook pages, receipts, forms we did not configure):

1. **OCR** the page locally (Apple Vision, $0), number its lines.
2. **Text call:** send only the numbered OCR lines (no image) to the model. It answers from text and cites the line
   ids it used (their OCR boxes become the evidence), or says it needs the image (a diagram, a tick or circle,
   handwriting OCR missed, colour, position) and names the lines nearest to what must be looked at.
3. **Pixel call (only if asked for):** crop a band around the named lines (full width, from just above the first
   line to well below the last, because diagrams and marks usually sit next to or below their text), or send the
   whole page if no line was named. One `pipeline.visual.zoom_answer` call, same box mapping as the claims route.

    answer(image, question, prior=None, model=None, call=None) -> eval.schema.PipelineResult
    eval:  --pipelines pipeline.general:factory
"""
from __future__ import annotations

import json
import os
from typing import Optional

from eval.schema import EvidenceBox, PipelineResult, RouteStep, Usage

MAX_LINES = 220
# Size rule (realdocs_v1, d3ade46): for a small image, sending the image costs less than sending its OCR text plus the
# text step's prompt and longer JSON answer. Image tokens ~ w*h/800 (app/costs.py calibration); the text step costs its
# text (~chars/4) plus about TEXT_STEP_OVERHEAD input-equivalent tokens (system prompt ~400 + extra output ~120 tokens
# priced ~5x input). If the image is cheaper, skip the text step and send the page.
TEXT_STEP_OVERHEAD = 1000
# Whole-page resolution (realdocs_v2 resolution frontier, 9792e2c / ca24f86, approved): DocVQA scans keep full ANLS
# down to a 1024 px long side (short side ~790 px) at about a third of the full-size cost, and drop at 768 px; tall
# infographics lose detail as soon as they are shrunk. Rule: keep the short side >= MIN_SHORT (768 px) and the long side
# >= MIN_LONG (1024 px), never upscale, cap at MAX_LONG (2400 px). A normal page goes to ~1024 px, a tall receipt keeps
# enough width to read, an infographic stays near full size. (The rule is set from those runs; receipts are measured
# separately.)
MIN_SHORT, MIN_LONG, MAX_LONG = 768, 1024, 2400


def _page_side(image) -> int:
    w, h = image.size
    lo, hi = min(w, h), max(w, h)
    want = max(MIN_LONG, round(MIN_SHORT * hi / max(1, lo)))
    return int(min(hi, MAX_LONG, want))


CONTENT_MARGIN = 0.03  # page fraction kept around the OCR text extent


def _content_spans(image, lines):
    """Rows/cols of the area that holds text (OCR line boxes plus a margin): a phone photo of a receipt is mostly
    table or background, so downscaling the whole frame wastes pixels. Whole frame if OCR found nothing or the text
    already fills most of it."""
    if not lines:
        return [(0.0, 1.0)], [(0.0, 1.0)]
    x0 = max(0.0, min(s["box"][0] for s in lines) - CONTENT_MARGIN)
    y0 = max(0.0, min(s["box"][1] for s in lines) - CONTENT_MARGIN)
    x1 = min(1.0, max(s["box"][2] for s in lines) + CONTENT_MARGIN)
    y1 = min(1.0, max(s["box"][3] for s in lines) + CONTENT_MARGIN)
    if (x1 - x0) * (y1 - y0) > 0.85:
        return [(0.0, 1.0)], [(0.0, 1.0)]
    return [(y0, y1)], [(x0, x1)]


# Model-free question -> region crop (message 190, idea 1). Words of the question, plus synonyms for fields a
# customer-service bot is asked about, are matched against the OCR lines; a band around the best lines is sent first.
# If the model abstains on the band, the cropped page follows. Off unless GENERAL_KEYWORD_CROP=1 (being measured).
SYN = {
    "total": "total amount sum due pay payable paid balance grand ttc betrag montant summe", "amount": "total amount sum due",
    "spending": "total amount sum paid", "spent": "total amount sum paid", "cost": "total price amount cost",
    "price": "price prix preis cost amount", "tax": "tax vat tva mwst gst", "vat": "vat tax tva mwst",
    "change": "change rendu", "discount": "discount rabais rebate reduction", "date": "date datum",
    "when": "date datum time", "time": "time heure zeit", "order": "order invoice receipt number no id",
    "invoice": "invoice facture rechnung number no", "number": "number no nr id", "phone": "phone tel telephone",
    "address": "address adresse street rue", "email": "email mail", "name": "name nom", "card": "card visa mastercard",
}
_STOP = set("what which who whom whose when where why how is are was were the a an of in on for to this that these those "
            "does did do with from by at and or it its be been as much many there their your my our please tell me".split())


def _norm(t: str) -> str:
    import unicodedata

    return "".join(c for c in unicodedata.normalize("NFKD", t.lower()) if not unicodedata.combining(c))


def _keyword_band(question, lines):
    import re

    words = [w for w in re.findall(r"[a-z0-9]+", _norm(question)) if len(w) >= 3 and w not in _STOP]
    terms = set(words)
    for w in words:
        terms |= set(SYN.get(w, "").split())
    if not terms:
        return None
    scored = []
    for s in lines:
        toks = set(re.findall(r"[a-z0-9]+", _norm(s["text"])))
        hit = sum(1 for t in terms if t in toks or (len(t) >= 5 and any(t in k for k in toks)))
        hit += sum(1 for w in words if w in toks)  # the customer's own words count double
        if hit:
            scored.append((hit, s))
    if not scored:
        return None
    best = max(h for h, _ in scored)
    top = [s for h, s in scored if h == best][:3]
    y0 = min(s["box"][1] for s in top); y1 = max(s["box"][3] for s in top)
    lh = max(0.01, sum(s["box"][3] - s["box"][1] for s in top) / len(top))
    return max(0.0, y0 - 2.5 * lh), min(1.0, y1 + 2.5 * lh), best


# Personal data redaction (message 214, audit 215): on the PAGE path only, lines that local OCR reads as card (Luhn-valid
# or masked), IBAN, email, phone or AHV numbers are blacked out unless the question asks for that field. Pattern-based,
# not a guarantee: configured-form crops and text OCR did not read go out unredacted. Off in eval runs; on in the app.
PII = {
    "card": (r"__luhn__|\b(?:x{4,}|\*{4,})[ -]?\d{4}\b", r"card|visa|mastercard|amex|carte|karte"),
    "iban": (r"\b[a-z]{2}\d{2}(?: ?[a-z0-9]{4}){3,7}\b", r"iban|account|bank|konto|compte"),
    "email": (r"[\w.+-]+@[\w-]+\.[\w.]+", r"e-?mail|mail"),
    "phone": (r"(?:\+|00)\d{2}[ \d]{8,14}|\b0\d{2}[ ./-]?\d{3}[ ./-]?\d{2}[ ./-]?\d{2}\b", r"phone|tel|call|number to"),
    "ahv": (r"\b756[.\s]?\d{4}[.\s]?\d{4}[.\s]?\d{2}\b", r"ahv|avs|social|insurance number|ssn"),
}


def _luhn(run: str) -> bool:
    d = [int(c) for c in run if c.isdigit()]
    if not 13 <= len(d) <= 19:
        return False
    tot = sum(x if i % 2 == 0 else (x * 2 - 9 if x * 2 > 9 else x * 2) for i, x in enumerate(reversed(d)))
    return tot % 10 == 0


def _redact(image, question, lines):
    """(image copy with personal-data lines blacked out, list of redacted kinds). Same image if nothing found."""
    import re

    q = _norm(question)
    boxes, kinds = [], []
    for kind, (pat, ask) in PII.items():
        if re.search(ask, q):
            continue  # the customer asked about this field: keep it visible
        for s in lines:
            t = _norm(s["text"])
            if kind in ("card", "phone") and re.search(
                    r"invoice|facture|rechnung|order|commande|transaction|trx|receipt|recu|ticket|n[o°]\b|nr\b", t):
                continue  # number-only detectors skip document identifiers (audit 215); email/IBAN/AHV stay on (codex)
            hit = re.search(pat.replace("__luhn__|", ""), t) if "__luhn__" in pat else re.search(pat, t)
            if not hit and "__luhn__" in pat:
                hit = any(_luhn(m) for m in re.findall(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)", t))
            if hit:
                boxes.append(s["box"]); kinds.append(kind)
    if not boxes:
        return image, []
    from PIL import ImageDraw

    out = image.convert("RGB").copy()
    d = ImageDraw.Draw(out)
    W, H = out.size
    for x0, y0, x1, y1 in boxes:
        d.rectangle([x0 * W - 2, y0 * H - 2, x1 * W + 2, y1 * H + 2], fill=(0, 0, 0))
    return out, sorted(set(kinds))


def _page_call(image, question, res, model, call, lines, look_for="the evidence for the question"):
    """The whole page as one image: cropped to the text area, then downscaled by _page_side. With
    GENERAL_KEYWORD_CROP=1, a band around the OCR lines that match the question is tried first."""
    from pipeline.visual import zoom_answer

    if os.environ.get("OCR_FIELDS") == "1" and lines:
        # Zero-token field answers (message 216): a printed label and the number on its row, read by local OCR, no
        # model. Only the fields that were 98-100% precise on receipts_v1 (dev: change, item price) or answers that pass
        # the cash - change = total consistency check (confidence >= 0.95); everything else continues to the model.
        try:
            from pipeline.ocr_fields import extract_from_spans

            ex = extract_from_spans(lines, question)
            if ex.get("answer") and ((ex.get("field") in ("change", "item") and ex.get("confidence", 0) >= 0.9)
                                     or ex.get("confidence", 0) >= 0.95):
                res.answer, res.abstained = str(ex["answer"]), False
                if ex.get("box"):
                    res.evidence_boxes = [EvidenceBox([round(v, 4) for v in ex["box"]], source="ocr",
                                                      label=str(ex.get("line") or "")[:60])]
                res.route.append(RouteStep("answer", note=f"read by local OCR from the '{ex.get('field')}' row, no model "
                                                          f"(confidence {ex.get('confidence')})"))
                return res
        except Exception:
            pass
    if os.environ.get("REDACT_PII") == "1" and lines:
        image, kinds = _redact(image, question, lines)
        if kinds:
            res.route.append(RouteStep("ocr", note=f"redacted before sending: {', '.join(kinds)}"))

    if os.environ.get("GENERAL_KEYWORD_CROP") == "1" and lines:
        kb = _keyword_band(question, lines)
        if kb:
            rows_c, cols_c = _content_spans(image, lines)
            y0, y1, score = kb
            res.route.append(RouteStep("fallback", target="image", note=f"keyword band (score {score})"))
            res = zoom_answer(image, question, [(y0, y1)], cols_c, prior=res, model=model, look_for=look_for,
                              target="keyword band", call=call, name="keyword_band", max_crop_side=MAX_LONG)
            if not res.abstained or res.error:
                return res
            res.route.append(RouteStep("fallback", target="image", note="band crop was not enough; one look at the whole page"))

    rows, cols = _content_spans(image, lines)
    cw = round(image.width * (cols[0][1] - cols[0][0])); ch = round(image.height * (rows[0][1] - rows[0][0]))
    side = _page_side(type("S", (), {"size": (cw, ch)})())
    spec = os.environ.get("SPECULATE_LOCAL", "")
    if spec and lines and not str(model).startswith("local:"):
        # Local proposes, OCR grounds, cloud confirms (message 205). The on-device model answers on the small page
        # ($0); OCR finds the line(s) where that exact answer is printed; the cloud model sees only a strip around those
        # lines (a few hundred tokens). Agreement -> answer with an OCR-verified evidence box. Otherwise: the ladder.
        proposal = None
        try:  # free proposer first: OCR field extraction (no model; pipeline/ocr_fields, 94% precise on receipts_v1)
            from pipeline.ocr_fields import extract_from_spans

            ex = extract_from_spans(lines, question)
            if ex and ex.get("answer") and ex.get("confidence", 0) >= 0.75:
                proposal = ex["answer"]
                res.route.append(RouteStep("ocr", note=f"OCR field proposal {proposal!r} (no model)"))
        except Exception:
            pass
        if proposal is None:
            low = max(512, round(side * LADDER_LOW))
            res = zoom_answer(image, question, rows, cols, prior=res, model=spec, look_for=look_for,
                              target="full page", call=call, name="local_propose", max_crop_side=low)
            proposal = None if (res.error or res.abstained) else res.answer
        hits = _locate(proposal, lines) if proposal else []
        res.error, res.abstained = None, True
        if hits:
            lh = max(0.008, sum(h["box"][3] - h["box"][1] for h in hits) / len(hits))
            spans = sorted((max(0.0, h["box"][1] - 1.5 * lh), min(1.0, h["box"][3] + 1.5 * lh)) for h in hits)
            band = [list(spans[0])]
            for a_, b_ in spans[1:]:  # one strip per occurrence, merged only when they touch
                if a_ <= band[-1][1]:
                    band[-1][1] = max(band[-1][1], b_)
                else:
                    band.append([a_, b_])
            band = [tuple(b) for b in band]
            res.route.append(RouteStep("fallback", target="image",
                                       note=f"local proposal {proposal!r} located by OCR; cloud confirms on that strip"))
            res = zoom_answer(image, question, band, cols, prior=res, model=model, look_for=look_for,
                              target="confirm strip", call=call, name="cloud_confirm", max_crop_side=side)
            if not res.error and not res.abstained and _same_answer(res.answer, proposal):
                res.evidence_boxes = [EvidenceBox([round(v, 4) for v in h["box"]], source="ocr",
                                                  label=h["text"].strip()[:60]) for h in hits]
                res.route.append(RouteStep("answer", note="local and cloud agree; answer located by OCR: accepted"))
                return res
            res.route.append(RouteStep("fallback", target="image", note="no agreement; ask on the page"))
            res.error, res.abstained = None, True
        else:
            res.route.append(RouteStep("fallback", target="image", note="local proposal not found in the OCR text"))
    if os.environ.get("GENERAL_MOSAIC", "0") == "1" and lines:
        # OCR-guided pixel pruning (message 198): send only strips around the OCR lines that match the question,
        # stitched into one row-aligned mosaic (pipeline.visual.View), so the model sees a few hundred tokens instead of
        # the page. Accept only if the answer is printed in the OCR text; otherwise continue to the page ladder.
        bands = _mosaic_bands(question, lines)
        if bands:
            res = zoom_answer(image, question, bands, cols, prior=res, model=model, look_for=look_for,
                              target="question strips", call=call, name="mosaic", max_crop_side=side)
            if res.error:
                return res
            if not res.abstained and _in_ocr(res.answer, lines):
                res.route.append(RouteStep("answer", note="strip answer found in the OCR text: accepted"))
                return res
            res.route.append(RouteStep("fallback", target="image",
                                       note="strips: answer not in the OCR text; ask on the page"))
    if os.environ.get("GENERAL_LADDER", "1") == "1" and lines:
        # OCR-verified resolution ladder (message 192): ask on a smaller page first; accept the answer only if it is
        # printed in the OCR text (a model-free check that catches low-resolution misreads); otherwise ask again at a
        # higher resolution. Answers that are not printed strings (yes/no, computed) always escalate.
        low = max(512, round(side * LADDER_LOW))
        res = zoom_answer(image, question, rows, cols, prior=res, model=model, look_for=look_for, target="full page",
                          call=call, name="page_low", max_crop_side=low)
        if res.error:
            return res
        if not res.abstained and _in_ocr(res.answer, lines):
            hits = _locate(res.answer, lines)
            if hits:  # a located citation: the OCR line(s) where the accepted answer is printed
                res.evidence_boxes = [EvidenceBox([round(v, 4) for v in h["box"]], source="ocr",
                                                  label=h["text"].strip()[:60]) for h in hits]
            res.route.append(RouteStep("answer", note="low-resolution answer found in the OCR text: accepted"))
            return res
        res.route.append(RouteStep("fallback", target="image",
                                   note="ladder: answer not in the OCR text; ask again at higher resolution"))
        side = max(side, LADDER_HIGH)
    return zoom_answer(image, question, rows, cols, prior=res, model=model, look_for=look_for, target="full page",
                       call=call, name="page", max_crop_side=side)


MOSAIC_LINES, MOSAIC_PAD = 4, 1.2  # up to 4 matched lines, each padded by 1.2 line heights above and below


def _mosaic_bands(question, lines):
    """Row bands (page fractions) around the OCR lines that best match the question words (+ synonyms), merged
    when they overlap. None if nothing matches."""
    import re

    words = [w for w in re.findall(r"[a-z0-9]+", _norm(question)) if len(w) >= 3 and w not in _STOP]
    terms = set(words)
    for w in words:
        terms |= set(SYN.get(w, "").split())
    if not terms:
        return None
    scored = []
    for s in lines:
        toks = set(re.findall(r"[a-z0-9]+", _norm(s["text"])))
        hit = sum(1 for t in terms if t in toks or (len(t) >= 5 and any(t in k for k in toks)))
        hit += sum(1 for w in words if w in toks)
        if hit:
            scored.append((hit, s))
    if not scored:
        return None
    scored.sort(key=lambda x: -x[0])
    spans = []
    for _, s in scored[:MOSAIC_LINES]:
        lh = max(0.008, s["box"][3] - s["box"][1])
        spans.append((max(0.0, s["box"][1] - MOSAIC_PAD * lh), min(1.0, s["box"][3] + MOSAIC_PAD * lh)))
    spans.sort()
    merged = [list(spans[0])]
    for a, b in spans[1:]:
        if a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    return [tuple(m) for m in merged]


LADDER_LOW, LADDER_HIGH = 0.75, 1568  # 1024 -> 768 px first; escalate to >= 1568 px (simulated on realdocs_v2: 192)


def _locate(answer, lines):
    """OCR lines on which the answer is printed (same matching rules as _in_ocr, per line)."""
    return [s for s in lines if _in_ocr(answer, [s])][:3]


def _same_answer(a, b) -> bool:
    import re

    if a is None or b is None:
        return False
    num_re = r"\d[\d.,']*\d|\d"
    key = lambda n: re.sub(r"\D", "", n).rstrip("0") or "0"
    na, nb = [key(n) for n in re.findall(num_re, str(a))], [key(n) for n in re.findall(num_re, str(b))]
    if na or nb:
        return na == nb
    norm = lambda t: re.sub(r"[^a-z0-9]", "", _norm(str(t)))
    return norm(a) == norm(b) or (len(norm(b)) >= 3 and norm(b) in norm(a)) or (len(norm(a)) >= 3 and norm(a) in norm(b))


def _in_ocr(answer, lines) -> bool:
    import re

    a = re.sub(r"[^a-z0-9]", "", _norm(str(answer or "")))
    if not a:
        return False
    text = re.sub(r"[^a-z0-9]", "", _norm(" ".join(s["text"] for s in lines)))
    mostly_number = bool(re.search(r"\d", str(answer))) and len(re.sub(r"[^a-z]", "", _norm(str(answer)))) <= 4
    if not mostly_number and a in text:  # words and codes: substring of the OCR text
        return True
    # "CHF 9.84" / "$1,322.87" / "9.84 EUR": the model adds a currency or unit the page prints apart. Accept when every
    # number in the answer is printed (digits compared without separators) and the answer is mostly that number.
    num_re = r"\d[\d.,']*\d|\d"
    key = lambda n: re.sub(r"\D", "", n).rstrip("0") or "0"  # 156.80 == 156.8; separators ignored
    nums = re.findall(num_re, str(answer))
    page = {key(n) for s in lines for n in re.findall(num_re, s["text"])}
    letters = re.sub(r"[^a-z]", "", _norm(str(answer)))
    return bool(nums) and len(letters) <= 4 and all(key(n) in page for n in nums)


PIXELS_PER_TOKEN = 800.0
BAND_ABOVE, BAND_BELOW = 0.30, 0.30  # crop band around the named lines (page fractions). Drawings sit above their
# labels (axis labels, legends, keys) as often as below their question text: homework_v2 held-out, 8264c05.

SYSTEM_TEXT = (
    "You answer questions about an image using ONLY its OCR text, given as numbered lines [L1], [L2], ... in reading "
    "order. If the lines contain what is needed, answer and cite the ids of the lines you used (at most 6). Put only "
    "the shortest answer in \"answer\", copied exactly as the page writes it (same words, numbers and spelling; no "
    "added units, articles like \"the\", or comments; if OCR garbled a word, give the intended word). For tutoring "
    "questions (solve, explain, check my work) add a short step-by-step explanation in \"explanation\" (at most 60 "
    "words); any other comment also goes there, never in \"answer\". If the answer depends on "
    "something OCR cannot capture, do not guess: ask for the image and list the ids of the lines nearest to what must "
    "be looked at. That includes: a drawing, diagram, map, graph, chart or picture; which cell of a table is empty or "
    "where things sit in a table or grid; a tick, cross, circle, highlight, sticker, line or arrow (OCR often reads a "
    "tick as V or a cross as X: never decide marks from OCR characters); handwriting that is missing or garbled; "
    "colour; position. Abstain only when the page clearly does not contain that kind of information at all. "
    "Reply with JSON only, one of:\n"
    '{"answer": "...", "explanation": "... (optional)", "lines": [ids]}\n'
    '{"need_image": true, "lines": [ids], "look_for": "what to inspect, in a few words"}\n'
    '{"abstain": true}'
)


def _lines(spans: list[dict]) -> list[dict]:
    """OCR spans in reading order (top to bottom, then left to right), confident ones only."""
    sp = [s for s in spans if s.get("confidence", 0) >= 0.3 and s.get("text", "").strip()]
    sp.sort(key=lambda s: (round((s["box"][1] + s["box"][3]) / 2, 2), s["box"][0]))
    return sp[:MAX_LINES]


def _parse(text: str) -> dict:
    """JSON reply; if it was cut off by the output limit, salvage its fields instead of showing raw JSON."""
    import re

    from pipeline.visual import parse

    d = parse(text)
    ans = d.get("answer")
    if isinstance(ans, str) and ans.lstrip().startswith("{"):
        out: dict = {}
        if re.search(r'"need_image"\s*:\s*true', text):
            out["need_image"] = True
        elif re.search(r'"abstain"\s*:\s*true', text):
            out["abstain"] = True
        m = re.search(r'"answer"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
        if m and not out:
            out["answer"] = json.loads(f'"{m.group(1)}"')
        m = re.search(r'"look_for"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
        if m:
            out["look_for"] = json.loads(f'"{m.group(1)}"')
        m = re.search(r'"lines"\s*:\s*\[([0-9,\sL"]*)', text)
        if m:
            out["lines"] = re.findall(r"\d+", m.group(1))
        return out or {"abstain": True}
    return d


def _band(boxes: list[list[float]]) -> tuple[float, float]:
    y0 = max(0.0, min(b[1] for b in boxes) - BAND_ABOVE)
    y1 = min(1.0, max(b[3] for b in boxes) + BAND_BELOW)
    return y0, y1


def answer(image, question: str, prior: Optional[PipelineResult] = None, model: Optional[str] = None,
           call=None, text_step: bool = True, thumb_px: Optional[int] = None,
           size_rule: Optional[bool] = None) -> PipelineResult:
    """text_step=False skips the OCR-text call and sends the whole page: for small models that do not reliably ask
    for pixels when text is not enough (Qwen2.5-VL-7B: REPORT_homework_v3_qwen7b.md). OCR still runs (boxes, $0)."""
    from pipeline.ocr import recognize_page
    from pipeline.router import ensure_ocr_bin
    from pipeline.visual import CALL_OVERRIDE, DEFAULT_MODEL, zoom_answer

    model = model or os.environ.get("EVAL_MODEL") or DEFAULT_MODEL
    if thumb_px is None:  # experimental: a small thumbnail with the OCR text, so the text step can see drawings
        thumb_px = int(os.environ.get("GENERAL_THUMB_PX", "0"))
    res = prior if prior is not None else PipelineResult(answer=None, abstained=True)
    res.pipeline = (res.pipeline + "+" if res.pipeline else "") + "general"

    # 1. OCR (local)
    import time

    t0 = time.perf_counter()
    lines: list[dict] = []
    try:
        if ensure_ocr_bin() is None:
            raise RuntimeError("OCR helper unavailable")
        spans, _ = recognize_page(image)
        lines = _lines(spans)
        note = f"{len(lines)} OCR lines"
    except Exception as e:
        note = f"OCR unavailable ({type(e).__name__}); whole page"
    res.route.append(RouteStep("ocr", note=note))
    res.usage.append(Usage(len(res.route) - 1, "local", "Apple Vision OCR", latency_ms=(time.perf_counter() - t0) * 1000))

    look_for, named = "", None
    if size_rule is None:
        size_rule = os.environ.get("GENERAL_SIZE_RULE", "1") != "0"
    if lines and text_step and size_rule:
        img_tok = image.width * image.height / PIXELS_PER_TOKEN
        txt_tok = sum(len(s["text"]) + 6 for s in lines) / 4 + TEXT_STEP_OVERHEAD
        if img_tok <= txt_tok:
            res.route.append(RouteStep("fallback", target="image",
                                       note=f"small image: whole page (~{img_tok:.0f} tok) is cheaper than its OCR text "
                                            f"(~{txt_tok:.0f} tok)"))
            return _page_call(image, question, res, model, call, lines)
    if lines and not text_step:
        res.route.append(RouteStep("fallback", target="image", note="whole page (text step off)"))
        return _page_call(image, question, res, model, call, lines)
    if lines:
        # 2. text-only call
        text = "\n".join(f"[L{i + 1}] {s['text'].strip()}" for i, s in enumerate(lines))
        injected = call or CALL_OVERRIDE
        image_block = None
        if injected is not None:
            call_fn = injected
        else:
            from eval.backends import get

            be, _ = get(model)
            call_fn, image_block = be.call, getattr(be, "image_block", None)
        content = [{"type": "text", "text": f"OCR lines:\n{text}\n\nQuestion: {question}"}]
        px: list = []
        target = "OCR text only"
        if thumb_px and image_block is not None:
            th = image.convert("RGB").copy()
            th.thumbnail((thumb_px, thumb_px))
            content = [image_block(th), {"type": "text", "text": "(A small thumbnail of the page is attached so you can "
                       "see whether drawings or marks matter; it is too small to read. Ask for the image if they do.)\n"
                       + content[0]["text"]}]
            px, target = [th.size], f"OCR text + {th.width}x{th.height}px thumbnail"
        res.route.append(RouteStep("native_text", target=target, note=f"{len(lines)} lines to {model}"))
        try:
            reply, usage, stop = call_fn(content, step_index=len(res.route) - 1, system=SYSTEM_TEXT, model=model,
                                         images_px=px)
        except Exception as e:
            res.error, res.answer, res.abstained = f"{type(e).__name__}: {e}", None, True
            res.route.append(RouteStep("abstain", note="text call failed"))
            return res
        res.usage.append(usage)
        d = _parse(reply)
        ids = [int(str(x).lstrip("Ll")) for x in (d.get("lines") or []) if str(x).lstrip("Ll").isdigit()]
        cited = [lines[i - 1] for i in ids if 1 <= i <= len(lines)]
        if d.get("abstain"):
            res.answer, res.abstained = None, True
            res.route.append(RouteStep("abstain", note="not in the OCR text, and no image needed"))
            return res
        if not d.get("need_image") and d.get("answer") not in (None, ""):
            res.answer, res.abstained = str(d["answer"]), False
            if d.get("explanation"):
                res.route[-1].note = (res.route[-1].note or "") + f" | explanation: {str(d['explanation'])[:600]}"
            for s in cited:
                res.evidence_boxes.append(EvidenceBox([round(v, 4) for v in s["box"]], source="ocr",
                                                      label=s["text"].strip()[:60]))
            res.route.append(RouteStep("answer", note=f"from OCR text, lines {ids}" if ids else "from OCR text"))
            return res
        look_for = str(d.get("look_for") or "")
        named = [s["box"] for s in cited] or None

    # 3. pixels: a band around the named lines, or the whole page
    if named:
        y0, y1 = _band(named)
        rows, target = [(y0, y1)], "near cited lines"
    else:
        rows, target = [(0.0, 1.0)], "full page"
    res.route.append(RouteStep("fallback", target="image", note=f"needs pixels: {look_for or 'not readable from OCR text'}"))
    res = zoom_answer(image, question, rows, [(0.0, 1.0)], prior=res, model=model,
                      look_for=look_for or "the evidence for the question", target=target, call=call,
                      name="pixels")
    # 4. the band was not enough: one more look, at the whole page (a band can miss a drawing far from its labels)
    if res.abstained and not res.error and rows != [(0.0, 1.0)]:
        res.route.append(RouteStep("fallback", target="image", note="band crop was not enough; one look at the whole page"))
        res = _page_call(image, question, res, model, call, lines, look_for or "the evidence for the question")
    return res


def factory():
    """run_eval: --pipelines pipeline.general:factory   (model from EVAL_MODEL)"""
    from eval.pipelines.compose import from_answer_fn

    return from_answer_fn(answer, "general")
