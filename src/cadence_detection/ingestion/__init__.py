"""
Cadence Detection Ingestion and Orchestration Module
Exposes core contracts, validators, and orchestrators for Person 1.
"""

from cadence_detection.ingestion.contracts import (
    BoundingBox,
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
    SourceLocation,
    SupportedFormat,
)
from cadence_detection.ingestion.orchestrator import (
    ExtractionAdapter,
    PIIDetectorAdapter,
    PipelineOrchestrator,
    RedactionAdapter,
    RescanAdapter,
    StubExtractionAdapter,
    StubPIIDetectorAdapter,
    StubRedactionAdapter,
    StubRescanAdapter,
)
from cadence_detection.ingestion.validator import FileValidator, ValidationResult

__all__ = [
    "ProcessingStatus",
    "ReleaseDecision",
    "QuarantineReason",
    "SupportedFormat",
    "SourceKind",
    "BoundingBox",
    "SourceLocation",
    "NormalizedBlock",
    "DocumentManifest",
    "PIIFinding",
    "ExtractionResult",
    "DetectionResult",
    "RedactedBlock",
    "RedactionResult",
    "RescanResult",
    "PipelineResponse",
    "FileValidator",
    "ValidationResult",
    "ExtractionAdapter",
    "PIIDetectorAdapter",
    "RedactionAdapter",
    "RescanAdapter",
    "PipelineOrchestrator",
    "StubExtractionAdapter",
    "StubPIIDetectorAdapter",
    "StubRedactionAdapter",
    "StubRescanAdapter",
]
