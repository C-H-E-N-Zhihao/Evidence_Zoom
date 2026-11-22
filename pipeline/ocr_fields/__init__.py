"""Model-free OCR field answerer: label + number on the same visual row (0 tokens).

extract(image, question) -> {"answer", "confidence", "line", "box"}; answer() wraps it as a pre-stage returning a
PipelineResult (abstained=True + RouteStep("fallback") when not confident). Precision over coverage.
"""
from __future__ import annotations

import difflib
import re
import unicodedata
from typing import Optional

from eval.schema import EvidenceBox, PipelineResult, RouteStep

MIN_CONF = 0.75  # answer() abstains below this

NUM = re.compile(r"(?<![\w.,])(\d{1,3}(?:[.,]\s?\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?)(?![\w])")


def _n(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s).split())


def _has(text: str, words) -> bool:
    t = " " + _n(text) + " "
    return any(" " + w + " " in t for w in words)


# ---- question classification ------------------------------------------------------------------
TAX_Q = ["tax", "vat", "tva", "mwst", "pajak", "ppn", "pb1", "gst", "taxe", "steuer", "impot"]
CHG_Q = ["change", "kembali", "kembalian", "rendu", "monnaie", "ruckgeld", "wisselgeld", "terugbetaling"]
SUB_Q = ["subtotal", "sub total", "sous total", "zwischensumme", "subtotaal"]
TOT_Q = ["total", "totaal", "gesamt", "montant", "ttc", "jumlah", "amount due", "grand", "summe", "bayar", "somme", "to pay", "amount paid", "balance due"]
DATE_Q = ["date", "tanggal", "datum", "tgl"]
INV_Q = ["invoice number", "invoice no", "invoice nr", "invoice id", "facture", "rechnungsnummer", "rechnung nr", "nomor faktur", "no faktur", "factuurnummer", "bill number", "bill no", "receipt number", "receipt no", "order number"]


def classify(question: str):
    q = question.strip()
    ql = q.lower()
    m = re.search(r"(?:price|cost|harga|prix|preis|prijs|amount (?:charged )?for)\s+(?:of|for|de|van|du)?\s*(?:the\s+(?:line|item)\s+)?['\"“]?(.+?)['\"”]?\s*\??$", q, re.I)
    if m and not _has(q, ["total", "tax", "change", "subtotal"]) and len(_n(m.group(1))) >= 2:
        return "item", m.group(1).strip(" '\"“”")
    if _has(q, INV_Q):
        return "invoice", None
    if _has(q, SUB_Q):
        return "subtotal", None
    if _has(q, TAX_Q) and _has(q, ["total"]) and not _has(q, ["registration", "number", "id", "no", "nummer", "numero",
                                                               "rate", "percentage"]):
        return None, None  # "total VAT" vs "total incl. VAT" is ambiguous: leave it to the model
    if _has(q, TAX_Q) and not _has(q, ["total", "registration", "number", "id", "no", "nummer", "numero", "rate", "percentage"]):
        return "tax", None
    if _has(q, CHG_Q):
        return "change", None
    if _has(q, TOT_Q) and not _has(q, ["items", "item", "quantity", "qty", "number of"]):
        return "total", None
    if _has(q, DATE_Q) and not _has(q, ["due", "paid", "pay", "payment", "expiry", "expiration", "birth", "valid"]):
        return "date", None
    return None, None


# label rank per field: (regex on normalized text, rank); higher = more specific
LABELS = {
    "total": [(r"\bgrand total\b|\btotal bayar\b|\btotal due\b|\bamount due\b|\btotal amount\b|\btotal a payer\b|\bnet total\b|\btotal ttc\b|\bgesamtbetrag\b|\btotal payable\b|\btotaal\b|\bgesamt\b|\btotal harga\b", 3),
              (r"^(?:\w+ )?total$|^total rp$|\btotal\b|\bjumlah\b|\bmontant\b", 2)],
    "subtotal": [(r"\bsub ?total\b|\bsous total\b|\bzwischensumme\b|\bsubtotaal\b", 3)],
    "cash": [(r"\bcash\b|\btunai\b|\bcash tendered\b|\bdibayar\b|\bbayar\b|\btendered\b|\bespece|\bbar\b", 3)],
    "tax": [(r"\btotal tax\b|\bppn\b|\bpb ?1\b|\bpajak\b|\btax\b|\bvat\b|\btva\b|\bmwst\b|\bgst\b|\bsteuer\b|\btaxe\b", 3)],
    "change": [(r"\bchange\b|\bkembali\b|\bkembalian\b|\bchg\b|\bchanged\b|\brendu\b|\bmonnaie\b|\bruckgeld\b|\bwisselgeld\b", 3)],
}
EXCL = {
    "total": r"\bsub ?total\b|\btotal (?:item|items|qty|quantity|disc|discount|diskon|saving|savings|point|points|pcs|pax|guest|before|tax|service|pb ?1|ppn|vat)\b|\b(?:item|items|qty) total\b|\bsub\b|\bbefore\b|\bcash\b|\bdiscount\b|\bsaving",
    "tax": r"\btax (?:id|no|number|reg|registration|invoice)\b|\bbefore tax\b|\bexcl|\bnpwp\b|\bno\b.*\bvat\b|\bvat (?:no|number|reg|id)\b|\bincl\b|\bexclusive\b|\binclusive\b|\bsubtotal\b|\bsub total\b|\btotal\b.*\btax\b.*\btotal\b",
    "change": r"\bchange (?:rate|of)\b",
    "subtotal": r"^$",
    "cash": r"\btotal\b|\bchange\b|\bkembali|\bpoint|\bcard\b|\bkartu\b|\bdebit|\bcredit|\bnon\b",
}


def _clean_num(tok: str) -> str:
    tok = re.sub(r"([.,])\s+(?=\d{3})", r"\1", tok)
    return tok


def _plausible(tok: str) -> bool:
    """Reject OCR fragments: leading-zero groups ("03,000", "000"), ragged grouping ("40,0000")."""
    t = tok.strip()
    if t in ("0", "00", "0.00", "0,00"):
        return True
    if re.match(r"0\d", t):
        return False
    if re.search(r"[.,]", t):
        parts = re.split(r"[.,]", re.sub(r"[.,]\d{1,2}$", "", t) if re.search(r"[.,]\d{1,2}$", t) and not re.search(r"[.,]\d{3}$", t) else t)
        if len(parts) > 1 and (len(parts[0]) > 3 or any(len(x) != 3 for x in parts[1:])):
            return False
    return True


def _numbers(text: str):
    text = re.sub(r"(?<=\d)['\u2019](?=\d{3})", "", text)
    t = re.sub(r"\d+(?:[.,]\d+)?\s*%", " ", text)
    t = re.sub(r"(?i)\b(?:rp|idr|usd|eur|chf)\b\.?\s*|[€$]", " ", t)
    t = re.sub(r"(?i)(?<=\s)rp(?=\d)|^rp(?=\d)", " ", t)
    return [x for x in (_clean_num(m.group(1)) for m in NUM.finditer(t)) if _plausible(x)]


def _val(tok: str) -> Optional[int]:
    t = re.sub(r"[.,]\d{1,2}$", "", tok) if re.search(r"[.,]\d{1,2}$", tok) and not re.search(r"[.,]\d{3}$", tok) else tok
    t = re.sub(r"[^\d]", "", t)
    return int(t) if t else None


def _cy(b): return (b[1] + b[3]) / 2
def _h(b): return max(b[3] - b[1], 1e-6)


def _row_numbers(spans, lab, exclude=None):
    """Numeric spans on the same visual row as `lab`, to its right (or inline in the same span after the label).
    Returns list of (token, span) ordered left to right."""
    out = []
    lb = lab["box"]
    for s in spans:
        if s is lab:
            continue
        b = s["box"]
        tol = 0.6 * max(_h(lb), _h(b))
        if abs(_cy(b) - _cy(lb)) <= tol and b[0] >= lb[0] + 0.5 * (lb[2] - lb[0]) and b[0] >= lb[0]:
            for tok in _numbers(s["text"]):
                out.append((tok, s))
    out.sort(key=lambda p: p[1]["box"][0])
    return out


def _inline_numbers(lab, label_re):
    t = lab["text"]
    # numbers occurring after the label inside the span: approximate by taking numbers in the span text after a non-digit label
    head = re.split(r"\d", t, maxsplit=1)[0]
    if not head.strip():
        return []
    return [(tok, lab) for tok in _numbers(t[len(head):])]


def _next_row(spans, lab):
    lb = lab["box"]
    cands = [s for s in spans if s is not lab and _numbers(s["text"]) and 0.6 * _h(lb) < _cy(s["box"]) - _cy(lb) <= 1.9 * _h(lb)
             and s["box"][2] >= lb[0]]
    if not cands:
        return []
    top = min(cands, key=lambda s: _cy(s["box"]))
    row = [s for s in cands if abs(_cy(s["box"]) - _cy(top["box"])) <= 0.6 * _h(top["box"])]
    row.sort(key=lambda s: s["box"][0])
    return [(t, s) for s in row for t in _numbers(s["text"])]


def _union(boxes):
    return [min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)]


def _result(tok, lab, vs):
    boxes = [lab["box"], vs["box"]]
    return {"answer": tok, "line": f'{lab["text"]} | {vs["text"]}' if vs is not lab else lab["text"], "box": _union(boxes)}


def _field_amount(spans, field, check=True):
    found = []  # (rank, conf, tok, lab, span)
    for lab in spans:
        nt = _n(lab["text"])
        if not nt:
            continue
        # label part only: drop trailing digits for matching
        label_text = _n(re.sub(r"[\d.,]+\s*%?", " ", lab["text"]))
        if not label_text:
            continue
        if re.search(EXCL[field], label_text):
            continue
        rank = 0
        for rx, r in LABELS[field]:
            if re.search(rx, label_text):
                rank = r
                break
        if not rank:
            continue
        # a label span that is mostly a longer sentence is unlikely to be a field label
        if len(label_text.split()) > 5:
            continue
        nums = _row_numbers(spans, lab)
        conf_base = 0.9
        if not nums:
            nums = _inline_numbers(lab, None) if field != "x" else []
        if not nums:
            nums = _next_row(spans, lab)
            conf_base = 0.55
        if not nums:
            continue
        if len({_val(t) for t, _ in nums}) > 1 and conf_base > 0.6:
            # several numbers on a row (e.g. qty + price): take right-most
            pass
        tok, sp = nums[-1]
        found.append((rank, conf_base, tok, lab, sp))
    if not found:
        return None
    best_rank = max(f[0] for f in found)
    top = [f for f in found if f[0] == best_rank]
    top_best_conf = max(f[1] for f in top)
    top = [f for f in top if f[1] == top_best_conf]
    vals = {_val(f[2]) for f in top}
    # a lower-ranked competing label with a different value lowers confidence (e.g. total vs. grand total) only slightly
    if len(vals) > 1:
        return None
    f = top[0]
    conf = f[1]
    others = {_val(x[2]) for x in found if x[0] < best_rank}
    if field == "total" and best_rank == 2 and others - vals:
        conf -= 0.1
    if _val(f[2]) is None:
        return None
    r = _result(f[2], f[3], f[4])
    if check:
        cons = _consistency(spans, field, {"answer": f[2]})
        if cons < 0:
            conf = min(conf, 0.4)
        elif cons > 0:
            conf = max(conf, 0.95)
    r["confidence"] = round(conf, 2)
    return r


def _consistency(spans, field, r):
    """Cross-check total / cash / change on the same receipt: cash - change == total. Returns +1 (consistent),
    0 (not checkable) or -1 (contradiction)."""
    if field not in ("total", "change"):
        return 0
    cash = _field_amount(spans, "cash", check=False)
    if not cash:
        return 0
    other = _field_amount(spans, "change" if field == "total" else "total", check=False)
    if not other:
        return 0
    c, o, v = _val(cash["answer"]), _val(other["answer"]), _val(r["answer"])
    if None in (c, o, v):
        return 0
    a, b = (v, o) if field == "total" else (o, v)  # a = total, b = change
    return 1 if c - b == a else -1


def _item(spans, name):
    target = _n(name)
    if not target:
        return None
    scored = []
    for lab in spans:
        lt = _n(re.sub(r"^\s*\d+\s*[xX]?\s+", "", lab["text"]))  # drop leading qty
        if not lt or _numbers(lab["text"]) and not re.search(r"[a-z]", lt):
            continue
        r = difflib.SequenceMatcher(None, target, lt).ratio()
        if target in lt or lt in target and len(lt) >= 4:
            r = max(r, 0.9 if target in lt else 0.85)
        scored.append((r, lab))
    if not scored:
        return None
    scored.sort(key=lambda p: -p[0])
    r, lab = scored[0]
    if r < 0.8:
        return None
    if len(scored) > 1 and scored[1][0] >= r - 0.05 and abs(_cy(scored[1][1]["box"]) - _cy(lab["box"])) > _h(lab["box"]) and _n(scored[1][1]["text"]) != _n(lab["text"]):
        return None  # two equally good matches on different rows
    nums = _row_numbers(spans, lab)
    conf = 0.85
    if not nums:
        nums = [(t, lab) for t in _numbers(lab["text"])[-1:]] if re.search(r"[a-zA-Z]\W*\d", lab["text"]) else []
        conf = 0.7
    if not nums:
        nums = _next_row(spans, lab)
        conf = 0.5
    if not nums:
        return None
    tok, sp = nums[-1]
    if (_val(tok) or 0) < 100 and not re.search(r"[.,]\d{2}$", tok):
        return None
    res = _result(tok, lab, sp)
    res["confidence"] = round(conf if r >= 0.9 else min(conf, 0.78), 2)
    return res


DATE_RX = re.compile(r"\b(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}|\d{4}[/.\-]\d{1,2}[/.\-]\d{1,2}|\d{1,2}\s+(?:jan|feb|mar|apr|may|mei|jun|jul|aug|agu|sep|oct|okt|nov|dec|des)[a-z]*\.?\s+\d{2,4})\b", re.I)


def _date(spans):
    found = {}
    for s in spans:
        m = DATE_RX.search(s["text"])
        if m:
            found.setdefault(m.group(1), s)
    if len(found) != 1:
        return None
    d, s = next(iter(found.items()))
    return {"answer": d, "line": s["text"], "box": s["box"], "confidence": 0.8}


def _invoice(spans):
    found = {}
    rx = r"\b(?:invoice|inv|facture|rechnung|faktur|bill|receipt|factuur)\s*(?:number|no|nr|num|id|nummer|#)\b\.?\s*[:#]?"
    for lab in spans:
        t = _n(lab["text"])
        if not re.search(rx, lab["text"], re.I) and not re.search(r"\binvoice number\b|\binvoice no\b", t):
            continue
        m = re.search(rx + r"\s*([A-Za-z0-9][A-Za-z0-9\-/]{2,})", lab["text"], re.I)
        if m and re.search(r"\d", m.group(1)):
            found[m.group(1)] = (lab, lab, 0.85)
            continue
        cands = []
        for s in spans:
            if s is lab:
                continue
            b = s["box"]
            if abs(_cy(b) - _cy(lab["box"])) <= 0.6 * max(_h(lab["box"]), _h(b)) and b[0] >= lab["box"][0]:
                cands.append(s)
        if not cands:
            cands = [s for s in spans if s is not lab and 0.6 * _h(lab["box"]) < _cy(s["box"]) - _cy(lab["box"]) <= 1.9 * _h(lab["box"]) and abs(s["box"][0] - lab["box"][0]) < 0.15]
            conf = 0.55
        else:
            conf = 0.85
        cands = [s for s in cands if re.search(r"\d", s["text"]) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9\-/ ]{2,}", s["text"].strip())]
        if len(cands) == 1:
            found[cands[0]["text"].strip()] = (lab, cands[0], conf)
    if len(found) != 1:
        return None
    tok, (lab, sp, conf) = next(iter(found.items()))
    r = _result(tok, lab, sp)
    r["confidence"] = conf
    return r


def extract_from_spans(spans, question):
    field, arg = classify(question)
    none = {"answer": None, "confidence": 0.0, "line": None, "box": None, "field": field}
    if field is None:
        return none
    spans = [s for s in spans if s.get("text", "").strip()]
    if field == "item":
        r = _item(spans, arg)
    elif field == "date":
        r = _date(spans)
    elif field == "invoice":
        r = _invoice(spans)
    else:
        r = _field_amount(spans, field)
    if not r:
        return none
    r["field"] = field
    return r


def extract(image, question):
    field, _ = classify(question)
    if field is None:
        return {"answer": None, "confidence": 0.0, "line": None, "box": None, "field": None}
    from pipeline.ocr import recognize_page
    spans, _ = recognize_page(image)
    return extract_from_spans(spans, question)


def answer(image, question, prior=None, model=None, min_conf: float = MIN_CONF) -> PipelineResult:
    """Pre-stage: confident -> answer + EvidenceBox(source="ocr"); otherwise abstained with a "fallback" route step."""
    res = PipelineResult(None, abstained=True, pipeline="ocr_fields@v1")
    res.route.append(RouteStep("ocr"))
    try:
        r = extract(image, question)
    except Exception as e:  # OCR helper missing/failed: let the caller fall back to a model
        res.error = f"ocr_fields: {e}"
        res.route.append(RouteStep("fallback", note="ocr failed"))
        return res
    if r["answer"] is not None and r["confidence"] >= min_conf:
        res.answer, res.abstained = r["answer"], False
        res.evidence_boxes.append(EvidenceBox(box=r["box"], source="ocr", label=r["line"]))
        res.route.append(RouteStep("answer", box=r["box"], note=f'ocr_fields:{r["field"]} conf={r["confidence"]}'))
    else:
        res.route.append(RouteStep("fallback", note=f'ocr_fields:{r["field"]} no confident match'))
    return res
