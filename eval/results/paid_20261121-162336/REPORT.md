### Run 2026-11-21T16:33:37+0100 · commit `74ea119` · `eval/data/accident_statement/items.jsonl` · input `clean` · spent $0.3174

Code: `pipeline/` tree `25220c27ceff` **≠ frozen tag `freeze-anchor-ocr-v1`**

| pipeline | group | n | acc | joint | hit@0.3 | abstain | correct abstain | $/q | p50 ms | in tok/q | of which image | out tok/q | calls/q | pair follow | zoomed | zoom covers gold | acc when covered | GPU s/q |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `full_image_cached@or:anthropic/claude-sonnet-5.5` | all | 96 | 100% | 42% | 42% | 12% | 100% | 0.00253 | 2010 | 4920 | – | 64 | 1.00 | 100% | 0% | – | – | 0.00 |
| `full_image_cached@or:anthropic/claude-sonnet-5.5` | text | 48 | 100% | 42% | 42% | 25% | 100% | 0.00362 | 1958 | 4913 | – | 40 | 1.00 |  | 0% | – | – | 0.00 |
| `full_image_cached@or:anthropic/claude-sonnet-5.5` | layout | 12 | 100% | 0% | 0% | 0% | – | 0.00098 | 1905 | 4920 | – | 44 | 1.00 |  | 0% | – | – | 0.00 |
| `full_image_cached@or:anthropic/claude-sonnet-5.5` | visual | 36 | 100% | 56% | 56% | 0% | – | 0.00159 | 2196 | 4929 | – | 103 | 1.00 |  | 0% | – | – | 0.00 |
| `full_image@or:anthropic/claude-haiku-5.5` | all | 96 | 95% | 42% | 42% | 15% | 100% | 0.00054 | 1467 | 4920 | – | 103 | 1.00 | 17% | 0% | – | – | 0.00 |
| `full_image@or:anthropic/claude-haiku-5.5` | text | 48 | 100% | 69% | 69% | 25% | 100% | 0.00051 | 1418 | 4913 | – | 41 | 1.00 |  | 0% | – | – | 0.00 |
| `full_image@or:anthropic/claude-haiku-5.5` | layout | 12 | 100% | 8% | 8% | 0% | – | 0.00052 | 1403 | 4920 | – | 46 | 1.00 |  | 0% | – | – | 0.00 |
| `full_image@or:anthropic/claude-haiku-5.5` | visual | 36 | 86% | 25% | 25% | 6% | – | 0.00059 | 1863 | 4929 | – | 204 | 1.00 |  | 0% | – | – | 0.00 |
| `gold_crop_px:384@or:anthropic/claude-haiku-5.5` | all | 96 | 65% | 39% | 39% | 45% | 100% | 0.00024 | 2144 | 1019 | – | 269 | 1.00 | 0% | 88% | 100% | 60% | 0.00 |
| `gold_crop_px:384@or:anthropic/claude-haiku-5.5` | text | 48 | 60% | 47% | 47% | 65% | 100% | 0.00029 | 2076 | 1492 | – | 278 | 1.00 |  | 75% | 100% | 47% | 0.00 |
| `gold_crop_px:384@or:anthropic/claude-haiku-5.5` | layout | 12 | 0% | 0% | 0% | 75% | – | 0.00013 | 1389 | 358 | – | 195 | 1.00 |  | 100% | 100% | 0% | 0.00 |
| `gold_crop_px:384@or:anthropic/claude-haiku-5.5` | visual | 36 | 92% | 44% | 44% | 8% | – | 0.00020 | 2153 | 608 | – | 282 | 1.00 |  | 100% | 100% | 92% | 0.00 |

`*` = contains estimated usage. Cost per question excludes one-off indexing unless the pipeline recorded it in `usage`. `in tok/q` = all input tokens incl. images and cache reads, as the backend reported them; `of which image` is shown only when an image/text split was available (probe hint), otherwise `–` (the image tokens are inside `in tok/q`).

### Run 2026-11-21T16:38:32+0100 · commit `d527dc4` · `eval/data/accident_statement/items.jsonl` · input `clean` · spent $0.0292

Code: `pipeline/` tree `25220c27ceff` = frozen tag `freeze-router-v2`

| pipeline | group | n | acc | joint | hit@0.3 | abstain | correct abstain | $/q | p50 ms | in tok/q | of which image | out tok/q | calls/q | pair follow | zoomed | zoom covers gold | acc when covered | GPU s/q |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `pipeline.router:factory_anchor` | all | 96 | 100% | 96% | 96% | 12% | 100% | 0.00010 | 733 | 636 | – | 78 | 1.38 | 100% | 50% | 100% | 100% | 0.00 |
| `pipeline.router:factory_anchor` | text | 48 | 100% | 100% | 100% | 25% | 100% | 0.00007 | 237 | 685 | – | 11 | 1.00 |  | 25% | – | – | 0.00 |
| `pipeline.router:factory_anchor` | layout | 12 | 100% | 100% | 100% | 0% | – | 0.00000 | 12 | 0 | – | 0 | 1.00 |  | 0% | – | – | 0.00 |
| `pipeline.router:factory_anchor` | visual | 36 | 100% | 92% | 92% | 0% | – | 0.00017 | 1744 | 783 | – | 192 | 2.00 |  | 100% | 100% | 100% | 0.00 |
| `pipeline.anchor:factory_then_overview` | all | 96 | 98% | 51% | 51% | 15% | 100% | 0.00020 | 1937 | 784 | – | 246 | 1.47 | 67% | 47% | 93% | 98% | 0.00 |
| `pipeline.anchor:factory_then_overview` | text | 48 | 96% | 31% | 31% | 29% | 100% | 0.00023 | 2102 | 800 | – | 302 | 1.19 |  | 19% | 67% | 83% | 0.00 |
| `pipeline.anchor:factory_then_overview` | layout | 12 | 100% | 0% | 0% | 0% | – | 0.00018 | 1887 | 724 | – | 216 | 1.00 |  | 0% | – | – | 0.00 |
| `pipeline.anchor:factory_then_overview` | visual | 36 | 100% | 89% | 89% | 0% | – | 0.00017 | 1496 | 783 | – | 182 | 2.00 |  | 100% | 100% | 100% | 0.00 |

`*` = contains estimated usage. Cost per question excludes one-off indexing unless the pipeline recorded it in `usage`. `in tok/q` = all input tokens incl. images and cache reads, as the backend reported them; `of which image` is shown only when an image/text split was available (probe hint), otherwise `–` (the image tokens are inside `in tok/q`).

### Run 2026-11-21T16:44:03+0100 · commit `6be5a59` · `eval/data/accident_statement/items.jsonl` · input `phone_photo` · spent $0.1778

> Geometric degradation: gold boxes no longer align exactly, so `joint` and `hit@0.3` and any gold_crop rows are approximate.

Code: `pipeline/` tree `4cfcded0a0ba` **≠ frozen tag `freeze-router-v2`**

| pipeline | group | n | acc | joint | hit@0.3 | abstain | correct abstain | $/q | p50 ms | in tok/q | of which image | out tok/q | calls/q | pair follow | zoomed | zoom covers gold | acc when covered | GPU s/q |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `pipeline.router:factory_anchor` | all | 96 | 99% | 14% | 14% | 12% | 100% | 0.00010 | 694 | 473 | – | 107 | 1.35 | 83% | 50% | 100% | 97% | 0.00 |
| `pipeline.router:factory_anchor` | text | 48 | 100% | 0% | 0% | 25% | 100% | 0.00006 | 209 | 494 | – | 19 | 1.00 |  | 25% | – | – | 0.00 |
| `pipeline.router:factory_anchor` | layout | 12 | 100% | 0% | 0% | 0% | – | 0.00000 | 4 | 0 | – | 0 | 1.00 |  | 0% | – | – | 0.00 |
| `pipeline.router:factory_anchor` | visual | 36 | 97% | 33% | 33% | 0% | – | 0.00019 | 2314 | 603 | – | 259 | 1.94 |  | 100% | 100% | 97% | 0.00 |
| `full_image_cached@or:anthropic/claude-sonnet-5.5` | all | 96 | 99% | 13% | 13% | 12% | 100% | 0.00175 | 1589 | 1864 | – | 97 | 1.00 | 83% | 0% | – | – | 0.00 |
| `full_image_cached@or:anthropic/claude-sonnet-5.5` | text | 48 | 100% | 0% | 0% | 25% | 100% | 0.00174 | 1548 | 1857 | – | 41 | 1.00 |  | 0% | – | – | 0.00 |
| `full_image_cached@or:anthropic/claude-sonnet-5.5` | layout | 12 | 100% | 0% | 0% | 0% | – | 0.00069 | 1488 | 1864 | – | 45 | 1.00 |  | 0% | – | – | 0.00 |
| `full_image_cached@or:anthropic/claude-sonnet-5.5` | visual | 36 | 97% | 31% | 31% | 0% | – | 0.00213 | 3390 | 1873 | – | 187 | 1.00 |  | 0% | – | – | 0.00 |

`*` = contains estimated usage. Cost per question excludes one-off indexing unless the pipeline recorded it in `usage`. `in tok/q` = all input tokens incl. images and cache reads, as the backend reported them; `of which image` is shown only when an image/text split was available (probe hint), otherwise `–` (the image tokens are inside `in tok/q`).

## Spend (OpenRouter key status after the sweep)

billed total $0.5291, remaining $9.4709 of $10 (includes the two smoke tests, $0.0168).
