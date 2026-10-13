"""
Cadence Detection Pipeline - Core Contracts and Schema Interfaces
Owned by Person 1 (Architecture, Ingestion, and Integration Lead).
Compatible across standard library, pydantic, and json serialization.
"""

from __future__ import annotations

import enum
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class ProcessingStatus(str, enum.Enum):
    ACCEPTED = "accepted"
    PROCESSING = "processing"
    COMPLETED = "completed"
    QUARANTINED = "quarantined"
    FAILED = "failed"


class ReleaseDecision(str, enum.Enum):
    SAFE_FOR_LLM = "safe_for_llm"
    NOT_SAFE_FOR_LLM = "not_safe_for_llm"


class QuarantineReason(str, enum.Enum):
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"
    MIME_EXTENSION_MISMATCH = "MIME_EXTENSION_MISMATCH"
    FILE_OVERSIZED = "FILE_OVERSIZED"
    CORRUPT_FILE = "CORRUPT_FILE"
    PASSWORD_PROTECTED = "PASSWORD_PROTECTED"
    EXTRACTION_FAILED = "EXTRACTION_FAILED"
    EXTRACTION_INCOMPLETE = "EXTRACTION_INCOMPLETE"
    UNSUPPORTED_EMBEDDED_MEDIA = "UNSUPPORTED_EMBEDDED_MEDIA"
    LOW_OCR_CONFIDENCE = "LOW_OCR_CONFIDENCE"
    DETECTION_FAILED = "DETECTION_FAILED"
    REDACTION_FAILED = "REDACTION_FAILED"
    RESCAN_FAILED = "RESCAN_FAILED"
    MISSING_STEP = "MISSING_STEP"


class SupportedFormat(str, enum.Enum):
    PDF = "pdf"
    PPTX = "pptx"
    DOCX = "docx"


class SourceKind(str, enum.Enum):
    PARAGRAPH = "paragraph"
    HEADING = "heading"
    TABLE_CELL = "table_cell"
    SLIDE_SHAPE = "slide_shape"
    SLIDE_NOTES = "slide_notes"
    HEADER_FOOTER = "header_footer"
    TEXT_BOX = "text_box"
    OCR_IMAGE_REGION = "ocr_image_region"


@dataclass
class BoundingBox:
    x0: float
    y0: float
    x1: float
    y1: float
    coord_system: str = "points"
    page_width: Optional[float] = None
    page_height: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SourceLocation:
    page_or_slide: int
    block_id: str
    source_kind: SourceKind
    reading_order: int
    table_row: Optional[int] = None
    table_column: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["source_kind"] = self.source_kind.value if isinstance(self.source_kind, SourceKind) else self.source_kind
        return d


@dataclass
class NormalizedBlock:
    document_id: str
    block_id: str
    page_or_slide: int
    source_kind: SourceKind
    reading_order: int
    text: str
    table_row: Optional[int] = None
    table_column: Optional[int] = None
    bbox: Optional[BoundingBox] = None
    ocr_confidence: Optional[float] = None
    extraction_complete: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        res = {
            "document_id": self.document_id,
            "block_id": self.block_id,
            "page_or_slide": self.page_or_slide,
            "source_kind": self.source_kind.value if isinstance(self.source_kind, SourceKind) else self.source_kind,
            "reading_order": self.reading_order,
            "text": self.text,
            "table_row": self.table_row,
            "table_column": self.table_column,
            "bbox": self.bbox.to_dict() if self.bbox else None,
            "ocr_confidence": self.ocr_confidence,
            "extraction_complete": self.extraction_complete,
            "metadata": self.metadata,
        }
        return res


@dataclass
class DocumentManifest:
    document_id: str
    filename: str
    detected_format: SupportedFormat
    sha256: str
    file_size_bytes: int
    mime_type: str
    processing_status: ProcessingStatus = ProcessingStatus.ACCEPTED
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["detected_format"] = (
            self.detected_format.value if isinstance(self.detected_format, SupportedFormat) else self.detected_format
        )
        res["processing_status"] = (
            self.processing_status.value
            if isinstance(self.processing_status, ProcessingStatus)
            else self.processing_status
        )
        return res


@dataclass
class PIIFinding:
    finding_id: str
    document_id: str
    block_id: str
    entity_type: str
    start: int
    end: int
    confidence: float
    detector: str
    source_location: Optional[SourceLocation] = None
    validation_status: str = "valid"

    def to_dict(self, include_raw_value: bool = False) -> Dict[str, Any]:
        # Raw value is strictly excluded by default to avoid PII exposure
        return {
            "finding_id": self.finding_id,
            "document_id": self.document_id,
            "block_id": self.block_id,
            "entity_type": self.entity_type,
            "start": self.start,
            "end": self.end,
            "confidence": self.confidence,
            "detector": self.detector,
            "source_location": self.source_location.to_dict() if self.source_location else None,
            "validation_status": self.validation_status,
        }


@dataclass
class ExtractionResult:
    document_id: str
    blocks: List[NormalizedBlock]
    extraction_complete: bool
    mean_ocr_confidence: Optional[float] = None
    has_unsupported_media: bool = False
    unsupported_media_details: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DetectionResult:
    document_id: str
    findings: List[PIIFinding]
    category_counts: Dict[str, int] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RedactedBlock:
    block_id: str
    page_or_slide: int
    source_kind: SourceKind
    reading_order: int
    text: str
    redaction_count: int = 0


@dataclass
class RedactionResult:
    document_id: str
    sanitized_blocks: List[RedactedBlock]
    total_redactions: int
    category_counts: Dict[str, int]
    redaction_map_hash: str
    warnings: List[str] = field(default_factory=list)


@dataclass
class RescanResult:
    document_id: str
    rescan_passed: bool
    residual_candidates_count: int
    residual_findings: List[PIIFinding] = field(default_factory=list)
    rescan_notes: str = ""


@dataclass
class PipelineResponse:
    document_id: str
    filename: str
    status: ProcessingStatus
    release_decision: ReleaseDecision
    quarantine_reasons: List[QuarantineReason] = field(default_factory=list)
    sanitized_text: Optional[str] = None
    sanitized_blocks: List[Dict[str, Any]] = field(default_factory=list)
    manifest: Optional[Dict[str, Any]] = None
    summary: Dict[str, Any] = field(default_factory=dict)
    audit_report: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "filename": self.filename,
            "status": self.status.value if isinstance(self.status, ProcessingStatus) else self.status,
            "release_decision": (
                self.release_decision.value
                if isinstance(self.release_decision, ReleaseDecision)
                else self.release_decision
            ),
            "quarantine_reasons": [
                r.value if isinstance(r, QuarantineReason) else r for r in self.quarantine_reasons
            ],
            "sanitized_text": self.sanitized_text,
            "sanitized_blocks": self.sanitized_blocks,
            "manifest": self.manifest,
            "summary": self.summary,
            "audit_report": self.audit_report,
            "errors": self.errors,
        }
