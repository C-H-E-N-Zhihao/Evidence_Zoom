"""Evidence Zoom demo server.

Run:  .venv/bin/uvicorn app.server:app --reload --port 8000
Pipeline:  PIPELINE=app.mock_pipeline (default), any module exposing
           answer(image: PIL.Image.Image, question: str) -> dict | PipelineResult,
           or an eval pipeline name, e.g. PIPELINE=eval:full_image_cached
           (any name in eval.pipelines.baselines.REGISTRY, or eval:module:factory).
"""
import importlib
import io
import os
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

app = FastAPI(title="Evidence Zoom")
# image_id -> {"path": Path, "w": int, "h": int, "questions": int}
IMAGES: dict[str, dict] = {}


def _register(path: Path) -> dict:
    with Image.open(path) as im:
        w, h = im.size
    image_id = uuid.uuid4().hex[:12]
    IMAGES[image_id] = {"path": path, "w": w, "h": h, "questions": 0}
    return {"image_id": image_id, "width": w, "height": h,
            "url": f"/api/images/{image_id}"}


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
    return _register(path)


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
        result = pipeline.answer(im.convert("RGB"), req.question)
    if hasattr(result, "to_dict"):
        result = result.to_dict()
    # the full-image baseline would produce one answer: use the final call's output size
    usage = result.get("usage") or [{}]
    out_tokens = usage[-1].get("output_tokens") or 60
    baseline = full_image_baseline(meta["w"], meta["h"],
                                   max(8, len(req.question) // 4), out_tokens,
                                   meta["questions"])
    meta["questions"] += 1
    return {"result": result, "baseline": baseline,
            "question_index": meta["questions"] - 1,
            "pipeline": pipeline.__name__}


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
