"""Render the demo form shown by the "Load demo form" button, plus its gold items.

Uses the eval generator so the demo and the eval set share one renderer, and
regenerates eval/data/demo_sample/items.jsonl so its gold labels always match.
Run:  .venv/bin/python -m app.make_sample
"""
import json
import random
from pathlib import Path

from eval.data.accident_statement.generate import items_for, make_form, render

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "app" / "static" / "sample.png"
ITEMS = ROOT / "eval" / "data" / "demo_sample" / "items.jsonl"

if __name__ == "__main__":
    form = make_form(random.Random(2), "demo")
    render(form).save(OUT)
    items = items_for(form, pair_id="demo", note="app demo form (app/make_sample.py, seed 2)")
    for it in items:
        it["image_path"] = "../../../app/static/sample.png"
    ITEMS.parent.mkdir(parents=True, exist_ok=True)
    ITEMS.write_text("\n".join(json.dumps(i) for i in items) + "\n")
    print(f"wrote {OUT}: A ticks {form.a.ticks}, B ticks {form.b.ticks}, "
          f"rear hitter {form.rear_hitter}; {len(items)} items -> {ITEMS}")
