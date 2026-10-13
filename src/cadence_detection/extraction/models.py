from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ExtractionOptions:
    dpi: int = 300
    max_file_bytes: int = 100 * 1024 * 1024
    max_uncompressed_bytes: int = 300 * 1024 * 1024
    max_zip_entries: int = 10000
    max_units: int = 500
    max_image_pixels: int = 40_000_000
    min_ocr_confidence: float = 60.0
    password: str | None = None
    include_notes: bool = True
    include_metadata: bool = True
    # Optional normalized [left, top, right, bottom] crops for small image-only evidence.
    ocr_regions: dict[int, list[list[float]]] = field(default_factory=dict)
    # Safe default: audit annotations/attachments/hidden content rather than silently omit.

    def __post_init__(self):
        if not 72 <= self.dpi <= 600:
            raise ValueError("dpi must be between 72 and 600")
        if not 0 <= self.min_ocr_confidence <= 100:
            raise ValueError("min_ocr_confidence must be between 0 and 100")
        for name in ("max_file_bytes", "max_uncompressed_bytes", "max_zip_entries", "max_units", "max_image_pixels"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        for page, regions in self.ocr_regions.items():
            if not isinstance(page, int) or page < 1:
                raise ValueError("OCR region page numbers must be positive integers")
            for box in regions:
                if len(box) != 4 or not (0 <= box[0] < box[2] <= 1 and 0 <= box[1] < box[3] <= 1):
                    raise ValueError("OCR regions must be normalized nonempty boxes")


@dataclass
class Issue:
    code: str
    message: str
    location: str = "document"
    severity: str = "warning"  # info is non-blocking; warning/error prevents completeness


@dataclass
class Block:
    document_id: str
    block_id: str
    page_or_slide: int | None
    source_kind: str
    reading_order: int
    text: str
    source_location: str
    table_row: int | None = None
    table_column: int | None = None
    bbox: list[float] | None = None
    coordinate_space: str | None = None
    ocr_confidence: float | None = None
    extraction_complete: bool = True
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractionResult:
    document_id: str
    filename: str
    detected_format: str
    sha256: str
    processing_status: str = "failed"
    blocks: list[Block] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    units: list[dict[str, Any]] = field(default_factory=list)
    extraction_complete: bool = False

    def issue(self, code, message, location="document", severity="warning"):
        self.issues.append(Issue(code, message, location, severity))

    def add(self, text, source_kind, source_location, page_or_slide=None, **kwargs):
        # Preserve Unicode, tabs, line breaks and offsets. Never collapse whitespace globally.
        if text is None or not text.strip():
            return None
        n = len(self.blocks)
        block = Block(self.document_id, f"{self.document_id}:b{n+1:06}", page_or_slide,
                      source_kind, n, text, source_location, **kwargs)
        self.blocks.append(block)
        return block

    def finish(self):
        if not any(b.source_kind != "metadata" for b in self.blocks):
            self.issue("NO_TEXT", "No text was recovered; review empty or image-only content.")
        self.extraction_complete = bool(self.units) and all(u["processed"] for u in self.units) and not any(
            i.severity != "info" for i in self.issues
        )
        for b in self.blocks:
            b.extraction_complete = b.extraction_complete and self.extraction_complete
        self.processing_status = "extracted" if self.extraction_complete else "quarantined"
        return self

    def to_dict(self):
        out = asdict(self)
        out["coverage"] = {
            "total_units": len(self.units),
            "processed_units": sum(u["processed"] for u in self.units),
            "block_count": len(self.blocks),
            "ocr_block_count": sum(b.ocr_confidence is not None for b in self.blocks),
            "note": "Processing coverage is not OCR accuracy, PII recall, or structure score.",
        }
        return out
