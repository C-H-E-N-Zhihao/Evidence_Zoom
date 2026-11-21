# Local OCR route for the accident form

On macOS with Swift and Vision, build the helper and point the Python process to it:

    swiftc pipeline/ocr/recognize.swift -o /tmp/evidence-ocr
    export EVIDENCE_OCR_BIN=/tmp/evidence-ocr

Call `pipeline.ocr.answer(pil_image, question)` for the app or `answer(image, item.question)` for evaluation. The returned eval.schema.PipelineResult includes the recognized value, its normalized box and local OCR latency. When the last route step is fallback, pass the image and question to the visual pipeline and retain the OCR trace and usage. The helper processes upright PNG pixels locally. A non-macOS host needs an alternative OCR backend.

The initial route accepts single-field questions about driver, insurer, registration or policy number for a named vehicle on a two-column form. It resolves rows and columns from OCR headers and labels. Unsupported phrasing, visual questions, missing fields and ambiguous matches go to overview. This version recognizes each eligible image per call. Measurements with this version should charge that cost each time.

On the 84 synthetic questions from commit 4d1183d, this route returned 24 exact answers and handed 60 questions to overview. All 24 direct answers matched. These fixtures share a form layout and question templates. This check measures the OCR exit only.
