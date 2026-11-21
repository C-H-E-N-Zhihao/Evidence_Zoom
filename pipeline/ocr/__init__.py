"""Conservative OCR exit for typed fields on the two-column accident statement."""
from collections import OrderedDict
import hashlib
import io
import json
import os
import re
import subprocess
import threading
import time

from eval.schema import EvidenceBox, PipelineResult, RouteStep, Usage


def requested_field(question):
    q = question.lower().strip(" ?.").replace("’", "'")
    q = q.replace("insurance policy", "policy")
    field = r"(insurer|driver|registration(?: number)?|policy (?:number|no\.?))"
    vehicle = r"(?:vehicle|car) ([ab])"
    for pattern, reversed_order in [
        (rf"(?:what is |what's |who is |who's )?(?:the )?{field} (?:for|of|on) {vehicle}", False),
        (rf"(?:what is |what's |who is |who's )?{vehicle}'s {field}", True),
    ]:
        match = re.fullmatch(pattern, q)
        if match:
            name, side = match.groups()[::-1] if reversed_order else match.groups()
            return name.split()[0], side
    return None


# Cyrillic/Greek capitals that render like Latin ones. Vision occasionally returns them inside IDs,
# which look right but break any lookup. IDs are folded to Latin and must then be plain ASCII.
CONFUSABLES = str.maketrans("АВЕКМНОРСТХУІЈЅΑΒΕΖΗΙΚΜΝΟΡΤΥΧ", "ABEKMHOPCTXYIJSABEZHIKMNOPTYX")


def clean_id(text):
    folded = text.translate(CONFUSABLES)
    return folded if folded.isascii() else None


def _squash(text):
    return re.sub(r"\s+", "", text.lower())


# Label wordings seen on accident-statement layouts (generic synonyms, not tied to one rendering).
LABELS = {
    "policy": ("policy no.", "policy no", "policy number", "policy"),
    "registration": ("registration", "registration number", "registration plate", "registration no.",
                     "licence plate", "license plate", "number plate", "plate"),
    "insurer": ("insurer", "insurance company", "insurance", "insured by"),
    "driver": ("driver", "driver name", "driver's name", "name of driver", "driver (name)"),
}
# Characters Vision confuses (digit vs letter). An ID segment that mixes letters and digits AND contains one
# of these cannot be read safely (held-out v2: "JI-9779-2542" read as "J1-9779-2542"): defer to the model.
AMBIGUOUS = set("01IOlSB5Z28")


def ambiguous_id(text):
    for seg in re.split(r"[\s\-/.]+", text):
        if any(c.isalpha() for c in seg) and any(c.isdigit() for c in seg) and AMBIGUOUS & set(seg):
            return True
    return False


def _label_key(text):
    return re.sub(r"\s+", " ", text.lower().strip().rstrip(":").strip())


def header_pairs(spans):
    """Same-height ("Vehicle A", "Vehicle B") header pairs, top first. Layouts may repeat the headers
    (e.g. above the circumstances table); every pair is tried, ambiguity is resolved by the field search."""
    hs = {k: [s["box"] for s in spans if _squash(s["text"]) == "vehicle" + k and s["confidence"] >= .8]
          for k in "ab"}
    pairs = []
    for a in hs["a"]:
        for b in hs["b"]:
            if a[2] < b[0] and abs((a[1] + a[3]) / 2 - (b[1] + b[3]) / 2) < .03 + .15 * (b[0] - a[2]):
                pairs.append((a, b))
    return sorted(pairs, key=lambda p: p[0][1])


def _locate_with(spans, field, side, left, right):
    delta_x = (right[0] + right[2] - left[0] - left[2]) / 2
    slope = (right[1] + right[3] - left[1] - left[3]) / (2 * delta_x)
    if abs(slope) > .15:
        return None

    def row_bounds(box):
        # Compare heights along the header baseline; evidence stays in original coordinates.
        shift = slope * (box[0] + box[2]) / 2
        return box[1] - shift, box[3] - shift

    header = left if side == "a" else right
    # Labels align with the vehicle headers. The right header starts column B.
    cut = right[0] - .015
    column = [s for s in spans if (s["box"][0] < cut) == (side == "a")
              and row_bounds(s["box"])[0] >= row_bounds(header)[1]]
    wanted = LABELS[field]
    matches = [s for s in column if _label_key(s["text"]) in wanted]
    inline = [s for s in column if ":" in s["text"] and _label_key(s["text"].split(":", 1)[0]) in wanted
              and s["text"].split(":", 1)[1].strip()]
    if len(matches) + len(inline) != 1:
        return None
    if inline:  # "Policy number: AB-1234-5678" recognised as one span
        s = inline[0]
        if s["confidence"] < .8:
            return None
        return {**s, "text": s["text"].split(":", 1)[1].strip()}
    if matches[0]["confidence"] < .8:
        return None
    label = matches[0]["box"]
    top, bottom = row_bounds(label)
    values = []
    for span in column:
        candidate_top, candidate_bottom = row_bounds(span["box"])
        overlap = min(bottom, candidate_bottom) - max(top, candidate_top)
        if span["box"][0] > label[2] and overlap > .4 * (bottom - top):
            values.append(span)
    return values[0] if len(values) == 1 and values[0]["confidence"] >= .8 else None


def locate(spans, field, side):
    """Value span for `field` of vehicle `side`, or None. Tries every header pair; answers only if exactly
    one distinct value is found (two pairs disagreeing = ambiguous = None)."""
    found = {}
    for left, right in header_pairs(spans):
        v = _locate_with(spans, field, side, left, right)
        if v is not None:
            found[v["text"]] = v
    return next(iter(found.values())) if len(found) == 1 else None


# Each worker keeps recent recognition results in memory. Cache spans, never page images.
_page_spans = OrderedDict()
_cache_lock = threading.Lock()


def recognize_page(image):
    helper = os.environ.get("EVIDENCE_OCR_BIN", "evidence-ocr")
    if image.mode not in ("RGB", "RGBA", "L"):
        image = image.convert("RGBA")
    cache_enabled = os.environ.get("EVIDENCE_OCR_CACHE", "1") != "0"
    if cache_enabled:
        key = (helper, image.mode, image.size, hashlib.sha256(image.tobytes()).digest())
        with _cache_lock:
            if key in _page_spans:
                _page_spans.move_to_end(key)
                return json.loads(_page_spans[key]), True

    # Run outside the lock so independent requests can recognize different pages in parallel.
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    process = subprocess.run([helper], input=stream.getvalue(), capture_output=True, check=True, timeout=30)
    spans = json.loads(process.stdout)
    if cache_enabled and len(process.stdout) <= 256 * 1024:
        with _cache_lock:
            _page_spans[key] = process.stdout
            _page_spans.move_to_end(key)
            if len(_page_spans) > 16:
                _page_spans.popitem(last=False)
    return spans, False


def answer(image, question):
    result = PipelineResult(None, abstained=True, pipeline="ocr_router")
    field = requested_field(question)
    insurer = re.fullmatch(r"which (?:vehicle|car) is insured by ([^?]+)\??", question.strip(), re.I)
    if field or insurer:
        start = time.perf_counter()
        result.route.append(RouteStep("ocr"))
        try:
            spans, reused = recognize_page(image)
            result.route[0].note = "Reused page OCR" if reused else "Recognized page locally"
            span = None
            response = None
            if field:
                span = locate(spans, *field)
                if span:
                    response = span["text"]
                    if field[0] in ("policy", "registration"):
                        response = clean_id(response)
                        if response and ambiguous_id(response):
                            response = None  # e.g. "J1-…" for "JI-…": cannot be read safely
                        span = span if response else None
            else:
                # Require readable values in both columns to establish uniqueness.
                insurers = [locate(spans, "insurer", side) for side in "ab"]
                if all(insurers):
                    target = insurer.group(1).strip().casefold()
                    matches = [(side, value) for side, value in zip("AB", insurers)
                               if value["text"].strip().casefold() == target]
                    if len(matches) == 1:
                        response, span = matches[0]
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            result.error = str(exc)
            span = None
        result.usage.append(Usage(0, "local", "Apple Vision OCR", latency_ms=(time.perf_counter()-start)*1000))
        if span:
            result.answer = response
            result.abstained = False
            result.evidence_boxes.append(EvidenceBox(span["box"], source="ocr", label=result.answer))
            result.route.append(RouteStep("answer", box=span["box"]))
            return result
    result.route.append(RouteStep("fallback", target="overview", note="Visual inspection required"))
    return result
