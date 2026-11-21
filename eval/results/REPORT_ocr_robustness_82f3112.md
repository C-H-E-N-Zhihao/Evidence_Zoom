# OCR route robustness to scan / phone-photo degradations

`python -m bench.ocr_robustness` · 60 OCR-eligible items (48 answerable text/layout, 12 unanswerable) from `eval/data/accident_statement/items.jsonl` · Apple Vision, local, $0.

| degradation | exit correct | **exit wrong** | fallback to visual |
|---|---:|---:|---:|
| clean | 48 | **0** | 12 |
| scale_1280 | 48 | **0** | 12 |
| scale_1024 | 48 | **0** | 12 |
| scale_768 | 24 | **0** | 36 |
| jpeg_q40 | 48 | **0** | 12 |
| blur_1.5 | 48 | **0** | 12 |
| rotate_2 | 48 | **0** | 12 |
| rotate_5 | 48 | **0** | 12 |
| perspective_3% | 48 | **0** | 12 |
| phone_photo | 48 | **0** | 12 |
