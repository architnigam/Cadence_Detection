"""Data models for Cadence Detection redaction, findings, and safe gate according to docs/design/interfaces.md."""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any


@dataclass
class Finding:
    """Represents a single detected PII entity finding within a block."""
    document_id: str
    block_id: str
    entity_type: str
    start: int  # Python Unicode code-point offset, start inclusive
    end: int    # Python Unicode code-point offset, end exclusive
    confidence: float
    detector: str
    source_location: str = ""
    original_text: Optional[str] = None  # Restricted; kept in-memory only

    def overlaps_with(self, other: "Finding") -> bool:
        """Check if this finding overlaps with another within the same block."""
        if self.block_id != other.block_id:
            return False
        return max(self.start, other.start) < min(self.end, other.end)


@dataclass
class Block:
    """Represents an extracted unit of text (paragraph, cell, slide shape)."""
    document_id: str
    block_id: str
    page_or_slide: Optional[int]  # DOCX/XML and metadata may not have a page index
    source_kind: str    # e.g., 'pptx_shape', 'docx_paragraph', 'pdf_ocr_block'
    reading_order: int
    text: str
    table_row: Optional[int] = None
    table_column: Optional[int] = None
    bbox: Optional[Dict[str, float]] = None
    OCR_confidence: Optional[float] = None
    extraction_complete: bool = True


@dataclass
class GateResult:
    """Outcome of the safe-release privacy verification gate."""
    status: str  # 'APPROVED', 'QUARANTINED', or 'FAILED'
    reason: str
    residual_pii_count: int
    residual_findings: List[Dict[str, Any]] = field(default_factory=list)
    extraction_complete: bool = True
    warnings: List[str] = field(default_factory=list)


@dataclass
class RedactionResult:
    """Full outcome of redaction for a document."""
    document_id: str
    status: str  # 'APPROVED', 'QUARANTINED', 'FAILED'
    sanitized_text: str
    sanitized_blocks: List[Dict[str, Any]]
    token_mapping: Dict[str, str]  # Map of token -> sanitized label (sensitive keys kept local)
    category_counts: Dict[str, int]
    gate_result: GateResult
    extraction_coverage: float = 1.0
    warnings: List[str] = field(default_factory=list)
