# Real documents (public benchmarks): the text-first route loses; the whole page is the default for real images

All runs use Haiku 5.5 on both arms. Receipts were independently re-scored by codex-guanyu, including relaxed accuracy item by item.
Samples: realdocs_v1 has 100 DocVQA validation + 100 ChartQA test questions. realdocs_v2 is fresh (new seed, no row overlap): 70 DocVQA + 70 InfographicVQA + 70 ChartQA; 6 of its questions reuse a v1 image, and the gaps are identical without them.
Metrics: ANLS for DocVQA and InfographicVQA; Pix2Struct relaxed accuracy for ChartQA; substring accuracy for reference.

| sample | route version | metric | route | whole page | route cost / page cost |
|---|---|---|---:|---:|---:|
| v1 DocVQA (100) | original (v2 tag) | ANLS | 0.856 | 0.931 | $0.0301 / $0.0467 |
| v1 ChartQA (100) | original | relaxed | 45 | 52 | $0.0389 / $0.0156 |
| v1 DocVQA | + 448 px thumbnail (v3) | ANLS | 0.869 | 0.931 | $0.027 / $0.047 |
| v1 ChartQA | + 448 px thumbnail (v3) | relaxed | 41 | 52 | $0.032 / $0.016 |
| **v2 DocVQA (70)** | fix 2 (v4: exact answers + size rule) | ANLS | **0.900** | **0.951** | $0.0200 / $0.0345 (58%) |
| **v2 InfographicVQA (70)** | fix 2 | ANLS / relaxed | **0.619 / 40** | **0.761 / 50** | $0.0291 / $0.0232 |
| **v2 ChartQA (70)** | fix 2 (size rule: all 70 sent whole) | relaxed | **33** | **31** | $0.0115 / $0.0113 |

What we learned:
- **Printed text-heavy documents (DocVQA):** text first saves about 40% but loses about 0.05 ANLS. The two sets used different questions and route versions. Observed failures included OCR reading "W77" as "WIT".
- **Infographics:** OCR text loses the layout that ties numbers to labels. The route is both worse and more expensive, because it often asks for pixels after the text call.
- **Small charts:** the image is cheaper than its OCR text. The size rule now sends them whole, which brings the cost back to parity and accuracy level with the page.
- **Prediction record:** fix 2's predictions (message 171) passed on ChartQA and on DocVQA cost, and failed on DocVQA ANLS, InfographicVQA and overall. Open-weights models on RCP (claude-zhihao, 170) show the same ordering: whole page > route with thumbnail > plain route.

**Consequence for the app** (c1aeb22): General mode's "Any image" sends the whole page; OCR still runs locally for the boxes. "Worksheet: OCR text first" stays for printed worksheets, where the revised route scored 96/96 versus 95/96 at 69.5% of the API charge on the second held-out set (`REPORT_homework_v3_heldout.md`). The claim-form router (model-free OCR and template selection) is unchanged; that is where the large savings are measured.


## Page resolution control (realdocs_v2, message 175; receipt `realdocs_v2_lowres1568/`, $0.0393)

The app's whole-page call caps the long side at 1568 px; the evaluated whole-page arm sent the stored image (up to 2400 px).

| source (70 each) | 1568 px page | full-size page | text-first route (v4) |
|---|---:|---:|---:|
| DocVQA ANLS / cost per q | **0.954 / $0.00029** | 0.951 / $0.00049 | 0.900 / $0.00029 |
| InfographicVQA ANLS / cost per q | 0.690 / $0.00028 | **0.761 / $0.00033** | 0.619 / $0.00042 |

- **On scanned documents, downscaling the whole page to 1568 px is the frugal winner.** It matches full resolution at 42% lower cost (58% of the charge), and beats the text-first route at the same cost.
- **Tall infographics lose detail when downscaled.** 31 of the 65 infographic pages are taller than 2:1, against 2 of 70 scans and no charts. The app now keeps up to 2400 px for pages taller than 2:1. That rule was chosen after this run (development), so its effect is not measured yet.
- The run records `eval_dirty: true` because its item list (`items_doc_info.jsonl`, the 140 non-chart questions) was still uncommitted when it ran. It is committed in 9792e2c; no harness code changed.

## Resolution frontier (message 177; receipt `realdocs_v2_lowres_frontier/`, predictions committed before the run)

| page long side | DocVQA ANLS | DocVQA $ per q | InfographicVQA ANLS |
|---|---:|---:|---:|
| full size (≤ 2400 px) | 0.951 | 0.00049 | 0.761 |
| 1568 px | 0.954 | 0.00029 | 0.690 |
| **1024 px** | **0.951** | **0.00016** | 0.669 |
| 768 px | 0.894 | 0.00012 | 0.574 |

- **Scans:** full accuracy down to 1024 px, at about a third of the full-size cost. Accuracy drops only at 768 px.
- **Infographics:** they lose with every step down.
- **Predictions (177):** DocVQA 1024 within 0.03 and 768 drops by more than 0.05: met. InfographicVQA 768 below 0.60: met. 1024 px at most 50% of the 1568 px cost: missed narrowly (55%).
- **App:** stays at 1568 px (2400 px for pages taller than 2:1). The margin is free in accuracy and costs about $0.0001 per question.
