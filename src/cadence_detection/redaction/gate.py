"""Safe-release privacy gate to verify sanitized text before downstream LLM boundary."""

import re
from typing import List, Dict, Any, Optional
from .models import Block, GateResult


class SafeReleaseGate:
    """
    Privacy and completeness gate.
    
    Verifies that:
    1. Extraction was 100% complete without missing pages, dropped media, or unreadable scans.
    2. Zero residual PII patterns survive post-redaction (re-scanning with conservative regexes).
    3. OCR confidence and extraction flags meet quality thresholds.
    
    Returns 'APPROVED', 'QUARANTINED', or 'FAILED'.
    """

    # Conservative regex checks to catch any residual leaked PII
    LEAKAGE_PATTERNS = {
        "EMAIL": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b"),
        "PHONE": re.compile(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
        "SYNTHETIC_PHONE": re.compile(r"\+1\s*\(\d{3}\)\s*\d{3,4}\b"),
        "EMPLOYEE_ID": re.compile(r"\b(?:EMP|DIR|VEND|CAD)-\d{4,8}\b", re.IGNORECASE),
        "NATIONAL_TAX_ID": re.compile(r"\b\d{3}-\d{2}-\d{4}\b|\b[A-Z]{2}\d{6,10}[A-Z]?\b"),
        "PAYMENT_CARD": re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
        "ACCOUNT_NUMBER": re.compile(r"\b(?:ACC|ACCT|ACT)[-_:]?\d{6,12}\b", re.IGNORECASE),
    }

    def __init__(self, min_ocr_confidence: float = 0.65):
        self.min_ocr_confidence = min_ocr_confidence

    def inspect_text_for_residuals(self, text: str) -> List[Dict[str, Any]]:
        """Scans sanitized text for potential residual PII leaks."""
        leaks = []
        for pii_type, pattern in self.LEAKAGE_PATTERNS.items():
            for match in pattern.finditer(text):
                # Ensure the matched text is not an already sanitized placeholder token (e.g., [EMAIL_1])
                val = match.group(0)
                if val.startswith("[") and val.endswith("]") and "_" in val:
                    continue
                leaks.append({
                    "type": pii_type,
                    "matched_text": val,
                    "start": match.start(),
                    "end": match.end()
                })
        return leaks

    def evaluate(self, blocks: List[Block]) -> GateResult:
        """
        Runs the full verification check across all blocks of a document.
        
        Returns:
            GateResult with status: APPROVED, QUARANTINED, or FAILED.
        """
        if not blocks:
            return GateResult(
                status="FAILED",
                reason="Document contains no extracted blocks.",
                residual_pii_count=0,
                extraction_complete=False,
                warnings=["Empty document blocks."]
            )

        warnings: List[str] = []
        residual_findings: List[Dict[str, Any]] = []
        extraction_complete = True

        for block in blocks:
            # 1. Completeness check
            if not getattr(block, "extraction_complete", True):
                extraction_complete = False
                warnings.append(
                    f"Block {block.block_id} (Page/Slide {block.page_or_slide}) flagged incomplete extraction."
                )

            # 2. OCR confidence check
            if block.OCR_confidence is not None and block.OCR_confidence < self.min_ocr_confidence:
                warnings.append(
                    f"Block {block.block_id} has low OCR confidence ({block.OCR_confidence:.2f} < {self.min_ocr_confidence})."
                )

            # 3. Residual PII re-scan
            block_leaks = self.inspect_text_for_residuals(block.text)
            for leak in block_leaks:
                leak["block_id"] = block.block_id
                leak["page_or_slide"] = block.page_or_slide
                residual_findings.append(leak)

        residual_count = len(residual_findings)

        # Gate decision policy
        if residual_count > 0:
            status = "QUARANTINED"
            reason = f"Security Gate Violation: {residual_count} potential residual PII patterns detected post-sanitization."
        elif not extraction_complete:
            status = "QUARANTINED"
            reason = "Completeness Gate Violation: Upstream extraction flagged incomplete content (unsupported media or unparsed pages)."
        elif warnings:
            # Warnings present (e.g. low OCR confidence) but zero leaked PII patterns
            status = "QUARANTINED"
            reason = f"Quality Review Required: {len(warnings)} quality warnings recorded (e.g., low OCR confidence)."
        else:
            status = "APPROVED"
            reason = "Safe for downstream LLM: 100% extraction verified, zero residual PII detected."

        return GateResult(
            status=status,
            reason=reason,
            residual_pii_count=residual_count,
            residual_findings=residual_findings,
            extraction_complete=extraction_complete,
            warnings=warnings
        )
