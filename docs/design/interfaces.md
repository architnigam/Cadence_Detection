# Comprehensive Component Contracts and Interface Specification

**Version:** 1.0.0-final
**Lead Owner:** Person 1 (Architecture, Ingestion, and Integration Lead)
**Stakeholders / Consumers:** Person 2 (Extraction & OCR), Person 3 (PII Detection & Classification), Person 4 (Redaction, Privacy Gate, & Demo UI), Person 5 (Evaluation, QA, & Submission)

---

## 1. Overview & Trust Boundaries

Cadence Financial Group requires a zero-leakage local document privacy pipeline:
```
Upload -> Validate -> Document Manifest -> Extract/OCR -> Normalize Blocks -> Detect/Classify PII -> Resolve Spans -> Redact -> Rescan -> Approve/Quarantine Gate -> Sanitized Output / Audit Report
```

### Trust Boundary Rule
- **Untrusted External:** User uploads, external network, downstream third-party Large Language Models (LLMs).
- **Trusted Local Processing Boundary:** Local sandbox execution environment (`src/cadence_detection/`). All raw text, raw OCR outputs, bounding boxes, entity values, and temporary file artifacts exist **only** within this boundary.
- **Strict Prohibition:** Raw, unredacted, or quarantined text must **never** be passed across the downstream LLM boundary. Logs must never contain raw PII strings.

---

## 2. Global Statuses and Enums

### 2.1 Processing Status (`ProcessingStatus`)
Explicitly tracks the lifecycle of a document through ingestion and orchestration:
- `accepted`: Document validated, hashes verified, manifest created. Ready for extraction.
- `processing`: Document currently moving through pipeline stages.
- `completed`: Successfully passed extraction, detection, redaction, and passed the rescan verification gate.
- `quarantined`: Processing stopped or release blocked due to validation failure, corrupt/password-protected file, low OCR confidence, unsupported media, incomplete extraction, or residual PII detection on rescan.
- `failed`: System-level fatal execution crash or unrecoverable adapter error.

### 2.2 Safe Release Decision (`ReleaseDecision`)
Strict, unambiguous decision for downstream transmission:
- `safe_for_llm`: All extraction complete, all PII redacted, rescan confirmed 0 residual PII spans, no quarantine flags. Sanitized text is authorized for downstream LLM ingestion.
- `not_safe_for_llm`: Document is quarantined, failed, unredacted, partially extracted, or contains unresolved/residual PII. Transmission to any LLM is strictly prohibited.

### 2.3 Quarantine Reasons (`QuarantineReason`)
Documented reasons for routing a document to quarantine:
- `UNSUPPORTED_FORMAT`: File extension or MIME type not in allowed list (`.pdf`, `.pptx`, `.docx`).
- `MIME_EXTENSION_MISMATCH`: File extension does not match true magic bytes / MIME type.
- `FILE_OVERSIZED`: File exceeds maximum allowed size limits.
- `CORRUPT_FILE`: Malformed header, truncated zip container, or unreadable stream.
- `PASSWORD_PROTECTED`: File is encrypted or password-protected.
- `EXTRACTION_FAILED`: Extraction adapter crashed or returned an incomplete payload.
- `EXTRACTION_INCOMPLETE`: Extracted coverage failed structure or completeness checks.
- `UNSUPPORTED_EMBEDDED_MEDIA`: Document contains embedded objects/images that cannot be parsed/converted (e.g. unknown OLE objects, unconvertible EMF/WMF vectors).
- `LOW_OCR_CONFIDENCE`: Mean OCR confidence or critical block OCR confidence fell below required threshold.
- `DETECTION_FAILED`: PII detector threw an error or failed execution.
- `REDACTION_FAILED`: Redaction engine failed to replace detected spans cleanly.
- `RESCAN_FAILED`: Secondary verification rescan detected remaining PII in redacted text.
- `MISSING_STEP`: A pipeline stage was skipped or missing.

### 2.4 Supported Formats (`SupportedFormat`)
- `pdf`: Portable Document Format (`application/pdf`)
- `pptx`: Microsoft PowerPoint Presentation (`application/vnd.openxmlformats-officedocument.presentationml.presentation`)
- `docx`: Microsoft Word Document (`application/vnd.openxmlformats-officedocument.wordprocessingml.document`)

### 2.5 Source Kind (`SourceKind`)
- `paragraph`: Standard body paragraph.
- `heading`: Structural section heading.
- `table_cell`: Cell inside a structured table.
- `slide_shape`: Text shape, callout, or text frame in a slide.
- `slide_notes`: Speaker notes on a presentation slide.
- `header_footer`: Document header or footer.
- `text_box`: Floating text frame or callout box.
- `ocr_image_region`: Text extracted via OCR from a scanned page, screenshot, or embedded raster image.

---

## 3. Schema Definitions

### 3.1 Document ID & Source File Identity Rules
To guarantee idempotency and auditability:
- **`document_id`**: Deterministic SHA-256 hash computed directly over the document's binary contents (`sha256(raw_bytes)`). If two uploads have identical contents, they share the identical `document_id`.
- **`source_identity`**: Captures original filename, sanitized display filename (stripping dangerous paths), byte size, content MIME type, and upload timestamp.

```json
{
  "document_id": "3f4b5db17d2e2694630fe4244754a270d4c0dde68ef009ee0495e43a2bf606f3",
  "filename": "Cadence_Group_Risk_Management_Policy__v6.0.pdf",
  "detected_format": "pdf",
  "sha256": "3f4b5db17d2e2694630fe4244754a270d4c0dde68ef009ee0495e43a2bf606f3",
  "file_size_bytes": 14094994,
  "mime_type": "application/pdf",
  "processing_status": "accepted",
  "created_at": "2026-10-13T14:40:00Z"
}
```

### 3.2 Normalized Block Schema (`NormalizedBlock`)
Preserves paragraph, table, slide, page, reading order, OCR confidence, and spatial location:

```json
{
  "document_id": "3f4b5db17d2e2694630fe4244754a270d4c0dde68ef009ee0495e43a2bf606f3",
  "block_id": "doc3f4b-p009-b0002",
  "page_or_slide": 9,
  "source_kind": "ocr_image_region",
  "reading_order": 2,
  "text": "Employee Name: John Doe\nRole: Lead Risk Analyst\nEmail: jdoe@cadence.com",
  "table_row": null,
  "table_column": null,
  "bbox": {
    "x0": 72.0,
    "y0": 144.0,
    "x1": 480.0,
    "y1": 210.0,
    "coord_system": "pdf_points",
    "page_width": 612.0,
    "page_height": 792.0
  },
  "ocr_confidence": 0.942,
  "extraction_complete": true,
  "metadata": {
    "section_title": "Section 4.1 Governance"
  }
}
```

### 3.3 Source Location Schema (`SourceLocation`)
Points to the exact structural location within the source document:
```json
{
  "document_id": "3f4b5db17d2e2694630fe4244754a270d4c0dde68ef009ee0495e43a2bf606f3",
  "page_or_slide": 9,
  "block_id": "doc3f4b-p009-b0002",
  "source_kind": "ocr_image_region",
  "reading_order": 2,
  "table_row": null,
  "table_column": null
}
```

### 3.4 PII Finding / Entity Interface (`PIIFinding`)
Offsets are strictly **Python Unicode code-point offsets**; `start` is inclusive, `end` is exclusive into the exact `NormalizedBlock.text`.

> **CRITICAL PRIVACY RULE:** Raw entity text values are never serialized into standard log output or external reports. Reports store only `entity_type`, `block_id`, `start`, `end`, `confidence`, and `detector`.

```json
{
  "finding_id": "find-001",
  "document_id": "3f4b5db17d2e2694630fe4244754a270d4c0dde68ef009ee0495e43a2bf606f3",
  "block_id": "doc3f4b-p009-b0002",
  "entity_type": "PERSON",
  "start": 15,
  "end": 23,
  "confidence": 0.98,
  "detector": "transformer_ner_v1",
  "source_location": {
    "page_or_slide": 9,
    "block_id": "doc3f4b-p009-b0002",
    "source_kind": "ocr_image_region"
  },
  "validation_status": "valid"
}
```

### 3.5 Redaction Result Interface (`RedactionResult`)
- Overlap resolution: Sort spans by start asc, length desc; eliminate overlaps deterministically.
- Replacement order: Right-to-left (descending start offset) so character offsets remain valid during transformation.
- Replacement tokens: Document-local stable tokens: `<PERSON_1>`, `<EMAIL_1>`, `<PHONE_1>` or `<REDACTED:PERSON>`. Preserves role and relational structure across blocks without revealing PII.

```json
{
  "document_id": "3f4b5db17d2e2694630fe4244754a270d4c0dde68ef009ee0495e43a2bf606f3",
  "sanitized_blocks": [
    {
      "block_id": "doc3f4b-p009-b0002",
      "text": "Employee Name: <PERSON_1>\nRole: Lead Risk Analyst\nEmail: <EMAIL_1>"
    }
  ],
  "total_redactions": 2,
  "category_counts": {
    "PERSON": 1,
    "EMAIL": 1
  },
  "redaction_map_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "warnings": []
}
```

### 3.6 Rescan Verification Result (`RescanResult`)
Person 4/Person 3 executes a secondary PII detector pass against `sanitized_blocks`.
- If `residual_candidates > 0`, the document is automatically **quarantined** with reason `RESCAN_FAILED`.

```json
{
  "document_id": "3f4b5db17d2e2694630fe4244754a270d4c0dde68ef009ee0495e43a2bf606f3",
  "rescan_passed": true,
  "residual_candidates_count": 0,
  "residual_findings": [],
  "rescan_notes": "Zero residual PII entities detected upon secondary scan."
}
```

### 3.7 Pipeline Response Schema (`PipelineResponse`)
Final result returned by Person 1's orchestrator to the client/caller:

```json
{
  "document_id": "3f4b5db17d2e2694630fe4244754a270d4c0dde68ef009ee0495e43a2bf606f3",
  "filename": "Cadence_Group_Risk_Management_Policy__v6.0.pdf",
  "status": "completed",
  "release_decision": "safe_for_llm",
  "quarantine_reasons": [],
  "sanitized_text": "Employee Name: <PERSON_1>...",
  "sanitized_blocks": [...],
  "manifest": { ... },
  "summary": {
    "total_blocks": 142,
    "total_entities_redacted": 87,
    "category_counts": {
      "PERSON": 34,
      "EMAIL": 21,
      "PHONE": 12,
      "EMPLOYEE_ID": 20
    },
    "mean_ocr_confidence": 0.965,
    "processing_time_ms": 1420
  },
  "audit_report": {
    "pipeline_version": "1.0.0",
    "rescan_verified": true,
    "warnings": []
  },
  "errors": []
}
```

---

## 4. Integration Points for Persons 2-5

| Person | Interface / Protocol | Input | Expected Output | Failure Behavior |
|---|---|---|---|---|
| **Person 2** | `ExtractionAdapter.extract(manifest, config)` | Validated `DocumentManifest` | `ExtractionResult` containing `List[NormalizedBlock]`, `extraction_complete: bool`, `mean_ocr_confidence: float`, `warnings: List[str]` | Return `extraction_complete=False` or raise `ExtractionError`; pipeline quarantines document. |
| **Person 3** | `PIIDetectorAdapter.detect(blocks, config)` | `List[NormalizedBlock]` | `DetectionResult` containing `List[PIIFinding]`, `detector_metadata: dict` | Return error; pipeline quarantines document. |
| **Person 4** | `RedactionAdapter.redact(blocks, findings, config)` and `RescanAdapter.rescan(sanitized_blocks, config)` | `List[NormalizedBlock]`, `List[PIIFinding]` | `RedactionResult` and `RescanResult` | Any failure or residual PII triggers `QuarantineReason.RESCAN_FAILED` and `ReleaseDecision.not_safe_for_llm`. |
| **Person 5** | `EvaluationPipeline.evaluate(response, ground_truth)` | `PipelineResponse`, Gold set annotations | Precision, Recall, F1, Structure Rubric scores (headings, reading order, tables, paragraphs, context) | Reports metrics; never alters production quarantine decisions. |

---

## 5. Decision Log
1. **Pydantic vs Dataclasses:** To maintain zero third-party dependency lock-in for ingestion, core contracts are defined with standard library `dataclasses` and `typing`, providing full JSON serialization helpers compatible with Pydantic v1/v2.
2. **Stable Document IDs:** Uses content SHA-256 rather than file upload name or random UUIDs. This prevents duplicate processing and ensures test reproducibility.
3. **Rescan Gate:** Mandated as a hard barrier. Under no circumstance can `safe_for_llm` be emitted if rescan is skipped or fails.

## Implemented Person 2 boundary

The extraction API is implemented in `cadence_detection.extraction`. Its JSON uses `issues` (code/message/location/severity), `ocr_confidence` (lowercase), `units`, `coverage`, `blocks` and `extraction_complete`. See `docs/person2_extraction.md` and the dataclasses in `models.py` for the precise current schema.

Extraction statuses are `extracted`, `quarantined` and `failed`. `extracted` is **not** a downstream release approval. Person 4 provides a separate redaction/gate package; extraction alone does not execute or approve that gate. DOCX block `page_or_slide` is null because no rendered pagination is claimed; source XML paths provide the location. Template/metadata blocks may also have no page/slide index.

OCR blocks retain line hierarchy and, when supplied by the backend, word offsets/boxes/confidence. Optional detailed PDF crops are supplementary, marked in attributes, and can overlap full-page text. Consumers must handle these overlaps using location as well as text; repeated PII in separate source locations must remain separate occurrences. Native-table cell boxes are labeled by their actual scope rather than claiming exact visual cell bounds.

## Adapter mapping between the implemented contracts

The schemas in sections 2-4 describe the ingestion/orchestration boundary. The standalone Person 2 API above has a distinct extraction result type; the two must not be passed interchangeably without an adapter.

- **IDs:** ingestion uses the full SHA-256 as `document_id`; standalone extraction uses its first 16 hex characters and retains the full `sha256`. An integration adapter must consistently remap document/block/finding references using the manifest identity.
- **OCR confidence:** standalone extraction reports 0-100; orchestration configuration/examples use 0-1. Divide extraction confidence by 100 before applying orchestration thresholds; preserve null for native text.
- **Boxes:** extraction uses `[left, top, right, bottom]` plus `coordinate_space`; ingestion uses `BoundingBox`. Map all four coordinates and retain the actual units/origin/rotation, rather than assuming every box is PDF points.
- **Kinds and metadata:** map extraction kind strings to the orchestration enum where supported. Preserve original kinds, `source_location`, OCR hierarchy/word geometry and `attributes` in metadata; do not silently discard kinds absent from the enum.
- **Pagination:** extraction's DOCX/template/metadata page indices can be null. Consumers must preserve structural source paths rather than invent page numbers despite the current orchestration integer annotations.
- **Completeness:** map extraction `issues`, `units`, `coverage` and block flags into orchestration warnings/completeness and unsupported-media indicators. Never turn an extraction quarantine into a completed or releasable result.
- **Release:** `extracted` is only an extraction-stage status. Only the full orchestration/redaction/rescan checks may produce `safe_for_llm`; placeholder stages remain blocked by the orchestrator.

These are required adapter mappings, not a claim that the current default orchestrator is wired to the standalone extraction engine.

## Integration acceptance checklist for the `test` branch

Before calling the pipeline end-to-end, the integration owner must verify:

- `extract_document` output is converted into `NormalizedBlock` objects without dropping source locations, media issues, OCR boxes or completeness flags.
- OCR confidence is converted from the extraction package's 0-100 scale to the orchestrator's 0-1 scale before threshold checks.
- Detection findings are converted from the standalone detector/redaction models into `PIIFinding` objects with stable source locations and no raw values in logs.
- Redaction output is converted back into the orchestration `RedactedBlock`/`RedactionResult` schema, preserving block order and document identity.
- `SafeReleaseGate` residual findings and quality warnings are represented as a failed rescan or quarantine decision; they cannot be treated as informational warnings.
- The Streamlit UI is not described as a PDF/PPTX/DOCX live walkthrough until it calls the same integrated path rather than fixture helpers or `.txt` upload handling.
- A full run on approved local fixtures produces an evidence report with input format, extraction status, detected categories, redaction count, residual count and quarantine reasons, without raw PII.
