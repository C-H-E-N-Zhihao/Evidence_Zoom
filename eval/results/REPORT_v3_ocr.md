### Run 2026-11-21T17:19:07+0100 · commit `b9b932b` · `eval/data/accident_statement_v3/items.jsonl` · input `clean` · spent $0.0000

Code: `pipeline/` tree `14d6378678b8` = frozen tag `freeze-router-v3`

Images: digest `a6b11370e2148082` over 12 files (compare with the set's images.sha256)

| pipeline | group | n | acc | joint | hit@0.3 | abstain | correct abstain | $/q | p50 ms | in tok/q | of which image | out tok/q | calls/q | pair follow | zoomed | zoom covers gold | acc when covered | GPU s/q |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `fn:pipeline.ocr:answer` | all | 96 | 12% | 0% | 0% | 100% | 100% | 0.00000 | 5 | 0 | – | 0 | 0.50 | 0% | 0% | – | – | 0.00 |
| `fn:pipeline.ocr:answer` | text | 48 | 25% | 0% | 0% | 100% | 100% | 0.00000 | 12 | 0 | – | 0 | 0.75 |  | 0% | – | – | 0.00 |
| `fn:pipeline.ocr:answer` | layout | 12 | 0% | 0% | 0% | 100% | – | 0.00000 | 10 | 0 | – | 0 | 1.00 |  | 0% | – | – | 0.00 |
| `fn:pipeline.ocr:answer` | visual | 36 | 0% | 0% | 0% | 100% | – | 0.00000 | 0 | 0 | – | 0 | 0.00 |  | 0% | – | – | 0.00 |

`*` = contains estimated usage. Cost per question excludes one-off indexing unless the pipeline recorded it in `usage`. `in tok/q` = all input tokens incl. images and cache reads, as the backend reported them; `of which image` is shown only when an image/text split was available (probe hint), otherwise `–` (the image tokens are inside `in tok/q`).
