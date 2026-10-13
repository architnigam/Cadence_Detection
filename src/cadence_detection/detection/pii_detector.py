"""
cadence_detection.detection.pii_detector
=========================================
Person 3 – Baseline PII detector: increment 1.  Stdlib-only, deterministic.

Entity types detected:
    EMAIL        – Conservative local@domain.tld pattern.
    PHONE        – Requires a context keyword (Tel, Mobile, Phone, M, …).
                   Confidence scores are heuristic, not calibrated probabilities.
    EMPLOYEE_ID  – Synthetic EMP-<digits> fixture only.  NOT an official Cadence
                   identifier; replace before production use.

Finding fields follow interfaces.md line 8 verbatim.  Offsets are Python Unicode
code-point positions, start-inclusive/end-exclusive into the unmodified block.text.

source_location format "<block_id>:<start>:<end>" is PROVISIONAL – Person 1 or
Person 4 must confirm before treating it as stable.

Overlap policy (PROVISIONAL – Person 1 / Person 4 review required): greedy,
priority = descending confidence → descending span → ascending start → ascending
end → ascending entity_type.  Exact duplicates (same doc/block/type/start/end)
are collapsed to the first occurrence.

Known limitations:
    PHONE/FP-1: keyword + date-like string (e.g. "Tel: 2024-01-01") produces a
        finding.  Date exclusion is out of scope for increment 1.
    PHONE/FP-2: standalone uppercase 'M' is the mobile abbreviation; lowercase
        'm' is excluded via (?-i:M) to avoid unit-prefix false positives.

No raw matched values are logged anywhere in this module.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

DETECTOR_ID = "cadence.detection.pii_detector.v0"


@dataclass(frozen=True)
class Block:
    """Fields consumed by this detector (interfaces.md line 6). Full Block contract owned by Person 1."""
    document_id: str
    block_id: str
    text: str


@dataclass(frozen=True)
class Finding:
    """Detection-layer finding (interfaces.md line 8)."""
    document_id: str
    block_id: str
    entity_type: str
    start: int        # Unicode code-point, inclusive
    end: int          # Unicode code-point, exclusive
    confidence: float
    detector: str
    source_location: str  # PROVISIONAL format – see module docstring


# Conservative local@domain.tld match; does not implement full RFC 5321.
_EMAIL_PATTERN = re.compile(
    r"(?<![.\w@])"
    r"[a-zA-Z0-9._%+\-]+"
    r"@"
    r"[a-zA-Z0-9.\-]+"
    r"\.[a-zA-Z]{2,}"
    r"(?![.\w@])",
    re.UNICODE,
)

# PHONE: keyword-gated. Long keywords are case-insensitive; standalone 'M'
# (mobile abbreviation) uses (?-i:M) to remain case-sensitive – see PHONE/FP-2.
_PHONE_CONTEXT = (
    r"(?:"
    r"(?:tel|telephone|phone|mobile|mob|cell|fax|ph|contact)"
    r"|"
    r"(?<!\w)(?-i:M)(?!\w)"
    r")"
    r"(?:\s*(?:no|num|number|#))?"
    r"\s*[:\-]?\s*"
)
# Digit body: optional leading + or (, then ≥ 7 digits with spaces/dashes/parens.
_PHONE_DIGITS = (
    r"(?:\+?\(?\d[\d\s\-\.\(\)]{5,})"
)
_PHONE_PATTERN = re.compile(
    _PHONE_CONTEXT + r"(" + _PHONE_DIGITS + r")",
    re.IGNORECASE | re.UNICODE,
)

# EMPLOYEE_ID: synthetic EMP-<digits> test fixture only – NOT an official identifier.
_EMP_ID_PATTERN = re.compile(
    r"(?<![A-Za-z0-9\-])"
    r"EMP-\d{3,8}"
    r"(?![A-Za-z0-9\-])",
    re.UNICODE,
)


def _make_source_location(block_id: str, start: int, end: int) -> str:
    """Provisional format "<block_id>:<start>:<end>" – see module docstring."""
    return f"{block_id}:{start}:{end}"


def _match_to_finding(
    m: re.Match,
    *,
    document_id: str,
    block_id: str,
    entity_type: str,
    confidence: float,
    span_group: int | None = None,
) -> Finding:
    """Build a Finding from a Match; span_group selects a capture group (used for PHONE)."""
    if span_group is not None:
        start, end = m.span(span_group)
    else:
        start, end = m.span()

    return Finding(
        document_id=document_id,
        block_id=block_id,
        entity_type=entity_type,
        start=start,
        end=end,
        confidence=confidence,
        detector=DETECTOR_ID,
        source_location=_make_source_location(block_id, start, end),
    )


def _deduplicate(findings: list[Finding]) -> list[Finding]:
    """Remove exact duplicates (same doc/block/type/start/end), keeping first occurrence."""
    seen: set[tuple] = set()
    result: list[Finding] = []
    for f in findings:
        key = (f.document_id, f.block_id, f.entity_type, f.start, f.end)
        if key not in seen:
            seen.add(key)
            result.append(f)
    return result


def _resolve_overlaps(findings: list[Finding]) -> list[Finding]:
    """Greedy overlap resolution using the PROVISIONAL policy in the module docstring.
    Two findings overlap when their [start, end) ranges intersect, regardless of type.
    """

    def priority_key(f: Finding):
        return (-f.confidence, -(f.end - f.start), f.start, f.end, f.entity_type)

    sorted_findings = sorted(findings, key=priority_key)
    accepted: list[Finding] = []

    for candidate in sorted_findings:
        overlaps = any(
            candidate.start < kept.end and candidate.end > kept.start
            for kept in accepted
        )
        if not overlaps:
            accepted.append(candidate)

    # Final sort into document order; the greedy pass does not preserve it.
    accepted.sort(key=lambda f: (f.start, f.end, f.entity_type))
    return accepted


def detect(block: Block) -> list[Finding]:
    """Run all detectors against a Block; return deduplicated, overlap-resolved Findings.

    block.text must be the exact normalized text used for all downstream offset work.
    No raw matched text is logged or retained beyond this function's local scope.
    """
    raw: list[Finding] = []

    # EMAIL
    for m in _EMAIL_PATTERN.finditer(block.text):
        raw.append(
            _match_to_finding(
                m,
                document_id=block.document_id,
                block_id=block.block_id,
                entity_type="EMAIL",
                confidence=0.95,
            )
        )

    # PHONE – span_group=1 captures the digit body, excluding the context keyword.
    for m in _PHONE_PATTERN.finditer(block.text):
        raw.append(
            _match_to_finding(
                m,
                document_id=block.document_id,
                block_id=block.block_id,
                entity_type="PHONE",
                confidence=0.85,
                span_group=1,
            )
        )

    # EMPLOYEE_ID (synthetic test fixture only)
    for m in _EMP_ID_PATTERN.finditer(block.text):
        raw.append(
            _match_to_finding(
                m,
                document_id=block.document_id,
                block_id=block.block_id,
                entity_type="EMPLOYEE_ID",
                confidence=0.80,
            )
        )

    deduped = _deduplicate(raw)
    resolved = _resolve_overlaps(deduped)
    return resolved

