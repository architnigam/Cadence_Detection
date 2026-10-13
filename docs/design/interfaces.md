# Draft component contract

Agree before implementation. All statuses below are proposals.

- Document: document_id, filename, detected_format, sha256, processing_status, errors.
- Block: document_id, block_id, page_or_slide (1-based), source_kind, reading_order, text, table_row/table_column (optional), bbox (optional), OCR_confidence (optional), extraction_complete.
- Bounding boxes: specify coordinate system and units per adapter; retain conversion to original image/slide/page. Never mix normalized and pixel coordinates silently.
- Finding: document_id, block_id, entity_type, start, end, confidence, detector, source_location. Python Unicode code-point offsets; start inclusive/end exclusive into the exact normalized block text. Raw values stay in memory/local restricted evidence only.
- Redaction: resolve overlaps, replace from right to left, generate stable document-local typed tokens and preserve block structure. Mapping storage requires explicit local controls.
- Result: approved, quarantined or failed; sanitized_blocks, category_counts, extraction_coverage, remaining_candidate_count, warnings. Approval requires completed extraction and a passed verification gate; gate criteria to be agreed.
- Implement adapters independently of UI. Person 1 owns contract changes with all consumers reviewing; fixtures should cover errors and success.

## Implemented Person 2 boundary

The extraction API is implemented in `cadence_detection.extraction`. Its JSON uses `issues` (code/message/location/severity), `ocr_confidence` (lowercase), `units`, `coverage`, `blocks` and `extraction_complete`. See `docs/person2_extraction.md` and the dataclasses in `models.py` for the precise current schema.

Extraction statuses are `extracted`, `quarantined` and `failed`. `extracted` is **not** the final `approved` status proposed above. Person 4's downstream release gate remains unimplemented. DOCX block `page_or_slide` is null because no rendered pagination is claimed; source XML paths provide the location. Template/metadata blocks may also have no page/slide index.

OCR blocks retain line hierarchy and, when supplied by the backend, word offsets/boxes/confidence. Optional detailed PDF crops are supplementary, marked in attributes, and can overlap full-page text. Consumers must handle these overlaps using location as well as text; repeated PII in separate source locations must remain separate occurrences. Native-table cell boxes are labeled by their actual scope rather than claiming exact visual cell bounds.
