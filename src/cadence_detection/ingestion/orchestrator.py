"""
Cadence Detection Pipeline - Pipeline Orchestration and Gatekeeper
Owned by Person 1 (Architecture, Ingestion, and Integration Lead).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol, runtime_checkable

from cadence_detection.ingestion.contracts import (
    DetectionResult,
    DocumentManifest,
    ExtractionResult,
    NormalizedBlock,
    PIIFinding,
    PipelineResponse,
    ProcessingStatus,
    QuarantineReason,
    RedactedBlock,
    RedactionResult,
    ReleaseDecision,
    RescanResult,
    SourceKind,
    SupportedFormat,
)
from cadence_detection.ingestion.validator import FileValidator, ValidationResult

# Zero-PII safe logger configuration
logger = logging.getLogger("cadence.ingestion")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [cadence.pipeline] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.setLevel(logging.INFO)


@runtime_checkable
class ExtractionAdapter(Protocol):
    def extract(self, manifest: DocumentManifest, config: Dict[str, Any]) -> ExtractionResult:
        ...


@runtime_checkable
class PIIDetectorAdapter(Protocol):
    def detect(self, blocks: List[NormalizedBlock], config: Dict[str, Any]) -> DetectionResult:
        ...


@runtime_checkable
class RedactionAdapter(Protocol):
    def redact(
        self,
        blocks: List[NormalizedBlock],
        findings: List[PIIFinding],
        config: Dict[str, Any],
    ) -> RedactionResult:
        ...


@runtime_checkable
class RescanAdapter(Protocol):
    def rescan(self, sanitized_blocks: List[RedactedBlock], config: Dict[str, Any]) -> RescanResult:
        ...


# Minimal Safe Fallback Stubs for Decoupled Execution (Persons 2-4)

class StubExtractionAdapter:
    """Non-production placeholder that must never authorize document release."""

    def extract(self, manifest: DocumentManifest, config: Dict[str, Any]) -> ExtractionResult:
        logger.info(
            "StubExtractionAdapter invoked: doc_id=%s, format=%s",
            manifest.document_id[:8],
            manifest.detected_format.value,
        )
        # Keep a block so interface tests can exercise downstream wiring. The
        # release gate below still rejects this placeholder adapter.
        block = NormalizedBlock(
            document_id=manifest.document_id,
            block_id=f"doc_{manifest.document_id[:6]}_p1_b1",
            page_or_slide=1,
            source_kind=SourceKind.PARAGRAPH,
            reading_order=1,
            text=f"Sample extracted content for {manifest.filename}",
            ocr_confidence=1.0,
            extraction_complete=True,
        )
        return ExtractionResult(
            document_id=manifest.document_id,
            blocks=[block],
            extraction_complete=True,
            mean_ocr_confidence=1.0,
            has_unsupported_media=False,
            warnings=["Placeholder extraction adapter is not production-ready."],
        )


class StubPIIDetectorAdapter:
    """Non-production placeholder that never claims PII detection coverage."""

    def detect(self, blocks: List[NormalizedBlock], config: Dict[str, Any]) -> DetectionResult:
        logger.info("StubPIIDetectorAdapter invoked: blocks_count=%d", len(blocks))
        return DetectionResult(
            document_id=blocks[0].document_id if blocks else "unknown",
            findings=[],
            category_counts={},
            warnings=["Placeholder PII detector is not production-ready."],
        )


class StubRedactionAdapter:
    """Non-production placeholder that performs no redaction."""

    def redact(
        self,
        blocks: List[NormalizedBlock],
        findings: List[PIIFinding],
        config: Dict[str, Any],
    ) -> RedactionResult:
        logger.info("StubRedactionAdapter invoked: findings_count=%d", len(findings))
        sanitized = []
        for b in blocks:
            sanitized.append(
                RedactedBlock(
                    block_id=b.block_id,
                    page_or_slide=b.page_or_slide,
                    source_kind=b.source_kind,
                    reading_order=b.reading_order,
                    text=b.text,
                    redaction_count=0,
                )
            )
        return RedactionResult(
            document_id=blocks[0].document_id if blocks else "unknown",
            sanitized_blocks=sanitized,
            total_redactions=0,
            category_counts={},
            redaction_map_hash=hashlib.sha256(b"stub_empty_redaction").hexdigest(),
        )


class StubRescanAdapter:
    """Non-production placeholder that performs no independent rescan."""

    def rescan(self, sanitized_blocks: List[RedactedBlock], config: Dict[str, Any]) -> RescanResult:
        logger.info("StubRescanAdapter invoked: blocks_count=%d", len(sanitized_blocks))
        return RescanResult(
            document_id="rescan_stub",
            rescan_passed=True,
            residual_candidates_count=0,
            residual_findings=[],
            rescan_notes="Placeholder rescan is not production-ready.",
        )


class PipelineOrchestrator:
    """
    Person 1 Core Orchestrator:
    Controls lifecycle: Ingest -> Validate -> Manifest -> Extract -> Detect -> Redact -> Rescan -> Gate.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        extraction_adapters: Optional[Dict[SupportedFormat, ExtractionAdapter]] = None,
        pii_detector: Optional[PIIDetectorAdapter] = None,
        redaction_adapter: Optional[RedactionAdapter] = None,
        rescan_adapter: Optional[RescanAdapter] = None,
    ):
        self.config = config or {}
        self.validator = FileValidator(self.config)

        default_extract = StubExtractionAdapter()
        self.extraction_adapters: Dict[SupportedFormat, ExtractionAdapter] = extraction_adapters or {
            SupportedFormat.PDF: default_extract,
            SupportedFormat.PPTX: default_extract,
            SupportedFormat.DOCX: default_extract,
        }

        self.pii_detector: PIIDetectorAdapter = pii_detector or StubPIIDetectorAdapter()
        self.redaction_adapter: RedactionAdapter = redaction_adapter or StubRedactionAdapter()
        self.rescan_adapter: RescanAdapter = rescan_adapter or StubRescanAdapter()

    def process_file(
        self,
        file_path_or_bytes: Path | str | bytes,
        filename: Optional[str] = None,
    ) -> PipelineResponse:
        start_time = time.time()
        raw_filename = filename or (Path(file_path_or_bytes).name if isinstance(file_path_or_bytes, (str, Path)) else "unnamed_document")
        # Treat caller-provided names as display metadata only; never preserve
        # directory traversal components in a manifest or log record.
        actual_filename = Path(raw_filename).name or "unnamed_document"

        logger.info("Initiating ingestion: filename='%s'", actual_filename)

        # 1. Ingestion Validation
        val_res: ValidationResult = self.validator.validate(file_path_or_bytes, filename=actual_filename)
        doc_id = val_res.sha256 or hashlib.sha256(str(actual_filename).encode("utf-8")).hexdigest()

        if not val_res.is_valid:
            logger.warning(
                "Ingestion validation failed: doc_id=%s, reasons=%s",
                doc_id[:8],
                [r.value for r in val_res.quarantine_reasons],
            )
            return PipelineResponse(
                document_id=doc_id,
                filename=actual_filename,
                status=ProcessingStatus.QUARANTINED,
                release_decision=ReleaseDecision.NOT_SAFE_FOR_LLM,
                quarantine_reasons=val_res.quarantine_reasons,
                errors=val_res.errors,
                summary={"processing_time_ms": int((time.time() - start_time) * 1000)},
                audit_report={"validation_passed": False},
            )

        # 2. Document Manifest Generation
        manifest = DocumentManifest(
            document_id=doc_id,
            filename=actual_filename,
            detected_format=val_res.detected_format,
            sha256=val_res.sha256,
            file_size_bytes=val_res.file_size_bytes,
            mime_type=val_res.mime_type,
            processing_status=ProcessingStatus.PROCESSING,
        )

        quarantine_reasons: List[QuarantineReason] = []
        errors: List[str] = []

        # 3. Format Dispatch & Extraction (Person 2)
        adapter = self.extraction_adapters.get(manifest.detected_format)
        if not adapter:
            quarantine_reasons.append(QuarantineReason.UNSUPPORTED_FORMAT)
            errors.append(f"No extraction adapter registered for format {manifest.detected_format.value}")
            return self._build_quarantine_response(manifest, quarantine_reasons, errors, start_time)

        try:
            extract_res = adapter.extract(manifest, self.config)
        except Exception as e:
            logger.error("Extraction adapter error: %s", type(e).__name__)
            quarantine_reasons.append(QuarantineReason.EXTRACTION_FAILED)
            errors.append(f"Extraction error: {type(e).__name__}")
            return self._build_quarantine_response(manifest, quarantine_reasons, errors, start_time)

        if extract_res is None:
            quarantine_reasons.append(QuarantineReason.EXTRACTION_FAILED)
            errors.append("Extraction adapter returned no result.")
            return self._build_quarantine_response(manifest, quarantine_reasons, errors, start_time)

        if not extract_res.extraction_complete:
            quarantine_reasons.append(QuarantineReason.EXTRACTION_INCOMPLETE)
            errors.append("Extraction incomplete or failed structure coverage check.")

        if not extract_res.blocks and QuarantineReason.EXTRACTION_INCOMPLETE not in quarantine_reasons:
            quarantine_reasons.append(QuarantineReason.EXTRACTION_INCOMPLETE)
            errors.append("Extraction returned no normalized blocks.")

        if extract_res.has_unsupported_media:
            quarantine_reasons.append(QuarantineReason.UNSUPPORTED_EMBEDDED_MEDIA)
            errors.extend(extract_res.unsupported_media_details or ["Document contains unsupported media format"])

        ocr_rules = self.config.get("ocr", {})
        min_ocr_conf = ocr_rules.get("min_ocr_confidence_threshold", 0.70)
        if extract_res.mean_ocr_confidence is not None and extract_res.mean_ocr_confidence < min_ocr_conf:
            quarantine_reasons.append(QuarantineReason.LOW_OCR_CONFIDENCE)
            errors.append(f"Mean OCR confidence {extract_res.mean_ocr_confidence:.3f} below threshold {min_ocr_conf}")

        if quarantine_reasons:
            return self._build_quarantine_response(manifest, quarantine_reasons, errors, start_time)

        # 4. PII Detection (Person 3)
        try:
            detect_res = self.pii_detector.detect(extract_res.blocks, self.config)
        except Exception as e:
            logger.error("PII detector error: %s", type(e).__name__)
            quarantine_reasons.append(QuarantineReason.DETECTION_FAILED)
            errors.append(f"Detection error: {type(e).__name__}")
            return self._build_quarantine_response(manifest, quarantine_reasons, errors, start_time)

        if detect_res is None:
            quarantine_reasons.append(QuarantineReason.DETECTION_FAILED)
            errors.append("PII detector returned null response.")
            return self._build_quarantine_response(manifest, quarantine_reasons, errors, start_time)

        logger.info(
            "Detection complete: doc_id=%s, total_findings=%d",
            doc_id[:8],
            len(detect_res.findings),
        )

        # 5. Redaction Handoff (Person 4)
        try:
            redact_res = self.redaction_adapter.redact(extract_res.blocks, detect_res.findings, self.config)
        except Exception as e:
            logger.error("Redaction adapter error: %s", type(e).__name__)
            quarantine_reasons.append(QuarantineReason.REDACTION_FAILED)
            errors.append(f"Redaction error: {type(e).__name__}")
            return self._build_quarantine_response(manifest, quarantine_reasons, errors, start_time)

        if redact_res is None:
            quarantine_reasons.append(QuarantineReason.REDACTION_FAILED)
            errors.append("Redaction returned null response.")
            return self._build_quarantine_response(manifest, quarantine_reasons, errors, start_time)

        logger.info(
            "Redaction complete: doc_id=%s, total_redactions=%d",
            doc_id[:8],
            redact_res.total_redactions,
        )

        # 6. Post-Redaction Rescan Gate (Person 4 / Privacy Gate)
        try:
            rescan_res = self.rescan_adapter.rescan(redact_res.sanitized_blocks, self.config)
        except Exception as e:
            logger.error("Rescan adapter error: %s", type(e).__name__)
            quarantine_reasons.append(QuarantineReason.RESCAN_FAILED)
            errors.append(f"Rescan execution error: {type(e).__name__}")
            return self._build_quarantine_response(manifest, quarantine_reasons, errors, start_time)

        if not rescan_res or not rescan_res.rescan_passed or rescan_res.residual_candidates_count > 0:
            quarantine_reasons.append(QuarantineReason.RESCAN_FAILED)
            cnt = rescan_res.residual_candidates_count if rescan_res else "unknown"
            errors.append(f"Rescan privacy gate failed: {cnt} residual PII candidate(s) detected.")
            return self._build_quarantine_response(manifest, quarantine_reasons, errors, start_time)

        # Placeholder adapters are useful for wiring tests, but they do not
        # provide evidence that the document was actually extracted, detected,
        # redacted, and independently rescanned. Fail closed until real
        # adapters are injected by Persons 2-4.
        placeholder_adapters = (
            isinstance(self.extraction_adapters.get(manifest.detected_format), StubExtractionAdapter),
            isinstance(self.pii_detector, StubPIIDetectorAdapter),
            isinstance(self.redaction_adapter, StubRedactionAdapter),
            isinstance(self.rescan_adapter, StubRescanAdapter),
        )
        if any(placeholder_adapters):
            quarantine_reasons.append(QuarantineReason.MISSING_STEP)
            errors.append("One or more pipeline stages still use a placeholder adapter.")
            return self._build_quarantine_response(manifest, quarantine_reasons, errors, start_time)

        # 7. Privacy Gate Release Approval
        manifest.processing_status = ProcessingStatus.COMPLETED
        sanitized_full_text = "\n\n".join(b.text for b in redact_res.sanitized_blocks)
        sanitized_blocks_dict = [asdict(b) for b in redact_res.sanitized_blocks]

        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.info(
            "Privacy Gate PASSED: doc_id=%s, release_decision=safe_for_llm, duration=%dms",
            doc_id[:8],
            elapsed_ms,
        )

        return PipelineResponse(
            document_id=manifest.document_id,
            filename=manifest.filename,
            status=ProcessingStatus.COMPLETED,
            release_decision=ReleaseDecision.SAFE_FOR_LLM,
            quarantine_reasons=[],
            sanitized_text=sanitized_full_text,
            sanitized_blocks=sanitized_blocks_dict,
            manifest=manifest.to_dict(),
            summary={
                "total_blocks": len(extract_res.blocks),
                "total_redactions": redact_res.total_redactions,
                "category_counts": redact_res.category_counts,
                "mean_ocr_confidence": extract_res.mean_ocr_confidence,
                "processing_time_ms": elapsed_ms,
            },
            audit_report={
                "pipeline_version": self.config.get("version", "1.0.0"),
                "rescan_verified": True,
                "residual_pii_count": 0,
                "redaction_map_hash": redact_res.redaction_map_hash,
                "warnings": extract_res.warnings + redact_res.warnings,
            },
            errors=[],
        )

    def _build_quarantine_response(
        self,
        manifest: DocumentManifest,
        quarantine_reasons: List[QuarantineReason],
        errors: List[str],
        start_time: float,
    ) -> PipelineResponse:
        manifest.processing_status = ProcessingStatus.QUARANTINED
        elapsed_ms = int((time.time() - start_time) * 1000)

        logger.warning(
            "Privacy Gate QUARANTINED: doc_id=%s, release_decision=not_safe_for_llm, reasons=%s",
            manifest.document_id[:8],
            [r.value for r in quarantine_reasons],
        )

        return PipelineResponse(
            document_id=manifest.document_id,
            filename=manifest.filename,
            status=ProcessingStatus.QUARANTINED,
            release_decision=ReleaseDecision.NOT_SAFE_FOR_LLM,
            quarantine_reasons=quarantine_reasons,
            sanitized_text=None,
            sanitized_blocks=[],
            manifest=manifest.to_dict(),
            summary={"processing_time_ms": elapsed_ms},
            audit_report={
                "pipeline_version": self.config.get("version", "1.0.0"),
                "rescan_verified": False,
                "quarantine_timestamp": time.time(),
            },
            errors=errors,
        )
