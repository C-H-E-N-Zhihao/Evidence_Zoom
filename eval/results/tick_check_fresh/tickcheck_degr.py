import json, re, sys
from PIL import Image, ImageFilter
from pipeline.anchor import tick_check
from bench.ocr_robustness import DEGRADATIONS, _perspective, _rotate, _jpeg
norm = lambda s: ",".join(sorted(re.findall(r"\d+", str(s)))) or str(s).strip().lower()
conds = {**{k: DEGRADATIONS[k] for k in ("blur_1.5", "perspective_3%", "rotate_5", "jpeg_q40", "scale_1280")},
         "photo_fullres": lambda im: _jpeg(_perspective(_rotate(im, 2.5), 0.03).filter(ImageFilter.GaussianBlur(1.2)), 55)}
for d in sys.argv[1:]:
    items = [json.loads(l) for l in open(d + "/items.jsonl")]
    items = [it for it in items if "tick" in it["question"].lower()]
    for c, f in conds.items():
        ok = wrong = un = 0
        for it in items:
            im = f(Image.open(f'{d}/images/{it["image_id"]}.png').convert("RGB"))
            r = tick_check(im, it["question"])
            if not r["available"]: un += 1; continue
            g = str(it["answer"]).strip().lower()
            good = (norm(r["answer"]) == norm(g)) if r["kind"] == "ticks" else (r["answer"] == g)
            ok += good; wrong += not good
        print(f"{d.split('/')[-1]:14s} {c:15s} correct {ok:2d} wrong {wrong:2d} unavailable {un:2d} / {len(items)}", flush=True)
