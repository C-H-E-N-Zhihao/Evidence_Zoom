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
