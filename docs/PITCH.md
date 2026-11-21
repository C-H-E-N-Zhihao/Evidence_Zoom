# Evidence Zoom: pitch draft (3–4 minutes + Q&A)

> **Superseded for wording by `docs/deck/`** (9 slides, codex-guanyu's pitch verdict d8a0a67 applied). This file keeps the Q&A preparation and the rationale; where the two differ, the deck wins.

Author: claude-guanyu (draft). Reviewer: codex-guanyu (release gate): nothing here is final until it passes `docs/RELEASE_CHECKLIST.md`. Presenter: Andrew (proposed). Every number comes from the **safe** list of `docs/NARRATIVE.md`. Each is tagged [dev] (development layout, the 12 forms the rules were written on), [held-out] or [blind]. **[PENDING …]** marks numbers the paid sweep must fill before the pitch; if they are not filled, the slide drops them.

---

## Slide 1: the problem (20 s)

> A claims handler opens a European Accident Statement and asks three things: *what is vehicle A's policy number? Which boxes did driver B tick? Who hit whom?*
> Today's AI answer: send the whole page to a large vision model, for every question. That is the expensive default, and the answer comes with no proof of where it came from.

Visual: the accident statement form, three questions overlaid.

## Slide 2: the idea (30 s)

> Read the form the way a claims handler does: **look only where the answer is.**
> 1. Printed fields: local OCR answers them, for **$0**.
> 2. Ticks and sketches: the form's own layout tells us which pixels matter. The model sees **only that crop**, not the page.
> 3. Every OCR or crop answer is **boxed on the original page**, so the handler can check it in a second.

Visual: page → OCR boxes → one row-aligned crop → answer with its box.

## Slide 3: live demo (60 s)

Script (see `docs/NARRATIVE.md` §2; run on the demo Mac):
1. Policy number → **LIVE OCR**, green box, $0.
2. "Which boxes did driver B tick?" → the crop that was actually sent, the answer, and the box on the original row.
3. Switch to the twin form where one tick moved → the answer changes and the box moves.
4. Off-script question → "no answer", with the reason.

**[PENDING: release checklist C1]** If the live model path is ready, steps 2–3 are live (cheap model, capped). Otherwise they are **labelled replays**, and the presenter says so in one sentence: "the visual answers here replay the model's recorded answers to show the mechanics; live numbers are on the next slide".

## Slide 4: does it work? (40 s): measured, open models on our GPUs, $0

| [dev] 36 visual questions | full page | the right crop (chosen from the layout) |
|---|---:|---:|
| Qwen2.5-VL-72B | 20/36 | **36/36** |
| Qwen2.5-VL-7B | 15/36 | 22/36 |

> The **7B** model reading our crop scored 22/36. The **72B** model reading the whole page scored 20/36.
> And the vision models **cannot pick the region themselves** (evidence covered in 0/24 and 3/36 of their zooms), so the layout has to tell them where to look.

Plus: OCR answered **48/96** questions locally, all correct, **0 wrong**, also on phone-photo, blurred, compressed and tilted inputs [dev].

Say "one layout, 36 questions", and quote both counts. No "beats", no "matches".

## Slide 5: is it frugal? (30 s)

> Half of the questions never reach a model: OCR answers them for $0 [dev].
> For the rest, the model sees only the crop. **Billed** on Claude 5.5 (OpenRouter), the whole route uses **636 input tokens per question**, against **4,920** for one full page [dev].
> Billed, 96 questions [dev]: router + Haiku **96/96 at $0.00010 per question**; Sonnet on the cached page **96/96 at $0.00253**; Haiku on the page 91/96 at $0.00054. **Same accuracy at about 1/25 of the cost.** [PENDING release review: codex-guanyu]
> On our own GPUs: 7B on the crop needs ~1/27 of the compute of 72B on the page (estimated, FLOPs proxy).

If the sweep numbers are not in, keep only the OCR line and the 4,900-token line.

## Slide 6: we tried to break it (40 s): the judgement slide

> We froze the code and tested on data it had never seen.
> - **A second layout** of the same form: the template rules found nothing to anchor on (0/48 OCR, 0/36 crops) [held-out]. Our first fallback then did **worse** than just sending the page, and made models invent missing fields. We changed the fallback to the whole page (router v2).
> - **Four new document types** (breaker panel, garage invoice, travel claim, vehicle damage; 320 questions, generated without looking at our code): router v2 sent every question to the whole page, with **0 wrong OCR answers** [blind].
> So: Evidence Zoom saves money **on forms it is configured for**, and elsewhere it degrades to the normal cost instead of guessing on the OCR side.

**[PENDING: model accuracy on the blind families]** Until it is measured, do not say anything about answer accuracy there.

## Slide 7: why this fits AXA (20 s)

> Insurance runs on **standard forms**: the European Accident Statement is one fixed layout across Europe. Configuring a template once is cheap; every claim after that is frugal and auditable.
> Next: onboard templates from one annotated example; a layout-independent region selector; question-driven image tokens (our FlexTok probe).

## Slide 8: how we worked (10 s, optional)

> Five agents and three people, coordinated through Git. Every number on these slides has a run file, a code version and a reviewer.

---

## Q&A preparation (likely judge questions)

| Question | Answer | Source |
|---|---|---|
| "Isn't this hard-coded to your form?" | Yes, per template, and we measured it: on an unseen layout and on 4 new document types the rules find nothing and route to the whole page. That is the honest boundary. | NARRATIVE §3, §7 |
| "Your data is synthetic." | Yes. Real forms are the next step. We tested robustness to phone photos, blur, compression and tilt; OCR made no wrong answers there [dev]. | REPORT_ocr_robustness_82f3112 |
| "Why not just use a big model on the page?" | It is the expensive default, and in our tests it was less accurate on ticks and sketches than a model reading the right crop (72B: 20/36 page vs 36/36 crop) [dev]. | model_scale/REPORT.md |
| "Does it hallucinate?" | Missing-field questions: 72B declined 12/12 on the route; 7B invented a value in 2/12 [dev]. On the unseen layout our first fallback made it worse, which is why router v2 sends the whole page. | e2e, e2e_frozen |
| "How much does it cost?" | **[PENDING: billed sweep]** Until then: OCR answers are $0, a full page bills ~4,900 tokens, and the crop is a fraction of the page in pixels. | sweep REPORT |
| "Can the model not just zoom by itself?" | We tested that: at 7B and 72B, model-chosen zooms covered the evidence in 0/24 and 3/36 cases. | model_scale/REPORT.md |
