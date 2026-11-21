"""Smoke test of the key-free demo, through the same HTTP API the browser uses ($0, no key).

    .venv/bin/python scripts/smoke_demo.py

Checks the judge script in DEMO.md:
  1. policy number on fixture eas-002a      -> source LIVE OCR, correct value, evidence box on the value
  2. "which boxes did driver B tick?" on a  -> REPLAY, 8, box on row 8, one image sent (anchor crop on macOS,
                                               full page where the OCR helper is missing)
  3. same question on form b                -> REPLAY, 7 (the only difference between the two forms)
  4. a question with no fixture label       -> NO ANSWER (nothing invented)
Exit code 0 if all pass. OCR needs macOS (Apple Vision); on other systems step 1 is reported as skipped.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
# Pinned, not defaulted: an inherited live configuration must not change what this test exercises.
os.environ["PIPELINE"] = "pipeline.router"
os.environ["DEMO_REPLAY"] = "1"
os.environ["DEMO_LIVE"] = "0"  # offline smoke: never inherit live mode from the presenter's shell

from fastapi.testclient import TestClient  # noqa: E402

from app.server import FIXTURES, _qkey, app  # noqa: E402

TICKS = "Which circumstance boxes did driver B tick? Answer with the box numbers."
POLICY = "What is vehicle A's insurance policy number?"
failures = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))
    if not ok:
        failures.append(name)


def ask(c: TestClient, image_id: str, q: str) -> dict:
    r = c.post("/api/ask", json={"image_id": image_id, "question": q})
    r.raise_for_status()
    return r.json()


def main() -> int:
    c = TestClient(app)
    cfg = c.get("/api/config").json()
    print(f"pipeline={cfg['pipeline']} replay={cfg['replay']} fixture pairs={len(cfg['pairs'])}")
    check("replay mode on", cfg["replay"] is True)
    check("router pipeline", cfg["pipeline"] == "pipeline.router", cfg["pipeline"])
    check("fixture eas-002 present", "eas-002a" in FIXTURES and "eas-002b" in FIXTURES)
    if failures:  # wrong configuration: the remaining checks would test the wrong thing
        print("\nsmoke test: ABORTED, configuration checks failed:", failures)
        return 1

    a = c.post("/api/images/fixture/eas-002a").json()["image_id"]
    b = c.post("/api/images/fixture/eas-002b").json()["image_id"]
    gold_policy = FIXTURES["eas-002a"]["items"][_qkey(POLICY)].answer

    print("1. policy number (OCR)")
    d = ask(c, a, POLICY)
    if sys.platform != "darwin":
        print(f"  [SKIP] OCR needs macOS; got source={d['source']}")
    else:
        check("source is LIVE OCR", d["source"] == "ocr", d["source"])
        check("answer matches the form", d["result"]["answer"] == gold_policy,
              f"{d['result']['answer']!r} vs {gold_policy!r}")
        check("evidence box returned", bool(d["result"]["evidence_boxes"]))
        check("cost $0", sum(u["cost_usd"] for u in d["result"]["usage"]) == 0)

    print("2. ticks on form a (visual route, replayed)")
    d = ask(c, a, TICKS)
    steps = [s["step"] for s in d["result"]["route"]]
    check("source is REPLAY", d["source"] == "replay", d["source"])
    check("answer 8", d["result"]["answer"] == "8", repr(d["result"]["answer"]))
    zoom = next((s for s in d["result"]["route"] if s["step"] == "zoom"), {})
    want = "anchor:ticks" if sys.platform == "darwin" else "full page"
    check(f"route is one zoom ({want}) -> answer, no overview", steps[-2:] == ["zoom", "answer"]
          and "overview" not in steps and (zoom.get("target") or "").startswith(want),
          " > ".join(f"{s['step']}:{s.get('target')}" for s in d["result"]["route"]))
    views = [(v["step"], v.get("px")) for v in d["views"]]
    check("one image returned (the crop sent)", [v[0] for v in views] == ["zoom"], str(views))
    box = d["result"]["evidence_boxes"][0]["box"] if d["result"]["evidence_boxes"] else None
    gold = FIXTURES["eas-002a"]["items"][_qkey(TICKS)].evidence_boxes[0]
    check("evidence box lands on B's tick 8", box is not None and abs(box[1] - gold[1]) < 0.005,
          f"{box} vs {gold}")

    print("3. same question on form b")
    d = ask(c, b, TICKS)
    check("answer changes to 7", d["result"]["answer"] == "7", repr(d["result"]["answer"]))

    print("4. question without a fixture label")
    d = ask(c, b, "Is there a dog in the picture?")
    check("NO ANSWER, nothing invented", d["source"] == "unavailable" and d["result"]["answer"] is None,
          d["source"])

    print("\nsmoke test:", "OK" if not failures else f"{len(failures)} FAILED: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
