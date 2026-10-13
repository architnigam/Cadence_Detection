"""Unit tests for TextRedactor."""

import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.cadence_detection.redaction.models import Block, Finding
from src.cadence_detection.redaction.redactor import TextRedactor
from tests.redaction.fixtures import get_organizational_pack_fixture, get_risk_policy_fixture


def test_basic_redaction():
    redactor = TextRedactor()
    block = Block(
        document_id="doc1",
        block_id="b1",
        page_or_slide=1,
        source_kind="text",
        reading_order=1,
        text="Contact Marcus Vance at marcus.vance@cadence.com."
    )
    findings = [
        Finding("doc1", "b1", "PERSON", 8, 20, 0.99, "detector"),
        Finding("doc1", "b1", "EMAIL", 24, 48, 0.99, "detector"),
    ]
    token_reg = {"PERSON": {}, "EMAIL": {}}
    counters = {"PERSON": 0, "EMAIL": 0}

    sanitized, applied = redactor.redact_block(block, findings, token_reg, counters)

    assert "[PERSON_1]" in sanitized
    assert "[EMAIL_1]" in sanitized
    assert "Marcus Vance" not in sanitized
    assert "marcus.vance@cadence.com" not in sanitized
    assert sanitized.startswith("Contact [PERSON_1] at [EMAIL_1].")


def test_stable_placeholder_consistency():
    """Verifies that recurring identical names get assigned the SAME token."""
    redactor = TextRedactor()
    blocks, findings = get_organizational_pack_fixture()

    sanitized_blocks, token_mapping, category_counts = redactor.redact_document(blocks, findings)

    # Marcus Vance is on slide 2 and slide 6
    # Elena Rostova is on slide 2 and slide 6
    slide2_contacts = next(b.text for b in sanitized_blocks if b.block_id == "b_slide2_contacts")
    slide2_dpo = next(b.text for b in sanitized_blocks if b.block_id == "b_slide2_dpo")
    slide6_raci = next(b.text for b in sanitized_blocks if b.block_id == "b_slide6_raci")

    assert "Marcus Vance" not in slide2_contacts
    assert "Marcus Vance" not in slide6_raci
    assert "Elena Rostova" not in slide2_dpo
    assert "Elena Rostova" not in slide6_raci

    # Stable token check: Marcus Vance token in slide 2 matches slide 6
    marcus_token = token_mapping.get("marcus vance")
    elena_token = token_mapping.get("elena rostova")

    assert marcus_token is not None
    assert elena_token is not None
    assert marcus_token != elena_token
    assert marcus_token in slide2_contacts
    assert marcus_token in slide6_raci
    assert elena_token in slide2_dpo
    assert elena_token in slide6_raci


def test_overlap_resolution():
    """Verifies that overlapping findings are safely resolved without corrupting text."""
    redactor = TextRedactor()
    block = Block(
        document_id="doc1",
        block_id="b1",
        page_or_slide=1,
        source_kind="text",
        reading_order=1,
        text="Call Officer John Smith directly."
    )
    # Overlapping spans: "John Smith" (13-23) vs "Officer John Smith" (5-23)
    findings = [
        Finding("doc1", "b1", "PERSON", 13, 23, 0.90, "ner"),
        Finding("doc1", "b1", "PERSON", 5, 23, 0.85, "rule"),
    ]

    resolved = redactor.resolve_overlaps(findings)
    assert len(resolved) == 1
    # Priority to earliest start and longest span: "Officer John Smith"
    assert resolved[0].start == 5
    assert resolved[0].end == 23


if __name__ == "__main__":
    test_basic_redaction()
    test_stable_placeholder_consistency()
    test_overlap_resolution()
    print("All TextRedactor tests passed successfully!")
