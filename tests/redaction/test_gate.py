"""Unit tests for SafeReleaseGate."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.cadence_detection.redaction.models import Block
from src.cadence_detection.redaction.redactor import TextRedactor
from src.cadence_detection.redaction.gate import SafeReleaseGate
from tests.redaction.fixtures import get_organizational_pack_fixture, get_risk_policy_fixture


def test_gate_approves_clean_document():
    """Verifies that a fully extracted document with 100% redacted PII is APPROVED."""
    blocks, findings = get_organizational_pack_fixture()
    redactor = TextRedactor()
    sanitized_blocks, _, _ = redactor.redact_document(blocks, findings)

    gate = SafeReleaseGate()
    result = gate.evaluate(sanitized_blocks)

    assert result.status == "APPROVED"
    assert result.residual_pii_count == 0
    assert result.extraction_complete is True
    assert len(result.warnings) == 0


def test_gate_quarantines_on_pii_leak():
    """Verifies that if an unredacted email or phone number survives, the gate QUARANTINES."""
    gate = SafeReleaseGate()
    leaky_blocks = [
        Block(
            document_id="leaky_doc",
            block_id="b1",
            page_or_slide=1,
            source_kind="text",
            reading_order=1,
            text="Unredacted CEO contact: ceo@cadence.com and phone +1 (555) 9988.",
            extraction_complete=True
        )
    ]

    result = gate.evaluate(leaky_blocks)
    assert result.status == "QUARANTINED"
    assert result.residual_pii_count >= 1
    assert any("Security Gate Violation" in result.reason for _ in [1])


def test_gate_quarantines_on_incomplete_extraction():
    """Verifies that incomplete extraction flags prevent safe release to downstream LLM."""
    gate = SafeReleaseGate()
    incomplete_blocks = [
        Block(
            document_id="incomplete_doc",
            block_id="b1",
            page_or_slide=1,
            source_kind="pdf_ocr",
            reading_order=1,
            text="Sanitized text [PERSON_1] safe content.",
            extraction_complete=False  # Upstream flagged dropped image or unparsed page
        )
    ]

    result = gate.evaluate(incomplete_blocks)
    assert result.status == "QUARANTINED"
    assert result.extraction_complete is False
    assert "Completeness Gate Violation" in result.reason


def test_gate_flags_low_ocr_confidence():
    """Verifies that low OCR confidence blocks trigger quality warnings and quarantine."""
    gate = SafeReleaseGate(min_ocr_confidence=0.70)
    low_ocr_blocks = [
        Block(
            document_id="low_ocr_doc",
            block_id="b1",
            page_or_slide=1,
            source_kind="pdf_ocr",
            reading_order=1,
            text="Sanitized text [PERSON_1] safe content.",
            OCR_confidence=0.52,  # Below threshold
            extraction_complete=True
        )
    ]

    result = gate.evaluate(low_ocr_blocks)
    assert result.status == "QUARANTINED"
    assert len(result.warnings) > 0
    assert "Quality Review Required" in result.reason


if __name__ == "__main__":
    test_gate_approves_clean_document()
    test_gate_quarantines_on_pii_leak()
    test_gate_quarantines_on_incomplete_extraction()
    test_gate_flags_low_ocr_confidence()
    print("All SafeReleaseGate tests passed successfully!")
