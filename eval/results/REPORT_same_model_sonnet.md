### Run 2026-11-21T17:03:54+0100 · commit `c8fa47a` · `eval/data/accident_statement/items.jsonl` · input `clean` · spent $0.4045

Code: `pipeline/` tree `645fc0328012` **≠ frozen tag `freeze-router-v2`**

Images: digest `09c6e9dbea93f650` over 12 files (compare with the set's images.sha256)

| pipeline | group | n | acc | joint | hit@0.3 | abstain | correct abstain | $/q | p50 ms | in tok/q | of which image | out tok/q | calls/q | pair follow | zoomed | zoom covers gold | acc when covered | GPU s/q |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `pipeline.router:factory` | all | 96 | 100% | 96% | 96% | 12% | 100% | 0.00169 | 1022 | 636 | – | 42 | 1.38 | 100% | 50% | 100% | 100% | 0.00 |
| `pipeline.router:factory` | text | 48 | 100% | 100% | 100% | 25% | 100% | 0.00144 | 340 | 685 | – | 7 | 1.00 |  | 25% | – | – | 0.00 |
| `pipeline.router:factory` | layout | 12 | 100% | 100% | 100% | 0% | – | 0.00000 | 11 | 0 | – | 0 | 1.00 |  | 0% | – | – | 0.00 |
| `pipeline.router:factory` | visual | 36 | 100% | 92% | 92% | 0% | – | 0.00258 | 1703 | 783 | – | 102 | 2.00 |  | 100% | 100% | 100% | 0.00 |
| `full_image_cached@or:anthropic/claude-sonnet-5.5` | all | 96 | 100% | 48% | 48% | 12% | 100% | 0.00253 | 2167 | 4920 | – | 64 | 1.00 | 100% | 0% | – | – | 0.00 |
| `full_image_cached@or:anthropic/claude-sonnet-5.5` | text | 48 | 100% | 44% | 44% | 25% | 100% | 0.00362 | 2115 | 4913 | – | 40 | 1.00 |  | 0% | – | – | 0.00 |
| `full_image_cached@or:anthropic/claude-sonnet-5.5` | layout | 12 | 100% | 0% | 0% | 0% | – | 0.00097 | 2111 | 4920 | – | 43 | 1.00 |  | 0% | – | – | 0.00 |
| `full_image_cached@or:anthropic/claude-sonnet-5.5` | visual | 36 | 100% | 67% | 67% | 0% | – | 0.00159 | 2421 | 4929 | – | 103 | 1.00 |  | 0% | – | – | 0.00 |

`*` = contains estimated usage. Cost per question excludes one-off indexing unless the pipeline recorded it in `usage`. `in tok/q` = all input tokens incl. images and cache reads, as the backend reported them; `of which image` is shown only when an image/text split was available (probe hint), otherwise `–` (the image tokens are inside `in tok/q`).
