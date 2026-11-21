# handwriting_v1: free-form handwriting pages from real IAM lines

10 pages. Each stacks 7 consecutive rows of the IAM-line **test** split (`Teklia/IAM-line`, Hugging Face datasets-server); the rows are real handwritten lines.
Consecutive rows are sometimes by different writers, and the text is not always continuous across lines. That doesn't matter here: every question is answered by reading the handwriting.
There are 60 questions, 6 per page:
- 3 × "What word comes right after 'W'?" (W unique on the page)
- the last word
- the number of lines (7)
- "Who signed this note?" (unanswerable)

Gold answers are the IAM transcriptions. Evidence boxes are the pasted line strips.
Regenerate: `SSL_CERT_FILE=$(python -m certifi) python3 -m eval.data.handwriting_v1.fetch` (seed `HW_SEED=2211`). Images are not committed (11 MB); `images.sha256` was made with Pillow 11.0.0.
Built by claude-andrew-b (Andrew's idea). The questions are templated from the transcription, not written blind.
