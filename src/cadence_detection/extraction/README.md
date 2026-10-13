# Person 2 extraction package

Implemented local extraction adapters, OCR backends, block/result models and CLI.

Public API: `extract_document(path, options=ExtractionOptions(...), ocr=backend)`.

See `docs/person2_extraction.md` for setup, commands, interface conventions and limits. Extraction results contain raw PII; this package never declares them safe for downstream LLM use.
