# receipts_v1: real receipts from CORD-v2 (blind evaluation set)

- Source: `naver-clova-ix/cord-v2`, split `test` (only 100 rows exist). 60 receipts sampled by seed (`RC_SEED=3131`) through the Hugging Face datasets-server API.
- 241 questions: total (57), change (36), tax (28), price of first menu item (60), unanswerable (60; rotating list of fields CORD never annotates: website, cashier name, email, loyalty number, reservation name, VAT number).
- `answer` is the gold string exactly as printed (Indonesian rupiah, no symbol; separators vary by receipt: `30.000`, `30,000`, `30000`). `accepted_answers` adds separator variants (`,` / `.` / none) and `Rp ` prefixed forms. Scoring should normalise numerically anyway.
- `evidence_boxes`: 121 items (total, change, tax) have one normalized box covering the whole annotated line (label plus value) from CORD `valid_line` quads. Item-price questions have none.
- Images: long side capped at 2400 px (LANCZOS); original size is in `notes`. Sizes range 228x336 to 1800x2400. Disk about 54 MB.
- Caveats: some receipts are Indonesian/handwritten-style or low-resolution; first-item name in a question comes from the gold `nm` field and may be abbreviated; a receipt may list several lines with the same item name.

Regenerate: `SSL_CERT_FILE=$(python -m certifi) python3 -m eval.data.receipts_v1.fetch` (about 15 min; rate-limited, HTTP 429/5xx are retried with backoff). Images are gitignored; compare with `images.sha256` (Pillow version dependent).
