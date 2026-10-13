"""Mock test fixtures representing Cadence evidence documents adhering to interface contract."""

from typing import List, Tuple
from src.cadence_detection.redaction.models import Block, Finding


def get_organizational_pack_fixture() -> Tuple[List[Block], List[Finding]]:
    """
    Simulates extracted blocks and detected PII from Cadence Organizational Pack (PPTX).
    Features: leadership directory, synthetic phone numbers, corporate emails, RACI matrix.
    """
    blocks = [
        Block(
            document_id="cadence_org_pack",
            block_id="b_slide1_title",
            page_or_slide=1,
            source_kind="pptx_shape",
            reading_order=1,
            text="Cadence Financial Group - Global Leadership & Reporting Structure",
            extraction_complete=True
        ),
        Block(
            document_id="cadence_org_pack",
            block_id="b_slide2_contacts",
            page_or_slide=2,
            source_kind="pptx_table",
            reading_order=2,
            text="Chief Risk Officer: Marcus Vance (marcus.vance@cadence.com, +1 (555) 0114). Office: 45 Wall St, New York.",
            extraction_complete=True
        ),
        Block(
            document_id="cadence_org_pack",
            block_id="b_slide2_dpo",
            page_or_slide=2,
            source_kind="pptx_table",
            reading_order=3,
            text="Data Protection Officer (DPO): Elena Rostova (elena.rostova@cadence.com, +1 (555) 0188). Accountability: PII Detection & Governance.",
            extraction_complete=True
        ),
        Block(
            document_id="cadence_org_pack",
            block_id="b_slide6_raci",
            page_or_slide=6,
            source_kind="pptx_table",
            reading_order=4,
            text="Incident Response RACI Matrix: DPO Accountable (Elena Rostova); Lead Investigator Responsible: Marcus Vance.",
            extraction_complete=True
        )
    ]

    findings = [
        # Slide 2 findings
        Finding(
            document_id="cadence_org_pack",
            block_id="b_slide2_contacts",
            entity_type="PERSON",
            start=20,
            end=32,
            confidence=0.98,
            detector="spacy_ner",
            source_location="slide_2_table_r1"
        ),
        Finding(
            document_id="cadence_org_pack",
            block_id="b_slide2_contacts",
            entity_type="EMAIL",
            start=34,
            end=58,
            confidence=0.99,
            detector="regex_catalog",
            source_location="slide_2_table_r1"
        ),
        Finding(
            document_id="cadence_org_pack",
            block_id="b_slide2_contacts",
            entity_type="PHONE",
            start=60,
            end=73,
            confidence=0.95,
            detector="contextual_phone",
            source_location="slide_2_table_r1"
        ),
        Finding(
            document_id="cadence_org_pack",
            block_id="b_slide2_contacts",
            entity_type="HOME_ADDRESS",
            start=84,
            end=104,
            confidence=0.90,
            detector="spacy_ner",
            source_location="slide_2_table_r1"
        ),
        # Slide 2 DPO findings
        Finding(
            document_id="cadence_org_pack",
            block_id="b_slide2_dpo",
            entity_type="PERSON",
            start=31,
            end=44,
            confidence=0.99,
            detector="spacy_ner",
            source_location="slide_2_table_r2"
        ),
        Finding(
            document_id="cadence_org_pack",
            block_id="b_slide2_dpo",
            entity_type="EMAIL",
            start=46,
            end=71,
            confidence=0.99,
            detector="regex_catalog",
            source_location="slide_2_table_r2"
        ),
        Finding(
            document_id="cadence_org_pack",
            block_id="b_slide2_dpo",
            entity_type="PHONE",
            start=73,
            end=86,
            confidence=0.95,
            detector="contextual_phone",
            source_location="slide_2_table_r2"
        ),
        # Slide 6 recurring names (checks stable token preservation)
        Finding(
            document_id="cadence_org_pack",
            block_id="b_slide6_raci",
            entity_type="PERSON",
            start=48,
            end=61,
            confidence=0.99,
            detector="spacy_ner",
            source_location="slide_6_table_r1"
        ),
        Finding(
            document_id="cadence_org_pack",
            block_id="b_slide6_raci",
            entity_type="PERSON",
            start=95,
            end=107,
            confidence=0.98,
            detector="spacy_ner",
            source_location="slide_6_table_r1"
        ),
    ]

    return blocks, findings


def get_risk_policy_fixture() -> Tuple[List[Block], List[Finding]]:
    """
    Simulates extracted blocks from Risk Management Policy v6.0 (PDF).
    Features: Section 16.5 incident narrative, employee ID, and audit log.
    """
    blocks = [
        Block(
            document_id="cadence_risk_policy",
            block_id="b_sec16_narrative",
            page_or_slide=22,
            source_kind="pdf_ocr_block",
            reading_order=1,
            text="Section 16.5 Incident Report: Analyst David Cho (EMP-49821) escalated an unencrypted data export containing customer account ACC-910283.",
            OCR_confidence=0.94,
            extraction_complete=True
        ),
        Block(
            document_id="cadence_risk_policy",
            block_id="b_audit_log",
            page_or_slide=20,
            source_kind="pdf_ocr_block",
            reading_order=2,
            text="Audit Log: User David Cho accessed database from IP 192.168.1.45 at 14:32:10 UTC.",
            OCR_confidence=0.91,
            extraction_complete=True
        )
    ]

    findings = [
        Finding(
            document_id="cadence_risk_policy",
            block_id="b_sec16_narrative",
            entity_type="PERSON",
            start=39,
            end=48,
            confidence=0.96,
            detector="spacy_ner",
            source_location="page_22_p1"
        ),
        Finding(
            document_id="cadence_risk_policy",
            block_id="b_sec16_narrative",
            entity_type="EMPLOYEE_ID",
            start=50,
            end=59,
            confidence=0.99,
            detector="regex_catalog",
            source_location="page_22_p1"
        ),
        Finding(
            document_id="cadence_risk_policy",
            block_id="b_sec16_narrative",
            entity_type="BANK_ACCOUNT",
            start=129,
            end=139,
            confidence=0.92,
            detector="regex_catalog",
            source_location="page_22_p1"
        ),
        Finding(
            document_id="cadence_risk_policy",
            block_id="b_audit_log",
            entity_type="PERSON",
            start=16,
            end=25,
            confidence=0.95,
            detector="spacy_ner",
            source_location="page_20_p1"
        ),
    ]

    return blocks, findings
