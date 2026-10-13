"""
Cadence Detection Pipeline - File Validation and Ingestion Verification
Owned by Person 1 (Architecture, Ingestion, and Integration Lead).
"""

from __future__ import annotations

import hashlib
import os
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from cadence_detection.ingestion.contracts import (
    DocumentManifest,
    ProcessingStatus,
    QuarantineReason,
    SupportedFormat,
)


@dataclass
class ValidationResult:
    is_valid: bool
    detected_format: Optional[SupportedFormat] = None
    mime_type: str = ""
    file_size_bytes: int = 0
    sha256: str = ""
    quarantine_reasons: List[QuarantineReason] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class FileValidator:
    """
    Validates file formats, sizes, integrity, and password protection
    before allowing documents into the extraction pipeline.
    """

    DEFAULT_MAX_FILE_SIZES = {
        SupportedFormat.PDF: 52428800,   # 50 MB
        SupportedFormat.PPTX: 31457280,  # 30 MB
        SupportedFormat.DOCX: 31457280,  # 30 MB
    }

    EXTENSION_MAP = {
        ".pdf": SupportedFormat.PDF,
        ".pptx": SupportedFormat.PPTX,
        ".docx": SupportedFormat.DOCX,
    }

    MAGIC_SIGNATURES = {
        SupportedFormat.PDF: b"%PDF-",
        # Office Open XML formats are PKZip archives
        SupportedFormat.PPTX: b"PK\x03\x04",
        SupportedFormat.DOCX: b"PK\x03\x04",
    }

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        limits = self.config.get("limits", {})
        self.max_file_size_bytes = limits.get("max_file_size_bytes", 52428800)
        self.max_by_format = limits.get("max_file_size_by_format", {})

    def validate(self, file_path_or_bytes: Path | str | bytes, filename: Optional[str] = None) -> ValidationResult:
        raw_bytes: bytes
        actual_filename: str

        if isinstance(file_path_or_bytes, (str, Path)):
            path = Path(file_path_or_bytes)
            actual_filename = filename or path.name
            if not path.exists():
                return ValidationResult(
                    is_valid=False,
                    quarantine_reasons=[QuarantineReason.CORRUPT_FILE],
                    errors=[f"File does not exist: {path.name}"],
                )
            try:
                raw_bytes = path.read_bytes()
            except Exception as e:
                return ValidationResult(
                    is_valid=False,
                    quarantine_reasons=[QuarantineReason.CORRUPT_FILE],
                    errors=[f"Failed to read file: {type(e).__name__}"],
                )
        elif isinstance(file_path_or_bytes, bytes):
            raw_bytes = file_path_or_bytes
            actual_filename = filename or "unnamed_document"
        else:
            return ValidationResult(
                is_valid=False,
                quarantine_reasons=[QuarantineReason.CORRUPT_FILE],
                errors=["Unsupported input type: must be file path or bytes"],
            )

        file_size = len(raw_bytes)
        sha256 = hashlib.sha256(raw_bytes).hexdigest()

        if file_size == 0:
            return ValidationResult(
                is_valid=False,
                file_size_bytes=0,
                sha256=sha256,
                quarantine_reasons=[QuarantineReason.CORRUPT_FILE],
                errors=["File is empty (0 bytes)"],
            )

        # 1. Extension inspection
        ext = os.path.splitext(actual_filename)[1].lower()
        if ext not in self.EXTENSION_MAP:
            return ValidationResult(
                is_valid=False,
                file_size_bytes=file_size,
                sha256=sha256,
                quarantine_reasons=[QuarantineReason.UNSUPPORTED_FORMAT],
                errors=[f"Unsupported file extension '{ext}'. Must be .pdf, .pptx, or .docx."],
            )

        expected_format = self.EXTENSION_MAP[ext]

        # 2. Size limitation check
        max_size = self.max_by_format.get(expected_format.value, self.max_file_size_bytes)
        if file_size > max_size:
            return ValidationResult(
                is_valid=False,
                detected_format=expected_format,
                file_size_bytes=file_size,
                sha256=sha256,
                quarantine_reasons=[QuarantineReason.FILE_OVERSIZED],
                errors=[f"File size {file_size} bytes exceeds limit of {max_size} bytes."],
            )

        # 3. Magic header / MIME verification
        magic = self.MAGIC_SIGNATURES[expected_format]
        if not raw_bytes.startswith(magic):
            return ValidationResult(
                is_valid=False,
                detected_format=expected_format,
                file_size_bytes=file_size,
                sha256=sha256,
                quarantine_reasons=[QuarantineReason.MIME_EXTENSION_MISMATCH],
                errors=[f"File header mismatch: does not match expected {expected_format.value} magic signature."],
            )

        # 4. Format-specific deep structure & encryption verification
        mime_type = self._get_mime_type(expected_format)
        deep_valid, deep_reason, deep_err = self._verify_deep_structure(expected_format, raw_bytes)
        if not deep_valid:
            return ValidationResult(
                is_valid=False,
                detected_format=expected_format,
                mime_type=mime_type,
                file_size_bytes=file_size,
                sha256=sha256,
                quarantine_reasons=[deep_reason] if deep_reason else [QuarantineReason.CORRUPT_FILE],
                errors=[deep_err] if deep_err else ["Structure verification failed."],
            )

        return ValidationResult(
            is_valid=True,
            detected_format=expected_format,
            mime_type=mime_type,
            file_size_bytes=file_size,
            sha256=sha256,
        )

    def _get_mime_type(self, fmt: SupportedFormat) -> str:
        if fmt == SupportedFormat.PDF:
            return "application/pdf"
        elif fmt == SupportedFormat.PPTX:
            return "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        elif fmt == SupportedFormat.DOCX:
            return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        return "application/octet-stream"

    def _verify_deep_structure(
        self, fmt: SupportedFormat, raw_bytes: bytes
    ) -> Tuple[bool, Optional[QuarantineReason], Optional[str]]:
        if fmt == SupportedFormat.PDF:
            return self._verify_pdf(raw_bytes)
        elif fmt in (SupportedFormat.PPTX, SupportedFormat.DOCX):
            return self._verify_ooxml_zip(fmt, raw_bytes)
        return True, None, None

    def _verify_pdf(self, raw_bytes: bytes) -> Tuple[bool, Optional[QuarantineReason], Optional[str]]:
        # PDF must contain an EOF marker or standard trailer
        if b"%%EOF" not in raw_bytes[-4096:] and b"startxref" not in raw_bytes[-4096:]:
            # If EOF is missing near the end, check for basic trailer
            if b"trailer" not in raw_bytes and b"xref" not in raw_bytes:
                return False, QuarantineReason.CORRUPT_FILE, "Malformed PDF: missing trailer / EOF markers"

        # Check for standard PDF password protection dictionary (/Encrypt)
        if b"/Encrypt" in raw_bytes:
            return (
                False,
                QuarantineReason.PASSWORD_PROTECTED,
                "PDF is encrypted or password-protected (/Encrypt dictionary detected)",
            )

        return True, None, None

    def _verify_ooxml_zip(
        self, fmt: SupportedFormat, raw_bytes: bytes
    ) -> Tuple[bool, Optional[QuarantineReason], Optional[str]]:
        import io

        try:
            with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
                # Test zip integrity
                bad_file = zf.testzip()
                if bad_file:
                    return False, QuarantineReason.CORRUPT_FILE, f"Corrupted zip entry in container: {bad_file}"

                # Check for zip-level password protection
                for info in zf.infolist():
                    if info.flag_bits & 0x1:
                        return (
                            False,
                            QuarantineReason.PASSWORD_PROTECTED,
                            f"Archive entry '{info.filename}' is encrypted/password-protected",
                        )

                namelist = zf.namelist()
                # Verify OOXML structure
                if "[Content_Types].xml" not in namelist:
                    return (
                        False,
                        QuarantineReason.CORRUPT_FILE,
                        "Invalid Office Open XML document: missing [Content_Types].xml",
                    )

                if fmt == SupportedFormat.PPTX:
                    has_ppt = any(name.startswith("ppt/") for name in namelist)
                    if not has_ppt:
                        return False, QuarantineReason.CORRUPT_FILE, "Missing 'ppt/' directory in PPTX package"
                elif fmt == SupportedFormat.DOCX:
                    has_word = any(name.startswith("word/") for name in namelist)
                    if not has_word:
                        return False, QuarantineReason.CORRUPT_FILE, "Missing 'word/' directory in DOCX package"

        except zipfile.BadZipFile:
            return False, QuarantineReason.CORRUPT_FILE, "Malformed archive: not a valid zip container"
        except Exception as e:
            return False, QuarantineReason.CORRUPT_FILE, f"Archive inspection error: {type(e).__name__}"

        return True, None, None
