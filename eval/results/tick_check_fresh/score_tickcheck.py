import json, sys, re
from pathlib import Path
from PIL import Image
from pipeline.anchor import tick_check
norm = lambda s: ",".join(sorted(re.findall(r"\d+", str(s)))) or str(s).strip().lower()
for d in sys.argv[1:]:
    d = Path(d); n = ok = unav = wrong = 0; fails = []
    for l in open(d / "items.jsonl"):
        it = json.loads(l)
        q = it["question"].lower()
        if "tick" not in q:
            continue
        img = Image.open((d / it["image_path"]).resolve() if (d / it["image_path"]).exists() else d / "images" / f'{it["image_id"]}.png').convert("RGB")
        r = tick_check(img, it["question"])
        n += 1
        if not r["available"]:
            unav += 1; fails.append((it["question_id"], "unavailable", r["reason"])); continue
        g = it["answer"]
        good = norm(r["answer"]) == norm(g) if any(c.isdigit() for c in str(g)) or r["kind"] == "ticks" else r["answer"] == str(g).strip().lower()
        if r["kind"] == "ticks" and str(g).strip().lower() in ("none", "no boxes", ""):
            good = r["answer"] == "none"
        ok += good; wrong += (not good)
        if not good: fails.append((it["question_id"], r["answer"], g))
    print(f"{d.name}: tick questions {n}, correct {ok}, wrong {wrong}, unavailable {unav}")
    for f in fails[:6]: print("   ", f)
