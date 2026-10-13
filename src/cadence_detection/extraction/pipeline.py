"""Validation and adapter routing; independent of UI and PII detection."""
from __future__ import annotations

import hashlib
from pathlib import Path
import zipfile
from .models import ExtractionOptions, ExtractionResult
from .ocr import default_ocr


def extract_document(path, *, options=None, ocr=None):
    options = options or ExtractionOptions()
    path = Path(path)
    result = ExtractionResult("unknown", path.name, path.suffix.lower().lstrip("."), "")
    if not path.is_file():
        result.issue("FILE_NOT_FOUND", "Input is not a readable regular file", severity="error")
        return result
    try:
        size = path.stat().st_size
    except OSError:
        result.issue("FILE_UNREADABLE", "Input metadata could not be read", severity="error")
        return result
    if size == 0 or size > options.max_file_bytes:
        result.issue("FILE_LIMIT", "Input is empty or exceeds configured size limit", severity="error")
        return result
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024*1024), b""):
                digest.update(chunk)
    except OSError:
        result.issue("FILE_UNREADABLE", "Input could not be read", severity="error")
        return result
    result.sha256 = digest.hexdigest(); result.document_id = result.sha256[:16]
    if result.detected_format not in ("pdf", "pptx", "docx"):
        result.issue("UNSUPPORTED_FORMAT", "Supported formats are PDF, PPTX and DOCX", severity="error")
        return result
    own_ocr = ocr is None
    ocr = ocr if ocr is not None else default_ocr()
    try:
        if result.detected_format == "pdf":
            with path.open("rb") as stream:
                header = stream.read(1024)
            if b"%PDF-" not in header:
                raise ValueError("PDF signature missing")
            from .pdf import extract_pdf
            extract_pdf(path, result, options, ocr)
        else:
            with zipfile.ZipFile(path) as package:
                infos = package.infolist()
                if len(infos) > options.max_zip_entries or sum(i.file_size for i in infos) > options.max_uncompressed_bytes:
                    result.issue("PACKAGE_LIMIT", "Office package exceeds expansion/entry limits", severity="error")
                    return result
                if len({i.filename for i in infos}) != len(infos):
                    raise ValueError("Duplicate ZIP members")
                expected = "word/document.xml" if result.detected_format == "docx" else "ppt/presentation.xml"
                if expected not in package.namelist():
                    raise ValueError("Office package content does not match extension")
                from .office import extract_office
                extract_office(package, result, options, ocr)
        return result.finish()
    except Exception:
        # Do not expose document contents, passwords or parser exception messages in routine logs.
        result.issue("PARSE_FAILED", "Document could not be fully parsed; verify format, encryption and integrity", severity="error")
        result.processing_status = "quarantined" if result.blocks else "failed"
        for block in result.blocks:
            block.extraction_complete = False
        return result
    finally:
        if own_ocr and ocr is not None:
            ocr.close()
