# Person 5 evaluation bundle contract, version 1

This is an evaluator input contract consuming the proposed component schema in `docs/design/interfaces.md`. Person 1 owns pipeline schema changes. Evaluation runs on local JSON bundles and emits aggregate JSON/Markdown without source text or finding values.

Required top-level keys: `schema_version: 1`, `dataset_kind` (`synthetic`, `source_sample`, `full_source`), `documents`, `blocks`, `gold`, `predictions`. Optional lists: `results`, `structure_reviews`. A complete working example lives in `data/synthetic/evaluation_fixture.json`.

## Documents and source coverage

`document_id` must be a safe opaque ID (letters, digits, underscore, hyphen, dot or colon), never a person name/email. Include `format` (`pdf`, `pptx`, `docx`), `split` (`development`, `held_out`) and boolean `extraction_complete`. `expected_units` lists unique source units, and `unit_status` maps processed units to `complete`, `incomplete` or `failed`. Missing units are incomplete. If expected units exist, claiming complete extraction while a unit is missing fails input validation. An empty unit inventory reports unknown coverage.

## Blocks and negative review

Each block needs unique `(document_id, block_id)`, exact `text`, `source_kind`, `image_only`, `extraction_complete`, `annotation_status`, and optional `page_or_slide` (1-based or null for unpaginated DOCX). Source kinds: body, table, narrative, image, header, footer, notes, text_box. Empty text can describe an image-region-only block.

`annotation_status` is `pending`, `reviewed` or `adjudicated`. Review zero-PII blocks explicitly. Only adjudicated blocks participate by default. `--include-provisional` also includes reviewed blocks and clearly marks the report exploratory. Pending blocks remain excluded. Predictions on excluded blocks are counted as excluded, not silently counted as false positives. All input offsets are validated even in excluded splits.

## Gold and predictions

Text findings use `document_id`, `block_id`, `entity_type`, `start`, `end`. Offsets count Python Unicode code points, start inclusive/end exclusive into the exact frozen normalized block string. No UTF-8 byte offsets or JavaScript UTF-16 offsets. Gold additionally needs `adjudication_status`; preserve reviewer IDs, notes and original source locations locally. Default scoring requires adjudicated gold in adjudicated blocks. Duplicate gold fails validation. Duplicate predictions count as FP.

Photograph/signature regions use `bbox: [x0,y0,x1,y1]` normalized to the full original page/slide/image and null/absent offsets. Never mix OCR pixel coordinates with these normalized coordinates. Visual regions use maximum one-to-one IoU >= 0.5 matching and stay separate from text recall. This does not implement image redaction.

Exact `(document, block, type, start, end)` matching is primary. A wrong category produces one FN and one FP. Partial boundaries also produce FN/FP in the primary metric. A separate maximum bipartite overlap match at IoU >= 0.5 helps diagnose those boundaries. One prediction cannot match multiple gold occurrences.

Precision = TP/(TP+FP). Recall = TP/(TP+FN). F1 = 2TP/(2TP+FP+FN). Undefined denominators report null/N/A. No predictions with nonempty gold gives zero recall/F1 and undefined precision. Zero gold does not imply 100% recall.

## Redaction and claimed release states

Each result has `document_id`, `status` (`approved`, `quarantined`, `failed`), `sanitized_blocks` with original block IDs and string text, `verification_passed` and nonnegative integer `remaining_candidate_count`. Approved results must cover every extracted block, retain nonempty output for nonempty source blocks, have complete extraction, passed verification and zero remaining candidates. Original text and sanitized text have different offsets. Do not reuse original offsets against placeholders.

The evaluator independently scans all sanitized blocks within a document for case-insensitive, whitespace-normalized known gold values. It reports checked distinct values, checked original occurrences and residual occurrences separately. Repeated identities do not multiply one surviving value into several residual leaks. Very short partial identifiers can also match benign context, so manually review their residual findings. Routine reports never include matched values. Cross-block splits, spelling/OCR variants, previously unlabeled PII and original-file metadata/images require additional review. A zero count cannot approve release by itself.

## Structure/context evidence

Every review explicitly specifies all five dimensions: headings, reading_order, block_boundaries, table_relationships, neighboring_context. Each applicable dimension contains unique check IDs, boolean passed values and source evidence locations. A non-applicable dimension needs a reason. At least one dimension must apply. Score each dimension as passed/total, then average the applicable dimension scores. The target is >= 0.8 per document. Missing reviews report unknown, not pass.

Optional independently aligned `text_accuracy` contains `correct_characters`, `reference_characters`. It stays separate from structure. Character alignment and OCR quality adjudication belong to the reviewers; this evaluator does not fabricate an alignment or silently treat structural retention as OCR accuracy.
