# realdocs_v1: real documents and charts from public benchmarks (general route test, message 163)

- 100 questions from **DocVQA validation**: real scanned business documents.
- 100 questions from **ChartQA test**: real charts from the web.
- Sampled by seed (`RD_SEED=1163`) through the Hugging Face datasets-server API: `lmms-lab-encoder/DocVQA` (config DocVQA) and `lmms-lab-encoder/ChartQA`.
- 193 unique images. Pages larger than 2400 px were downscaled with LANCZOS. Both arms see the same file.
- `question_id` = `rd-<source>-<row offset>`, and `source` keeps the dataset, config, split and offset, so every item maps back to its benchmark row.
- `answer` = first gold answer; `accepted_answers` = the other gold answers.
- No gold boxes, so only answer scores are reported: our substring scorer and ANLS (eval.metrics.anls, 1cbbb21).
- `evidence_type` is by source, not per question: DocVQA = "text", ChartQA = "visual". Some charts print their values, and some DocVQA answers need layout.

Images are not committed (132 MB). Regenerate with `SSL_CERT_FILE=$(python -m certifi) python3 -m eval.data.realdocs_v1.fetch` (about 15 min, rate-limited).
Question ids are stable across machines. Image bytes can differ under another Pillow version (resize); compare with `images.sha256` (Pillow 11.0.0).
