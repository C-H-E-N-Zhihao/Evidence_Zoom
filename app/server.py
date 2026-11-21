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
import threading
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
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
_replay_lock = threading.Lock()

app = FastAPI(title="Evidence Zoom")
# image_id -> {"path": Path, "w": int, "h": int, "questions": int, "fixture": str | None}
IMAGES: dict[str, dict] = {}


# ---- fixture forms (gold-labelled, from eval/data) ------------------------------------------
def _qkey(q: str) -> str:
    return " ".join(q.lower().split())


def _load_fixtures() -> dict[str, dict]:
    from eval.schema import EvalItem
    out: dict[str, dict] = {}
    for items_file in (ROOT.parent / "eval" / "data" / "demo_sample" / "items.jsonl",
                       ROOT.parent / "eval" / "data" / "accident_statement" / "items.jsonl"):
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
    IMAGES[image_id] = {"path": path, "w": w, "h": h, "questions": 0, "fixture": fixture}
    return {"image_id": image_id, "width": w, "height": h, "fixture": fixture,
            "url": f"/api/images/{image_id}"}


@app.get("/api/config")
def config():
    pairs: dict[str, list] = {}
    for fid, f in FIXTURES.items():
        pairs.setdefault(f["pair_id"] or fid, []).append(
            {"fixture": fid, "note": f["note"], "questions": f["questions"]})
    return {"pipeline": pipeline.__name__, "replay": REPLAY,
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
        im = Image.open(io.BytesIO(data))
        im.verify()
    except Exception:
        raise HTTPException(400, "not an image")
    suffix = Path(file.filename or "x.png").suffix.lower() or ".png"
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


@app.post("/api/ask")
def ask(req: Ask):
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

    with _replay_lock:  # the visual module's hooks are process-global; one question at a time
        if visual is not None:
            visual.VIEW_SINK = sink
        if REPLAY and visual is not None:
            # Key-free rehearsal: the real pipeline runs; only the vision-model calls are replayed from
            # the fixture's gold labels. Questions without a fixture label fail loudly (no invented answers).
            from pipeline.visual import replay
            item = FIXTURES.get(meta["fixture"] or "", {}).get("items", {}).get(_qkey(req.question))
            visual.CALL_OVERRIDE = replay.oracle(item, img.size) if item else replay.unavailable(req.question)
        try:
            result = pipeline.answer(img, req.question)
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
        # The visual stage failed before any model call (no key / no fixture). A real run would still pay
        # the overview call, so charge its estimate; otherwise a failure would make the savings look better.
        from .costs import MODEL, image_tokens, price
        from eval.schema import Usage
        ov_w, ov_h = (512 * meta["w"] // max(meta["w"], meta["h"]), 512 * meta["h"] // max(meta["w"], meta["h"]))
        u = Usage(len(result.get("route", [])), "estimate", MODEL, input_text_tokens=450,
                  input_image_tokens=image_tokens(ov_w + 40, ov_h + 24), output_tokens=40, estimated=True,
                  note="overview call a live run would pay; not served (no answer)")
        price(u)
        result.setdefault("usage", []).append(u.__dict__)
    source = ("unavailable" if result.get("error") and result.get("abstained") else
              "replay" if "replay" in providers else
              "ocr" if providers <= {"local"} and result.get("route") and not result.get("abstained") else
              "mock" if pipeline.__name__ == "app.mock_pipeline" else "model")
    return {"result": result, "baseline": baseline, "source": source, "views": views,
            "question_index": meta["questions"] - 1,
            "pipeline": pipeline.__name__}


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
