"""Conservative OCR exit for typed fields on the two-column accident statement."""
import io
import json
import os
import re
import subprocess
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


def locate(spans, field, side):
    headers = {}
    for key in "ab":
        hits = [s for s in spans if _squash(s["text"]) == "vehicle" + key and s["confidence"] >= .8]
        if len(hits) != 1:
            return None
        headers[key] = hits[0]["box"]
    left, right = headers["a"], headers["b"]
    if left[2] >= right[0] or abs(left[1] - right[1]) > .03:
        return None
    # Labels align with the vehicle headers. The right header starts column B.
    cut = right[0] - .015
    column = [s for s in spans if (s["box"][0] < cut) == (side == "a")
              and s["box"][1] >= headers[side][3] and s["confidence"] >= .8]
    labels = {"policy": ("policy no.", "policy number"), "registration": ("registration",),
              "insurer": ("insurer",), "driver": ("driver",)}
    matches = [s for s in column if s["text"].lower().strip().rstrip(":") in labels[field]]
    if len(matches) != 1:
        return None
    label = matches[0]["box"]
    values = [s for s in column if s["box"][0] > label[2]
              and min(label[3], s["box"][3]) - max(label[1], s["box"][1]) > .4 * (label[3]-label[1])]
    return values[0] if len(values) == 1 else None


def answer(image, question):
    result = PipelineResult(None, abstained=True, pipeline="ocr_router")
    field = requested_field(question)
    insurer = re.fullmatch(r"which (?:vehicle|car) is insured by ([^?]+)\??", question.strip(), re.I)
    if field or insurer:
        start = time.perf_counter()
        result.route.append(RouteStep("ocr"))
        try:
            stream = io.BytesIO()
            image.save(stream, format="PNG")
            process = subprocess.run([os.environ.get("EVIDENCE_OCR_BIN", "evidence-ocr")],
                                     input=stream.getvalue(), capture_output=True, check=True, timeout=30)
            spans = json.loads(process.stdout)
            span = None
            response = None
            if field:
                span = locate(spans, *field)
                if span:
                    response = span["text"]
                    if field[0] in ("policy", "registration"):
                        response = clean_id(response)
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
