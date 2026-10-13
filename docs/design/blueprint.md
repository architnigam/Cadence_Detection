# Cadence Detection Pipeline - Functional Blueprint

**Version:** 1.0.0-final
**Lead Owner:** Person 1 (Architecture, Ingestion, and Integration Lead)
**Target Systems:** Cadence Group Document Privacy Gateway

---

## 1. Executive Summary and Scope

The Cadence Detection pipeline enforces a zero-leakage local redaction boundary around sensitive organizational assets, policy documents, and third-party risk management artifacts across PDF, PPTX, and DOCX formats.

Unredacted files or raw PII must never reach external Large Language Models (LLMs) or public cloud APIs. This document defines the functional lifecycle of every document processed by the pipeline, detailing the stages, security boundaries, and gate policies from initial upload to sanitized release or quarantine.

## Implementation status on the `test` branch

The repository now contains implemented components for local PDF/DOCX/PPTX extraction and OCR (`src/cadence_detection/extraction/`), a deterministic baseline detector (`src/cadence_detection/detection/pii_detector.py`), text redaction and a residual-leakage gate (`src/cadence_detection/redaction/`), an independent evaluator (`src/cadence_detection/evaluation/`), and a Streamlit demonstration interface (`app/app.py`).

The Person 1 orchestrator remains the fail-closed integration boundary. It exposes adapter contracts for those components and blocks `safe_for_llm` when any placeholder adapter is still active. The standalone extraction result and the orchestration contracts are not interchangeable: an integration adapter must map document IDs, block kinds, source locations, OCR confidence units, completeness issues and pagination before the results enter the release gate. The exact mapping is recorded in [interfaces.md](interfaces.md).

The current UI demonstrates redaction and gate behavior using local fixtures and optional `.txt` upload. It is not yet a production upload path for PDF, PPTX and DOCX. Therefore, the flow below is the target end-to-end blueprint, while the implementation status and test evidence must be presented separately from measured final case-study outcomes.

---

## 2. End-to-End Functional Flowchart

```mermaid
flowchart TD
    subgraph Client Boundary [Untrusted Client Zone]
        U[Client Document Upload\nPDF, PPTX, DOCX]
    end

    subgraph Ingestion & Validation [Person 1: Ingestion & Boundary Enforcement]
        V{File Validator}
        V -- Invalid MIME / Over Max Size / Corrupt --> Q[Quarantine Store\nQuarantineReason Recorded]
        V -- Password Encrypted --> Q
        V -- Valid & Readable --> M[Generate Stable Document ID\nSHA-256 Content Hash]
        M --> DMF[Build Document Manifest\nStore in Local Manifest Registry]
        DMF --> D[Document Dispatcher]
    end

    subgraph Extraction & OCR [Person 2: Extraction Adapters]
        D -- format=pdf --> EX_PDF[PDF Adapter\nNative Text + Tesseract OCR Fallback]
        D -- format=pptx --> EX_PPT[PPTX Adapter\nSlides, Shapes, Notes, Tables]
        D -- format=docx --> EX_DOC[DOCX Adapter\nParagraphs, Tables, Headers/Footers]
        EX_PDF --> NORM[Normalize Ordered Blocks\nPage/Slide, BBox, Reading Order, OCR Conf]
        EX_PPT --> NORM
        EX_DOC --> NORM
        NORM --> EX_CHK{Extraction\nComplete & Valid?}
        EX_CHK -- Low Conf / Truncated / Unsupported Media --> Q
    end

    subgraph Detection & Classification [Person 3: PII Recognition]
        EX_CHK -- Pass --> DET[PII Detection Engine\nLocal Transformer NER + Regex Catalog]
        DET --> OVR[Deterministic Overlap Resolver\nPriority by Confidence & Specificity]
        OVR --> FND[PII Findings Set\nUnicode Offsets, Types, No Raw PII in Logs]
    end

    subgraph Redaction & Verification [Person 4: Privacy Gate & Redaction]
        FND --> RED[Document Redactor\nRight-to-Left Stable Token Replacement\ne.g., <PERSON_1>, <EMAIL_1>]
        RED --> BLK_SAN[Sanitized Blocks]
        BLK_SAN --> RSC[Post-Redaction Rescan Gate\nSecondary Detector Pass]
        RSC --> GAT{Residual PII\nCount == 0?}
        GAT -- Residual PII Found --> Q
        GAT -- Clean Verification --> APR[Mark Status: Completed\nRelease: safe_for_llm]
    end

    subgraph Safe Delivery & Downstream [Authorized Egress]
        APR --> SAN_OUT[Sanitized Text Deliverable\nAudit Report & Metrics]
        SAN_OUT --> EXT_LLM[Downstream LLM Boundary\nZero Raw PII Exposure]
        Q --> AUD_REP[Quarantine Audit Report\nZero PII Emitted]
    end

    style Client Boundary fill:#f9f9f9,stroke:#666,stroke-width:1px
    style Ingestion & Validation fill:#e1f5fe,stroke:#0288d1,stroke-width:2px
    style Extraction & OCR fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    style Detection & Classification fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    style Redaction & Verification fill:#e8f5e9,stroke:#388e3c,stroke-width:2px
    style Safe Delivery & Downstream fill:#efebe9,stroke:#5d4037,stroke-width:2px
```

---

## 3. Detailed Stage Blueprints

### Stage 1: Local Upload & Trust Boundary
- **Objective:** Establish the demarcation line between untrusted file origins and trusted internal processing memory.
- **Rule:** No raw bytes leave the execution machine. All parsing and extraction work is done within isolated temporary directories. Files are uploaded via local file path or stream.

### Stage 2: File Validation and Resource Limits
- **Validation Engine:** Inspects file extension, file size, readability, and initial magic numbers (MIME verification).
- **Constraints Enforced:**
  - Maximum file size: PDF (50 MB), PPTX (30 MB), DOCX (30 MB), matching `config/pipeline.json`.
  - Allowed extensions: `.pdf`, `.pptx`, `.docx`.
  - Magic byte verification: Validates PKZip headers for PPTX/DOCX (`PK\x03\x04`), `%PDF-` header for PDF.
  - Password and corruption checks: Any encrypted or password-protected container is immediately intercepted and quarantined.
  - Fail-safe response: Any validation failure halts pipeline progression and writes an explicit quarantine entry.

### Stage 3: Document Identity & Manifest Generation
- **Stable Document ID:** Computed using cryptographic SHA-256 hash across the raw byte payload (`hashlib.sha256(file_bytes).hexdigest()`).
  - Guarantees idempotency and identical IDs regardless of file renames.
  - Enables exact reproducibility across testing runs and prevents duplicate execution overhead.
- **Document Manifest:** Structured immutable record capturing `document_id`, sanitized filename, MIME type, byte size, format, created timestamp, and initial status (`accepted`).

### Stage 4: Document Dispatch & Extraction Handoff
- **Dispatcher:** Reads `detected_format` and invokes the registered `ExtractionAdapter`:
  - `PDFAdapter`: Native PDF text parser with OCR fallback for scanned images (Tesseract/paddleOCR). Handles the 35 scanned pages of the Risk Policy.
  - `PPTXAdapter`: Traverses slide trees, shapes, tables, notes, and embedded vector/raster media (handles the 9-slide Organizational Pack).
  - `DOCXAdapter`: Traverses body paragraphs, structured tables, headers/footers, and embedded media relations (handles the 16 tables and 41 media items in TPRM Training).
- **Output:** Standardized `List[NormalizedBlock]`.

### Stage 5: Normalization
- **Structure Preservation:** Every extracted unit is converted to a `NormalizedBlock`:
  - `block_id`: Hierarchical, traceable ID (e.g. `doc{hash[:6]}-p{page}-b{idx}`).
  - `page_or_slide`: 1-based page or slide number.
  - `source_kind`: Categorized as `paragraph`, `heading`, `table_cell`, `slide_shape`, `slide_notes`, `header_footer`, `text_box`, or `ocr_image_region`.
  - `reading_order`: Sequential natural reading order index.
  - `bbox`: Spatial coordinates with coordinate system definition.
  - `ocr_confidence`: Confidence score (0.0 - 1.0) when produced by OCR.
  - `extraction_complete`: Boolean flag certifying complete extraction.

### Stage 6: PII Detection & Classification Handoff
- **Engine:** Person 3's hybrid recognizer combines transformer NER, regex catalogs, and contextual rules for Cadence-specific identifiers (`EMPLOYEE_ID`, `DIRECTOR_ID`, `VENDOR_PERSON_ID`, `NATIONAL_ID`, synthetic phone formats like `+1 (555) 0114`, emails, names).
- **Output:** `List[PIIFinding]` specifying exact Unicode start and end code-point offsets within each block.

### Stage 7: Overlap Resolution
- When multiple recognizers trigger on overlapping spans (e.g. `PERSON` overlapping with `EMAIL` or `EMPLOYEE_ID`), overlaps are resolved deterministically:
  1. Longer span wins (maximal coverage).
  2. Higher confidence wins if lengths are identical.
  3. Strict entity priority order breaks remaining ties.

### Stage 8: Redaction Handoff
- **Safe Replacement Engine:**
  - Sorts resolved findings in **descending order of start offset** (right-to-left) per block.
  - Replaces raw spans with document-local consistent placeholders: `<PERSON_1>`, `<EMAIL_1>`, `<PHONE_1>`.
  - Guarantees offset stability during sequential replacements without corrupting preceding indices.
  - Preserves grammatical context, tables, and sentence structures.

### Stage 9: Post-Redaction Rescan Gate
- **Dual-Verification Rule:** Redacted text is passed through a secondary PII detector scan.
- **Gate Criteria:**
  - If residual PII candidates == 0: Rescan passes.
  - If residual PII candidates > 0: Document is immediately flagged with `QuarantineReason.RESCAN_FAILED` and marked `ReleaseDecision.not_safe_for_llm`.

### Stage 10: Approval & Quarantine Gate
- **Safe Release Conditions (ALL must be true):**
  1. File validation succeeded.
  2. Extraction marked `extraction_complete == True`.
  3. Mean OCR confidence >= configured threshold (default 0.70).
  4. No unsupported embedded media flags raised.
  5. Detection completed without error.
  6. Redaction completed with 0 errors.
  7. Rescan completed with 0 residual findings.
  8. Zero quarantine reasons recorded.
- **Decision:** Sets `status = completed`, `release_decision = safe_for_llm`.
- **Any Exception or Failure:** Sets `status = quarantined`, `release_decision = not_safe_for_llm`.

### Stage 11: Sanitized Output & Audit Report Generation
- **Deliverables:**
  1. Sanitized structured blocks / concatenated sanitized document text.
  2. Privacy Audit Report: Summary metrics, category counts, block count, execution timing, SHA-256 checksums, gate verification status.
  3. **Zero PII Guarantee:** Audit reports and system logs record counts, entity types, and locations, but **never** emit the raw underlying PII strings.

### Stage 12: Downstream LLM Boundary
- Only deliverables with `release_decision == "safe_for_llm"` may be routed to external LLMs.
- Any attempt to push a quarantined or failed document payload triggers an immediate egress exception.

---

## 4. Scaling Considerations (Batch & Concurrent Processing)
- **Local Multi-Processing:** Ingestion uses deterministic, stateless document IDs, enabling concurrent extraction workers across CPU cores using a process pool.
- **Resource Throttling:** OCR workers are bounded to avoid memory exhaustion on large documents (e.g. 35 scanned pages of the Risk Policy).
- **Isolation:** Each document runs in an isolated ephemeral workspace with automatic temporary file cleanup.
