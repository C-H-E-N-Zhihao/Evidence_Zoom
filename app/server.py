"""Evidence Zoom demo server.

Run:  .venv/bin/uvicorn app.server:app --reload --port 8000
Key-free rehearsal (real OCR, visual route REPLAYED from fixture labels):  ./scripts/demo.sh
      = PIPELINE=pipeline.router DEMO_REPLAY=1 uvicorn app.server:app
Pipeline:  PIPELINE=app.mock_pipeline (default), any module exposing
           answer(image: PIL.Image.Image, question: str) -> dict | PipelineResult,
           or an eval pipeline name, e.g. PIPELINE=eval:full_image_cached
           (any name in eval.pipelines.baselines.REGISTRY, or eval:module:factory).
"""
import base64
import importlib
import io
import json
import os
os.environ.setdefault("VISION_CACHE", "1")
os.environ.setdefault("OCR_FIELDS", "1")  # zero-token field answers for high-precision fields
os.environ.setdefault("REDACT_PII", "1")  # page path: black out OCR-read card/IBAN/email/phone/AHV lines (pattern-based)  # prompt-cache images: follow-up questions on the same crop are ~10% price
import re
import threading
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageOps
from pydantic import BaseModel

from .costs import full_image_baseline

ROOT = Path(__file__).parent
STATIC = ROOT / "static"
UPLOADS = ROOT / "uploads"
UPLOADS.mkdir(exist_ok=True)


class _EvalAdapter:
    """Wrap an eval pipeline (item, image) -> PipelineResult as answer(image, question)."""

    def __init__(self, name: str):
        from eval.pipelines.baselines import as_app_answer
        from eval.run_eval import get_pipeline
        self.answer = as_app_answer(get_pipeline(name))
        self.__name__ = f"eval:{name}"


_spec = os.getenv("PIPELINE", "app.mock_pipeline")
pipeline = _EvalAdapter(_spec[5:]) if _spec.startswith("eval:") else importlib.import_module(_spec)

REPLAY = os.getenv("DEMO_REPLAY") == "1"
# Live demo (release check C1): visual questions go to a real model (EVAL_MODEL, e.g. or:anthropic/claude-haiku-5.5).
# With DEMO_REPLAY=1 as well, a question whose live call fails (no key, network, provider error) is answered by
# the fixture replay instead, labelled REPLAY with the live error shown; without it, the failure is shown.
LIVE = os.getenv("DEMO_LIVE") == "1"
# Spend guard for live demos: once this server's billed live spend reaches the threshold (checked before each call,
# so the last call can overshoot it slightly; a stop threshold, not a billing maximum), model calls stop (OCR still
# answers locally) and, with DEMO_REPLAY=1, visual questions fall back to the labelled replay.
LIVE_MAX_USD = float(os.getenv("APP_LIVE_MAX_USD", "1.00"))
# Models the presenter may switch between at runtime (comma-separated model strings); default: just EVAL_MODEL.
APP_MODELS = [m.strip() for m in os.getenv("APP_MODELS", os.getenv("EVAL_MODEL", "")).split(",") if m.strip()]


def _on_device(model: str) -> bool:
    from urllib.parse import urlparse
    host = urlparse(os.getenv("OPENAI_BASE_URL", "")).hostname or ""
    return model.startswith("local:") and host in ("localhost", "127.0.0.1", "::1")


def _use_model(requested: str | None) -> str:
    """Model for this request: the requested one if allowed, else the default. Applied via EVAL_MODEL, which the
    pipeline reads at call time; requests are serialized by _replay_lock."""
    m = requested if requested in APP_MODELS else (APP_MODELS[0] if APP_MODELS else os.getenv("EVAL_MODEL", ""))
    if m:
        os.environ["EVAL_MODEL"] = m
    return m
LIVE_SPENT = 0.0
_replay_lock = threading.Lock()

app = FastAPI(title="Evidence Zoom")
# image_id -> {"path": Path, "w": int, "h": int, "questions": int, "fixture": str | None}
IMAGES: dict[str, dict] = {}


# ---- fixture forms (gold-labelled, from eval/data) ------------------------------------------
_FORMAT_HINT = re.compile(r"\s*answer (with|yes|a or b|in)\b.*$", re.I)


def _qkey(q: str) -> str:
    """Normalize a question for fixture lookup. Drops a trailing answer-format instruction
    ("Answer with the box numbers.", "Answer yes or no.", "Answer A or B.") and punctuation/case,
    so a judge can type the short form. No fuzzy matching: "did driver A tick 8" must never
    match "did driver B tick 8"."""
    q = _FORMAT_HINT.sub("", q.strip())
    return " ".join(re.sub(r"[^a-z0-9' ]+", " ", q.lower()).split())


def _load_fixtures() -> dict[str, dict]:
    from eval.schema import EvalItem
    out: dict[str, dict] = {}
    data = ROOT.parent / "eval" / "data"
    # layout 1 (development), layout 2 (held-out, later development), layout 3 fresh forms (v3b: configured from one
    # example of layout 3, frozen before these forms were generated). A judge can switch layouts in the menu.
    for items_file in (data / "demo_sample" / "items.jsonl", data / "accident_statement" / "items.jsonl",
                       data / "accident_statement_v2" / "items.jsonl", data / "accident_statement_v3b" / "items.jsonl",
                       data / "homework_v1" / "items.jsonl"):
        if not items_file.exists():
            continue
        for line in items_file.read_text().splitlines():
            if not line.strip():
                continue
            it = EvalItem(**json.loads(line))
            path = (items_file.parent / it.image_path).resolve()
            f = out.setdefault(it.image_id, {"path": path, "pair_id": it.pair_id, "items": {},
                                             "note": None, "questions": []})
            f["items"][_qkey(it.question)] = it
            f["questions"].append(it.question)
            if it.notes:
                f["note"] = it.notes
    return out


FIXTURES = _load_fixtures()


def _register(path: Path, fixture: str | None = None) -> dict:
    with Image.open(path) as im:
        w, h = im.size
    image_id = uuid.uuid4().hex[:12]
    import hashlib
    sha = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    IMAGES[image_id] = {"path": path, "w": w, "h": h, "questions": 0, "fixture": fixture, "sha": sha}
    return {"image_id": image_id, "width": w, "height": h, "fixture": fixture,
            "url": f"/api/images/{image_id}"}


@app.get("/api/claims")
def claims():
    """'What we measured' drawer: docs/claims.json (copy by claude-guanyu, approved by the release reviewer).
    Rows are served only when its status says approved; otherwise the drawer says they are pending review."""
    f = Path(os.getenv("CLAIMS_FILE", str(ROOT.parent / "docs" / "claims.json")))  # override for UI tests only
    if not f.exists():
        return {"approved": False, "status": "missing", "claims": []}
    d = json.loads(f.read_text())
    ok = str(d.get("status", "")).lower().startswith("approved")
    return {"approved": ok, "status": d.get("status"), "about": d.get("about") if ok else None,
            "claims": d.get("claims", []) if ok else []}


@app.get("/api/config")
def config():
    pairs: dict[str, list] = {}
    for fid, f in FIXTURES.items():
        pairs.setdefault(f["pair_id"] or fid, []).append(
            {"fixture": fid, "note": f["note"], "questions": f["questions"]})
    from .costs import MODEL as page_model
    from urllib.parse import urlparse
    base = os.getenv("OPENAI_BASE_URL", "")
    loopback = (urlparse(base).hostname or "") in ("localhost", "127.0.0.1", "::1")
    model = os.getenv("EVAL_MODEL", "")
    return {"pipeline": pipeline.__name__, "replay": REPLAY, "live": LIVE,
            # the "runs on this laptop" claim holds only for a local: model behind a loopback endpoint (release review)
            "on_device": bool(LIVE and model.startswith("local:") and loopback),
            "models": [{"id": m, "on_device": _on_device(m)} for m in APP_MODELS] if LIVE else [],
            "live_spent_usd": round(LIVE_SPENT, 4) if LIVE else None, "live_max_usd": LIVE_MAX_USD if LIVE else None,
            "model": os.getenv("EVAL_MODEL") if LIVE else None, "page_model": page_model,
            "route_model": os.getenv("EVAL_MODEL") if LIVE else os.getenv("APP_ROUTE_MODEL", page_model),
            "pairs": [{"pair_id": k, "forms": sorted(v, key=lambda x: x["fixture"])}
                      for k, v in sorted(pairs.items())]}


@app.post("/api/images/fixture/{fixture_id}")
def load_fixture(fixture_id: str):
    f = FIXTURES.get(fixture_id)
    if f is None or not f["path"].exists():
        raise HTTPException(404, "unknown fixture; run python -m eval.data.accident_statement.generate")
    return _register(f["path"], fixture_id)


@app.post("/api/images")
async def upload(file: UploadFile = File(...)):
    data = await file.read()
    try:
        with Image.open(io.BytesIO(data)) as im:
            im.verify()
        with Image.open(io.BytesIO(data)) as im:
            suffix = Path(file.filename or "x.png").suffix.lower() or ".png"
            if im.getexif().get(274) in range(2, 9):
                # Persist display-oriented pixels once so preview, OCR and evidence share a canvas.
                oriented = ImageOps.exif_transpose(im)
                if oriented.mode not in ("1", "L", "LA", "P", "RGB", "RGBA", "I;16"):
                    oriented = oriented.convert("RGB")
                buf = io.BytesIO()
                oriented.save(buf, format="PNG")
                data, suffix = buf.getvalue(), ".png"
    except Exception:
        raise HTTPException(400, "not an image")
    path = UPLOADS / f"{uuid.uuid4().hex}{suffix}"
    path.write_bytes(data)
    return _register(path)


@app.post("/api/images/sample")
def sample():
    path = STATIC / "sample.png"
    if not path.exists():
        raise HTTPException(404, "no sample image; run python -m app.make_sample")
    return _register(path, "demo" if "demo" in FIXTURES else None)


@app.get("/api/images/{image_id}")
def get_image(image_id: str):
    if image_id not in IMAGES:
        raise HTTPException(404)
    return FileResponse(IMAGES[image_id]["path"])


class Ask(BaseModel):
    image_id: str
    question: str
    model: str | None = None  # live only: one of APP_MODELS
    mode: str | None = None  # "claims" (form router) | "worksheet" (OCR text first) | "general" (whole page) | None = auto


@app.post("/api/compare")
def compare(req: Ask):
    """Live only: send the SAME question with the WHOLE original page to the same model (the eval harness's
    `full_image` baseline) and return its real answer, billed cost, tokens and time, for a side-by-side line."""
    global LIVE_SPENT
    if not LIVE:
        raise HTTPException(400, "the whole-page comparison needs live mode (scripts/demo-live.sh or demo-local.sh)")
    if LIVE_SPENT >= LIVE_MAX_USD:
        raise HTTPException(429, f"live spend stop threshold ${LIVE_MAX_USD:.2f} reached")
    meta = IMAGES.get(req.image_id)
    if meta is None:
        raise HTTPException(404, "unknown image_id")
    import time
    from eval.pipelines.baselines import full_image
    from eval.schema import EvalItem
    with Image.open(meta["path"]) as im:
        img = im.convert("RGB")
    with _replay_lock:
        model = _use_model(req.model)
    item = EvalItem(question_id="live-compare", image_id=req.image_id, image_path="", question=req.question, answer=None)
    t0 = time.perf_counter()
    r = full_image(model=model)(item, img).to_dict()
    ms = (time.perf_counter() - t0) * 1000
    usage = r.get("usage", [])
    cost = sum(u.get("cost_usd", 0) or 0 for u in usage)
    LIVE_SPENT += sum(u.get("cost_usd", 0) or 0 for u in usage if u.get("provider") not in ("local", None))
    tok = sum((u.get("input_image_tokens") or 0) + (u.get("input_text_tokens") or 0) +
              (u.get("cache_read_tokens") or 0) + (u.get("cache_write_tokens") or 0) for u in usage)
    return {"answer": r.get("answer"), "abstained": r.get("abstained"), "error": r.get("error"),
            "cost_usd": cost, "input_tokens": tok, "latency_ms": ms, "model": model, "image_px": [img.width, img.height]}


# Answer cache: a customer-service bot sees the same image and question again (re-sent screenshots, repeated
# questions). Same image bytes + same normalized question + same model -> the stored answer, 0 model tokens.
ANSWER_CACHE: dict = {}
ANSWER_CACHE_ON = os.getenv("APP_ANSWER_CACHE", "1") == "1"


@app.post("/api/ask")
def ask(req: Ask):
    meta = IMAGES.get(req.image_id)
    key = None
    if ANSWER_CACHE_ON and meta is not None:
        key = (meta.get("sha"), req.question.strip(), req.model, req.mode)  # exact question (codex answer-cache note)
        hit = ANSWER_CACHE.get(key)
        if hit is not None:
            import copy
            out = copy.deepcopy(hit)
            out["answer_cache"] = True
            out["result"]["usage"] = []  # nothing was sent to a model this time
            out["views"] = []
            meta["questions"] += 1
            out["question_index"] = meta["questions"] - 1
            return out
    out = _ask(req)
    r = out.get("result") or {}
    if key is not None and not r.get("error") and not out.get("live_error") and out.get("source") in ("model", "ocr"):
        ANSWER_CACHE[key] = out
    return out


def _ask(req: Ask):
    meta = IMAGES.get(req.image_id)
    if meta is None:
        raise HTTPException(404, "unknown image_id")
    with Image.open(meta["path"]) as im:
        img = im.convert("RGB")
    views: list[dict] = []
    visual = None
    try:
        import pipeline.visual as visual
    except ImportError:
        pass

    def sink(step, im):
        buf = io.BytesIO()
        im.save(buf, format="PNG")
        views.append({"step": step, "px": list(im.size),
                      "data_url": "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()})

    def billed(r) -> bool:  # did any real model call get served?
        d = r.to_dict() if hasattr(r, "to_dict") else r
        return any(u.get("provider") not in ("local", "replay", "estimate", None) for u in d.get("usage", []))

    live_error = None
    # route: the claims router for configured claim forms, the general assistant (OCR text first) otherwise
    # worksheet mode (OCR text first) where it was measured to save cost (printed worksheets, REPORT_homework_v3_heldout);
    # "general" = any image: whole page, because text-first lost on real documents (REPORT_realdocs.md)
    # One automatic route for every image (no picker): OCR -> configured-form crop -> the page cropped to its text
    # area and downscaled (pipeline.router). The API still accepts mode="worksheet"/"general" for experiments.
    worksheet = req.mode == "worksheet"
    general = worksheet or req.mode == "general"
    pipe = importlib.import_module("pipeline.general") if general else pipeline
    with _replay_lock:  # the visual module's hooks are process-global; one question at a time
        chosen = _use_model(req.model) if LIVE else None
        if visual is not None:
            visual.VIEW_SINK = sink
        # small local models do not reliably ask for pixels when OCR text is not enough
        # (REPORT_homework_v3_qwen7b.md): in general mode they get the whole page instead of the text step
        kw = {"text_step": worksheet and not (chosen or "").startswith("local:")} if general else {}
        fixture_item = FIXTURES.get(meta.get("fixture") or "", {}).get("items", {}).get(_qkey(req.question))
        if LIVE:
            global LIVE_SPENT
            capped = LIVE_SPENT >= LIVE_MAX_USD
            if capped and visual is not None:
                def _cap(*_a, **_k):
                    raise RuntimeError(f"live spend stop threshold ${LIVE_MAX_USD:.2f} reached (APP_LIVE_MAX_USD)")
                _cap.direct_zoom = True  # keep the shipped route; only the model call is blocked
                visual.CALL_OVERRIDE = _cap
            try:
                result = pipe.answer(img, req.question, **kw)
            finally:
                if visual is not None:
                    visual.VIEW_SINK = None
                    if capped:
                        visual.CALL_OVERRIDE = None
            d0 = result.to_dict() if hasattr(result, "to_dict") else result
            LIVE_SPENT += sum(u.get("cost_usd", 0) or 0 for u in d0.get("usage", [])
                              if u.get("provider") not in ("local", "replay", "estimate", None))
            d = result.to_dict() if hasattr(result, "to_dict") else result
            visual_tried = any(st.get("step") in ("zoom", "overview") for st in d.get("route", []))
            err = d.get("error") or ""
            if err and (chosen or "").startswith("local:") and ("Connection refused" in err or "URLError" in err):
                err = ("on-device model not reachable (is Ollama running? start it with "
                       "OLLAMA_CONTEXT_LENGTH=8192 ollama serve, or pick the cloud model)")
                d["error"] = err
            if REPLAY and visual is not None and visual_tried and err and not billed(d) and fixture_item:
                live_error = err  # live call failed on a fixture question: fall back to the labelled replay below
                views.clear()
                visual.VIEW_SINK = sink
            else:
                result = d
                if err and not billed(d):
                    live_error = err  # no replay for this question (e.g. an upload): show the failure, nothing invented
        replay_now = (REPLAY and not LIVE) or (live_error and fixture_item)
        if replay_now and visual is not None:
            # Key-free rehearsal: the real pipeline runs; only the vision-model calls are replayed from
            # the fixture's gold labels. Questions without a fixture label fail loudly (no invented answers).
            from pipeline.visual import replay
            item = fixture_item
            # Replayed calls are priced with the same model as the full-page baseline (a like-for-like meter);
            # APP_ROUTE_MODEL=claude-haiku-5-5 shows the billed "cheap model on the crop" comparison instead.
            from .costs import MODEL as _page_model
            route_model = os.getenv("APP_ROUTE_MODEL", _page_model)
            visual.CALL_OVERRIDE = (replay.oracle(item, img.size, price_as=route_model) if item
                                    else replay.unavailable(req.question))
        if not LIVE or (live_error and fixture_item):
            try:
                result = pipe.answer(img, req.question, **kw)
            finally:
                if visual is not None:
                    visual.CALL_OVERRIDE = None
                    visual.VIEW_SINK = None
    if hasattr(result, "to_dict"):
        result = result.to_dict()
    # the full-image baseline would produce one answer: use the final call's output size
    usage = result.get("usage") or [{}]
    out_tokens = usage[-1].get("output_tokens") or 60
    baseline = full_image_baseline(meta["w"], meta["h"],
                                   max(8, len(req.question) // 4), out_tokens,
                                   meta["questions"])
    meta["questions"] += 1
    providers = {u.get("provider") for u in result.get("usage", [])}
    if result.get("abstained") and result.get("error") and not (providers - {"local", None}):
        # The visual stage failed before any model call (no key / no fixture). A real run would still pay the
        # call it attempted (router@v2: the anchor crop or the full page; v1: the overview), so charge its
        # estimate; otherwise a failure would make the savings look better.
        from .costs import MODEL, TEXT_BASE_TOKENS, image_tokens, price
        from eval.schema import Usage
        tried = [st for st in result.get("route", []) if st.get("step") in ("zoom", "overview")]
        m = re.search(r"(\d+)x(\d+)px", (tried[0].get("note") or "") if tried else "")
        cw, ch = (int(m.group(1)), int(m.group(2))) if m else (meta["w"], meta["h"])
        u = Usage(len(result.get("route", [])), "estimate", MODEL, input_text_tokens=TEXT_BASE_TOKENS,
                  input_image_tokens=image_tokens(cw, ch), output_tokens=40, estimated=True,
                  note=f"{tried[0]['step'] if tried else 'page'} call ({cw}x{ch}px) a live run would pay; "
                       "not served (no answer)")
        price(u)
        result.setdefault("usage", []).append(u.__dict__)
    source = ("unavailable" if result.get("error") and result.get("abstained") else
              "replay" if "replay" in providers else
              # OCR only if no visual step ran: local vLLM calls also report provider "local"
              "ocr" if (providers <= {"local"} and result.get("route") and not result.get("abstained")
                        and not any(st.get("step") in ("overview", "zoom") for st in result["route"])
                        and not any(u.get("device") == "gpu" for u in result.get("usage", []))) else
              "mock" if pipeline.__name__ == "app.mock_pipeline" else "model")
    # model-free second opinion on tick questions (pixel ink inside the located boxes); gated by resolution
    check = None
    if source in ("model", "replay"):
        try:
            from pipeline.anchor import tick_check
            check = tick_check(img, req.question)
            if check.get("available") and not result.get("abstained") and result.get("answer") is not None:
                a = str(result["answer"]).lower()
                if check["kind"] == "tick_row":
                    check["agrees"] = a.strip().startswith(check["answer"])
                else:
                    got = sorted(int(x) for x in re.findall(r"\d+", a))
                    want = check["ticked"]
                    check["agrees"] = (got == want) if got or "none" not in a else (want == [])
        except Exception as e:
            check = {"available": False, "reason": f"pixel check failed ({type(e).__name__})"}
    ticket_lines = None
    if result.get("abstained"):  # human handoff: give the agent the page text the bot could see (local OCR, $0)
        try:
            from pipeline.general import _keyword_band, _lines
            from pipeline.ocr import recognize_page

            lines = _lines(recognize_page(img)[0])
            ticket_lines = [s["text"].strip() for s in lines][:60]
        except Exception:
            ticket_lines = None
    return {"result": result, "baseline": baseline, "source": source, "views": views, "live_error": live_error,
            "ticket_lines": ticket_lines,
            "check": check,
            "model": chosen, "on_device": _on_device(chosen or ""),
            "question_index": meta["questions"] - 1,
            "pipeline": pipe.__name__}


@app.get("/")
def index():
    # no-store + versioned asset URLs: a judge's browser must never mix a stale app.js/style.css with a newer page
    # (seen in the live check). Each asset URL carries its file's mtime, so any edit busts the cache.
    from fastapi.responses import HTMLResponse
    page = (STATIC / "index.html").read_text()
    for asset in ("app.js", "style.css"):
        v = int((STATIC / asset).stat().st_mtime)
        page = page.replace(f"/static/{asset}\"", f"/static/{asset}?v={v}\"")
    return HTMLResponse(page, headers={"Cache-Control": "no-store"})


app.mount("/static", StaticFiles(directory=STATIC), name="static")
