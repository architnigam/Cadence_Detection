"""
Cadence Detection Pipeline - Person 1 Ingestion and Orchestration Test Suite
Covers:
- Supported format acceptance (PDF, PPTX, DOCX)
- Unsupported format rejection
- MIME/extension mismatch
- Corrupt file handling
- Oversized file handling
- Password-protected file handling
- Deterministic document IDs
- Manifest creation
- Dispatch to correct adapter
- Missing extraction result
- Missing detection result
- Failed redaction
- Residual PII after rescan
- Unsupported embedded content
- Low-confidence OCR
- Quarantine decisions
- Successful end-to-end orchestration with mocked components
- Zero raw PII in logs check
"""

import io
import json
import logging
import os
import sys
import unittest
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure src is on sys.path
REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

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
    PipelineOrchestrator,
    StubExtractionAdapter,
    StubPIIDetectorAdapter,
    StubRedactionAdapter,
    StubRescanAdapter,
)
from cadence_detection.ingestion.validator import FileValidator


def make_valid_pdf_bytes() -> bytes:
    # A minimal valid PDF structure with header, body, xref, and trailer EOF
    content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>
endobj
xref
0 4
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
trailer
<< /Size 4 /Root 1 0 R >>
startxref
190
%%EOF
"""
    return content


def make_valid_pptx_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", b"<Types></Types>")
        zf.writestr("ppt/presentation.xml", b"<p:presentation></p:presentation>")
        zf.writestr("ppt/slides/slide1.xml", b"<p:sld></p:sld>")
    return buf.getvalue()


def make_valid_docx_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", b"<Types></Types>")
        zf.writestr("word/document.xml", b"<w:document></w:document>")
    return buf.getvalue()


class TestIngestionAndValidation(unittest.TestCase):
    def setUp(self):
        self.config_path = REPO_ROOT / "config" / "pipeline.json"
        with open(self.config_path, "r") as f:
            self.config = json.load(f)
        self.validator = FileValidator(self.config)

    def test_supported_format_acceptance_pdf(self):
        pdf_bytes = make_valid_pdf_bytes()
        res = self.validator.validate(pdf_bytes, filename="sample.pdf")
        self.assertTrue(res.is_valid)
        self.assertEqual(res.detected_format, SupportedFormat.PDF)
        self.assertEqual(res.mime_type, "application/pdf")
        self.assertEqual(len(res.quarantine_reasons), 0)

    def test_supported_format_acceptance_pptx(self):
        pptx_bytes = make_valid_pptx_bytes()
        res = self.validator.validate(pptx_bytes, filename="deck.pptx")
        self.assertTrue(res.is_valid)
        self.assertEqual(res.detected_format, SupportedFormat.PPTX)
        self.assertEqual(res.mime_type, "application/vnd.openxmlformats-officedocument.presentationml.presentation")

    def test_supported_format_acceptance_docx(self):
        docx_bytes = make_valid_docx_bytes()
        res = self.validator.validate(docx_bytes, filename="training.docx")
        self.assertTrue(res.is_valid)
        self.assertEqual(res.detected_format, SupportedFormat.DOCX)
        self.assertEqual(res.mime_type, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")

    def test_unsupported_format_rejection(self):
        res = self.validator.validate(b"hello world", filename="notes.txt")
        self.assertFalse(res.is_valid)
        self.assertIn(QuarantineReason.UNSUPPORTED_FORMAT, res.quarantine_reasons)

        res_exe = self.validator.validate(b"MZ\x90\x00", filename="binary.exe")
        self.assertFalse(res_exe.is_valid)
        self.assertIn(QuarantineReason.UNSUPPORTED_FORMAT, res_exe.quarantine_reasons)

    def test_mime_extension_mismatch(self):
        # A text file disguised as a PDF
        fake_pdf = b"This is not a real pdf file"
        res = self.validator.validate(fake_pdf, filename="fake.pdf")
        self.assertFalse(res.is_valid)
        self.assertIn(QuarantineReason.MIME_EXTENSION_MISMATCH, res.quarantine_reasons)

    def test_corrupt_pdf_handling(self):
        # Starts with %PDF- but truncated/missing EOF and trailers
        corrupt_pdf = b"%PDF-1.4\n1 0 obj garbage data"
        res = self.validator.validate(corrupt_pdf, filename="corrupt.pdf")
        self.assertFalse(res.is_valid)
        self.assertIn(QuarantineReason.CORRUPT_FILE, res.quarantine_reasons)

    def test_corrupt_ooxml_zip_handling(self):
        # Starts with PK\x03\x04 but invalid zip stream
        corrupt_docx = b"PK\x03\x04random_corrupt_bytes_not_a_valid_zip"
        res = self.validator.validate(corrupt_docx, filename="corrupt.docx")
        self.assertFalse(res.is_valid)
        self.assertIn(QuarantineReason.CORRUPT_FILE, res.quarantine_reasons)

    def test_oversized_file_handling(self):
        small_config = {"limits": {"max_file_size_bytes": 100, "max_file_size_by_format": {"pdf": 100}}}
        validator = FileValidator(small_config)
        large_pdf = make_valid_pdf_bytes() + (b"A" * 200)
        res = validator.validate(large_pdf, filename="big.pdf")
        self.assertFalse(res.is_valid)
        self.assertIn(QuarantineReason.FILE_OVERSIZED, res.quarantine_reasons)

    def test_password_protected_pdf(self):
        # PDF with /Encrypt dictionary
        pwd_pdf = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [] /Count 0 >>
endobj
3 0 obj
<< /Filter /Standard /V 2 /R 3 /Encrypt >>
endobj
trailer
<< /Size 4 /Root 1 0 R /Encrypt 3 0 R >>
startxref
190
%%EOF
"""
        res = self.validator.validate(pwd_pdf, filename="protected.pdf")
        self.assertFalse(res.is_valid)
        self.assertIn(QuarantineReason.PASSWORD_PROTECTED, res.quarantine_reasons)

    def test_deterministic_document_id(self):
        pdf1 = make_valid_pdf_bytes()
        res1 = self.validator.validate(pdf1, filename="file_version_a.pdf")
        res2 = self.validator.validate(pdf1, filename="renamed_version_b.pdf")
        # SHA256 must be identical despite different filenames
        self.assertEqual(res1.sha256, res2.sha256)
        self.assertTrue(len(res1.sha256) == 64)


class TestPipelineOrchestration(unittest.TestCase):
    def setUp(self):
        self.config_path = REPO_ROOT / "config" / "pipeline.json"
        with open(self.config_path, "r") as f:
            self.config = json.load(f)

    def test_placeholder_adapters_fail_closed(self):
        orchestrator = PipelineOrchestrator(config=self.config)
        pdf_bytes = make_valid_pdf_bytes()

        response = orchestrator.process_file(pdf_bytes, filename="policy.pdf")
        self.assertEqual(response.status, ProcessingStatus.QUARANTINED)
        self.assertEqual(response.release_decision, ReleaseDecision.NOT_SAFE_FOR_LLM)
        self.assertIn(QuarantineReason.MISSING_STEP, response.quarantine_reasons)
        self.assertIsNone(response.sanitized_text)

    def test_dispatch_to_correct_format_adapters(self):
        mock_pdf_adapter = MagicMock()
        mock_pptx_adapter = MagicMock()
        mock_docx_adapter = MagicMock()

        dummy_block = NormalizedBlock(
            document_id="doc123",
            block_id="b1",
            page_or_slide=1,
            source_kind=SourceKind.PARAGRAPH,
            reading_order=1,
            text="Clean test block",
            ocr_confidence=0.99,
            extraction_complete=True,
        )
        dummy_result = ExtractionResult(
            document_id="doc123",
            blocks=[dummy_block],
            extraction_complete=True,
            mean_ocr_confidence=0.99,
        )

        mock_pdf_adapter.extract.return_value = dummy_result
        mock_pptx_adapter.extract.return_value = dummy_result
        mock_docx_adapter.extract.return_value = dummy_result

        adapters = {
            SupportedFormat.PDF: mock_pdf_adapter,
            SupportedFormat.PPTX: mock_pptx_adapter,
            SupportedFormat.DOCX: mock_docx_adapter,
        }

        orch = PipelineOrchestrator(config=self.config, extraction_adapters=adapters)

        orch.process_file(make_valid_pdf_bytes(), filename="test.pdf")
        mock_pdf_adapter.extract.assert_called_once()
        mock_pptx_adapter.extract.assert_not_called()
        mock_docx_adapter.extract.assert_not_called()

        orch.process_file(make_valid_pptx_bytes(), filename="test.pptx")
        mock_pptx_adapter.extract.assert_called_once()

        orch.process_file(make_valid_docx_bytes(), filename="test.docx")
        mock_docx_adapter.extract.assert_called_once()

    def test_missing_or_incomplete_extraction_quarantine(self):
        mock_adapter = MagicMock()
        mock_adapter.extract.return_value = ExtractionResult(
            document_id="doc123",
            blocks=[],
            extraction_complete=False,  # Failed coverage
        )

        orch = PipelineOrchestrator(
            config=self.config,
            extraction_adapters={SupportedFormat.PDF: mock_adapter},
        )
        response = orch.process_file(make_valid_pdf_bytes(), filename="incomplete.pdf")

        self.assertEqual(response.status, ProcessingStatus.QUARANTINED)
        self.assertEqual(response.release_decision, ReleaseDecision.NOT_SAFE_FOR_LLM)
        self.assertIn(QuarantineReason.EXTRACTION_INCOMPLETE, response.quarantine_reasons)

    def test_low_confidence_ocr_quarantine(self):
        mock_adapter = MagicMock()
        dummy_block = NormalizedBlock(
            document_id="doc123",
            block_id="b1",
            page_or_slide=1,
            source_kind=SourceKind.OCR_IMAGE_REGION,
            reading_order=1,
            text="Fuzzy scanned text",
            ocr_confidence=0.45,  # Very low
            extraction_complete=True,
        )
        mock_adapter.extract.return_value = ExtractionResult(
            document_id="doc123",
            blocks=[dummy_block],
            extraction_complete=True,
            mean_ocr_confidence=0.45,  # Below 0.70 threshold
        )

        orch = PipelineOrchestrator(
            config=self.config,
            extraction_adapters={SupportedFormat.PDF: mock_adapter},
        )
        response = orch.process_file(make_valid_pdf_bytes(), filename="fuzzy_scan.pdf")

        self.assertEqual(response.status, ProcessingStatus.QUARANTINED)
        self.assertEqual(response.release_decision, ReleaseDecision.NOT_SAFE_FOR_LLM)
        self.assertIn(QuarantineReason.LOW_OCR_CONFIDENCE, response.quarantine_reasons)

    def test_unsupported_embedded_content_quarantine(self):
        mock_adapter = MagicMock()
        dummy_block = NormalizedBlock(
            document_id="doc123",
            block_id="b1",
            page_or_slide=1,
            source_kind=SourceKind.PARAGRAPH,
            reading_order=1,
            text="Document with strange embedded objects",
            ocr_confidence=1.0,
            extraction_complete=True,
        )
        mock_adapter.extract.return_value = ExtractionResult(
            document_id="doc123",
            blocks=[dummy_block],
            extraction_complete=True,
            has_unsupported_media=True,
            unsupported_media_details=["Unconvertible EMF vector in appendix C"],
        )

        orch = PipelineOrchestrator(
            config=self.config,
            extraction_adapters={SupportedFormat.DOCX: mock_adapter},
        )
        response = orch.process_file(make_valid_docx_bytes(), filename="tprm.docx")

        self.assertEqual(response.status, ProcessingStatus.QUARANTINED)
        self.assertEqual(response.release_decision, ReleaseDecision.NOT_SAFE_FOR_LLM)
        self.assertIn(QuarantineReason.UNSUPPORTED_EMBEDDED_MEDIA, response.quarantine_reasons)

    def test_missing_detection_result_quarantine(self):
        mock_detector = MagicMock()
        mock_detector.detect.return_value = None  # None returned

        orch = PipelineOrchestrator(config=self.config, pii_detector=mock_detector)
        response = orch.process_file(make_valid_pdf_bytes(), filename="test.pdf")

        self.assertEqual(response.status, ProcessingStatus.QUARANTINED)
        self.assertEqual(response.release_decision, ReleaseDecision.NOT_SAFE_FOR_LLM)
        self.assertIn(QuarantineReason.DETECTION_FAILED, response.quarantine_reasons)

    def test_failed_redaction_quarantine(self):
        mock_redactor = MagicMock()
        mock_redactor.redact.side_effect = RuntimeError("Redaction crash on invalid offset")

        orch = PipelineOrchestrator(config=self.config, redaction_adapter=mock_redactor)
        response = orch.process_file(make_valid_pdf_bytes(), filename="test.pdf")

        self.assertEqual(response.status, ProcessingStatus.QUARANTINED)
        self.assertEqual(response.release_decision, ReleaseDecision.NOT_SAFE_FOR_LLM)
        self.assertIn(QuarantineReason.REDACTION_FAILED, response.quarantine_reasons)

    def test_residual_pii_after_rescan_quarantine(self):
        # Simulate Person 4 rescan detecting an unredacted PII span
        mock_rescan = MagicMock()
        mock_rescan.rescan.return_value = RescanResult(
            document_id="doc123",
            rescan_passed=False,
            residual_candidates_count=2,
            residual_findings=[
                PIIFinding(
                    finding_id="res-1",
                    document_id="doc123",
                    block_id="b1",
                    entity_type="EMAIL",
                    start=10,
                    end=25,
                    confidence=0.95,
                    detector="rescan_regex",
                )
            ],
            rescan_notes="Found leaked email address in table footer",
        )

        orch = PipelineOrchestrator(config=self.config, rescan_adapter=mock_rescan)
        response = orch.process_file(make_valid_pdf_bytes(), filename="test.pdf")

        self.assertEqual(response.status, ProcessingStatus.QUARANTINED)
        self.assertEqual(response.release_decision, ReleaseDecision.NOT_SAFE_FOR_LLM)
        self.assertIn(QuarantineReason.RESCAN_FAILED, response.quarantine_reasons)
        self.assertIn("residual PII candidate", response.errors[0])

    def test_zero_raw_pii_written_to_logs(self):
        # Create a mock detector that flags a PII span with secret sensitive info
        class MockSensitiveDetector:
            def detect(self, blocks, config):
                finding = PIIFinding(
                    finding_id="f1",
                    document_id=blocks[0].document_id,
                    block_id=blocks[0].block_id,
                    entity_type="PERSON",
                    start=0,
                    end=15,
                    confidence=0.99,
                    detector="test_ner",
                )
                return DetectionResult(
                    document_id=blocks[0].document_id,
                    findings=[finding],
                    category_counts={"PERSON": 1},
                )

        sensitive_text = "SECRET_PERSON_NAME_XYZ"

        class MockSensitiveExtractor:
            def extract(self, manifest, config):
                b = NormalizedBlock(
                    document_id=manifest.document_id,
                    block_id="b1",
                    page_or_slide=1,
                    source_kind=SourceKind.PARAGRAPH,
                    reading_order=1,
                    text=sensitive_text,
                    ocr_confidence=1.0,
                    extraction_complete=True,
                )
                return ExtractionResult(document_id=manifest.document_id, blocks=[b], extraction_complete=True)

        orch = PipelineOrchestrator(
            config=self.config,
            extraction_adapters={SupportedFormat.PDF: MockSensitiveExtractor()},
            pii_detector=MockSensitiveDetector(),
        )

        with self.assertLogs("cadence.ingestion", level="INFO") as log_capture:
            orch.process_file(make_valid_pdf_bytes(), filename="confidential.pdf")

            # Verify that the raw sensitive string NEVER appears anywhere in the log records
            full_log_output = "\n".join(log_capture.output)
            self.assertNotIn(sensitive_text, full_log_output)
        self.assertIn("Privacy Gate QUARANTINED", full_log_output)
        self.assertIn(QuarantineReason.MISSING_STEP.value, full_log_output)


if __name__ == "__main__":
    unittest.main()
