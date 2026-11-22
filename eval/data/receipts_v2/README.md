# receipts_v2: real receipts from CORD-v2 **validation** (fresh held-out set for the shipped app)

- Built by claude-guanyu (message 217) with the receipts_v1 generator unchanged except the split (`validation`, which no route, threshold or OCR field rule was developed on), the seed (`RC_SEED=2222`) and question-id prefix `rv-`. Built on an RCP CPU job (`guanyu-fetch-receipts-v2-1122-0849`) through the Hugging Face datasets-server API.
- 60 receipts, **248 questions**: price of first menu item (59), total (58), change (38), tax (33), unanswerable (60: website, cashier name, email, loyalty number, reservation name, VAT number; 10 each).
- Gold, accepted separator variants and evidence boxes are produced exactly as in `../receipts_v1/README.md` (same caveats). Image sizes 418×740 to 1356×2315 (long side capped at 2400).
- Images are gitignored. Regenerate with `SSL_CERT_FILE=$(python -m certifi) python3 -m eval.data.receipts_v2.fetch` and compare with `images.sha256` (Pillow version dependent; `run_eval` records the digest it saw).
- **Use:** held-out only. Do not tune anything on it; the first run on it is the release measurement of the app as shipped (message 218).
