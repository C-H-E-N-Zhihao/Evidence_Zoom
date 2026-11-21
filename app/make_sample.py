"""Render the demo form shown by the "Load demo form" button.

Uses the eval generator so the demo and the eval set share one renderer.
Run:  .venv/bin/python -m app.make_sample
"""
import random
from pathlib import Path

from eval.data.accident_statement.generate import make_form, render

OUT = Path(__file__).parent / "static" / "sample.png"

if __name__ == "__main__":
    form = make_form(random.Random(2), "demo")
    render(form).save(OUT)
    print(f"wrote {OUT}: A ticks {form.a.ticks}, B ticks {form.b.ticks}, "
          f"rear hitter {form.rear_hitter}, A policy {form.a.policy}")
