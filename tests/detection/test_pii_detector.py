"""
tests.detection.test_pii_detector
===================================
Synthetic unit tests for cadence_detection.detection.pii_detector (increment 1).

All fixtures are fully synthetic: no real personal data, no evidence files,
no extracted source text, no production identifiers.  No raw matched values
appear in assertion messages.
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from cadence_detection.detection.pii_detector import (
    Block,
    DETECTOR_ID,
    Finding,
    _deduplicate,
    _resolve_overlaps,
    detect,
)


def _make_block(text: str, doc_id: str = "doc-001", blk_id: str = "blk-001") -> Block:
    return Block(document_id=doc_id, block_id=blk_id, text=text)


def _types(findings: list[Finding]) -> list[str]:
    return [f.entity_type for f in findings]


# 1. EMAIL – positive cases

class TestEmailPositive(unittest.TestCase):

    def test_simple_email(self):
        blk = _make_block("Contact synth.user@example.com for details.")
        findings = detect(blk)
        emails = [f for f in findings if f.entity_type == "EMAIL"]
        self.assertEqual(len(emails), 1)

    def test_email_start_of_text(self):
        blk = _make_block("synth@test.org is the address.")
        findings = detect(blk)
        emails = [f for f in findings if f.entity_type == "EMAIL"]
        self.assertEqual(len(emails), 1)
        self.assertEqual(emails[0].start, 0)

    def test_email_end_of_text(self):
        text = "Send to synth@test.org"
        blk = _make_block(text)
        findings = detect(blk)
        emails = [f for f in findings if f.entity_type == "EMAIL"]
        self.assertEqual(len(emails), 1)
        self.assertEqual(emails[0].end, len(text))

    def test_email_span_correct(self):
        text = "From: synth.user@example.com today"
        blk = _make_block(text)
        findings = detect(blk)
        emails = [f for f in findings if f.entity_type == "EMAIL"]
        self.assertEqual(len(emails), 1)
        f = emails[0]
        self.assertEqual(text[f.start:f.end], "synth.user@example.com")

    def test_email_with_plus_tag(self):
        blk = _make_block("synth+tag@example.co.uk is valid.")
        findings = detect(blk)
        emails = [f for f in findings if f.entity_type == "EMAIL"]
        self.assertEqual(len(emails), 1)

    def test_two_emails_in_text(self):
        blk = _make_block("a@example.com and b@example.org both appear.")
        findings = detect(blk)
        emails = [f for f in findings if f.entity_type == "EMAIL"]
        self.assertEqual(len(emails), 2)

    def test_confidence_range(self):
        blk = _make_block("x@example.com")
        findings = detect(blk)
        emails = [f for f in findings if f.entity_type == "EMAIL"]
        self.assertEqual(len(emails), 1)
        self.assertGreater(emails[0].confidence, 0.0)
        self.assertLessEqual(emails[0].confidence, 1.0)


# 2. EMAIL – negative cases

class TestEmailNegative(unittest.TestCase):

    def test_no_at_sign(self):
        blk = _make_block("userexample.com is not an email.")
        findings = detect(blk)
        emails = [f for f in findings if f.entity_type == "EMAIL"]
        self.assertEqual(len(emails), 0)

    def test_no_tld(self):
        blk = _make_block("user@nodot is not valid.")
        findings = detect(blk)
        emails = [f for f in findings if f.entity_type == "EMAIL"]
        self.assertEqual(len(emails), 0)

    def test_tld_too_short(self):
        blk = _make_block("user@example.c is not valid.")
        findings = detect(blk)
        emails = [f for f in findings if f.entity_type == "EMAIL"]
        self.assertEqual(len(emails), 0)

    def test_double_at(self):
        blk = _make_block("user@@example.com should not match.")
        findings = detect(blk)
        emails = [f for f in findings if f.entity_type == "EMAIL"]
        self.assertEqual(len(emails), 0)

    def test_empty_local_part(self):
        blk = _make_block("@example.com is not valid.")
        findings = detect(blk)
        emails = [f for f in findings if f.entity_type == "EMAIL"]
        self.assertEqual(len(emails), 0)


# 3. PHONE – contextual positive cases

class TestPhoneContextualPositive(unittest.TestCase):

    def test_tel_colon_prefix(self):
        blk = _make_block("Tel: +44 20 7946 0000")
        findings = detect(blk)
        phones = [f for f in findings if f.entity_type == "PHONE"]
        self.assertEqual(len(phones), 1)

    def test_phone_colon_prefix(self):
        blk = _make_block("Phone: 555-867-5309")
        findings = detect(blk)
        phones = [f for f in findings if f.entity_type == "PHONE"]
        self.assertEqual(len(phones), 1)

    def test_mobile_prefix(self):
        blk = _make_block("Mobile: 07700 900000")
        findings = detect(blk)
        phones = [f for f in findings if f.entity_type == "PHONE"]
        self.assertEqual(len(phones), 1)

    def test_fax_prefix(self):
        blk = _make_block("Fax: 01234 567890")
        findings = detect(blk)
        phones = [f for f in findings if f.entity_type == "PHONE"]
        self.assertEqual(len(phones), 1)

    def test_phone_span_excludes_keyword(self):
        """The span must cover the digit body only, not the keyword 'Tel:'."""
        text = "Tel: +44 20 7946 0000"
        blk = _make_block(text)
        findings = detect(blk)
        phones = [f for f in findings if f.entity_type == "PHONE"]
        self.assertEqual(len(phones), 1)
        f = phones[0]
        self.assertGreater(f.start, 0)
        matched = text[f.start:f.end]
        digit_count = sum(c.isdigit() for c in matched)
        self.assertGreaterEqual(digit_count, 7)

    def test_case_insensitive_keyword(self):
        blk = _make_block("MOBILE: 07700 900001")
        findings = detect(blk)
        phones = [f for f in findings if f.entity_type == "PHONE"]
        self.assertEqual(len(phones), 1)

    def test_phone_confidence_range(self):
        blk = _make_block("Tel: 0123456789")
        findings = detect(blk)
        phones = [f for f in findings if f.entity_type == "PHONE"]
        self.assertEqual(len(phones), 1)
        self.assertGreater(phones[0].confidence, 0.0)
        self.assertLessEqual(phones[0].confidence, 1.0)


# 4. PHONE – negative cases (no context keyword)

class TestPhoneNegative(unittest.TestCase):

    def test_bare_digits_no_keyword(self):
        """A bare digit string without a phone keyword must NOT match."""
        blk = _make_block("Order number 1234567890 processed.")
        findings = detect(blk)
        phones = [f for f in findings if f.entity_type == "PHONE"]
        self.assertEqual(len(phones), 0)

    def test_year_range_no_keyword(self):
        blk = _make_block("Period 2019-2024.")
        findings = detect(blk)
        phones = [f for f in findings if f.entity_type == "PHONE"]
        self.assertEqual(len(phones), 0)

    def test_isbn_no_keyword(self):
        blk = _make_block("ISBN 978-0-306-40615-7")
        findings = detect(blk)
        phones = [f for f in findings if f.entity_type == "PHONE"]
        self.assertEqual(len(phones), 0)

    def test_too_few_digits_with_keyword(self):
        """Keyword present but digit string too short (< 7 digits)."""
        blk = _make_block("Tel: 12345")
        findings = detect(blk)
        phones = [f for f in findings if f.entity_type == "PHONE"]
        self.assertEqual(len(phones), 0)


# 5. EMPLOYEE_ID – synthetic positive cases

class TestEmployeeIdPositive(unittest.TestCase):
    """Synthetic EMP-<digits> convention for test fixtures only."""

    def test_basic_emp_id(self):
        blk = _make_block("Record for EMP-12345 is complete.")
        findings = detect(blk)
        empids = [f for f in findings if f.entity_type == "EMPLOYEE_ID"]
        self.assertEqual(len(empids), 1)

    def test_emp_id_span_correct(self):
        text = "Review EMP-98765 before closing."
        blk = _make_block(text)
        findings = detect(blk)
        empids = [f for f in findings if f.entity_type == "EMPLOYEE_ID"]
        self.assertEqual(len(empids), 1)
        f = empids[0]
        self.assertEqual(text[f.start:f.end], "EMP-98765")

    def test_emp_id_min_digits(self):
        blk = _make_block("EMP-100 is the minimum.")
        findings = detect(blk)
        empids = [f for f in findings if f.entity_type == "EMPLOYEE_ID"]
        self.assertEqual(len(empids), 1)

    def test_emp_id_max_digits(self):
        blk = _make_block("EMP-12345678 is the maximum.")
        findings = detect(blk)
        empids = [f for f in findings if f.entity_type == "EMPLOYEE_ID"]
        self.assertEqual(len(empids), 1)

    def test_emp_id_at_start(self):
        blk = _make_block("EMP-00001 starts the line.")
        findings = detect(blk)
        empids = [f for f in findings if f.entity_type == "EMPLOYEE_ID"]
        self.assertEqual(len(empids), 1)
        self.assertEqual(empids[0].start, 0)


# 6. EMPLOYEE_ID – negative cases

class TestEmployeeIdNegative(unittest.TestCase):

    def test_no_prefix(self):
        blk = _make_block("12345 alone should not match employee id.")
        findings = detect(blk)
        empids = [f for f in findings if f.entity_type == "EMPLOYEE_ID"]
        self.assertEqual(len(empids), 0)

    def test_wrong_prefix(self):
        blk = _make_block("USR-12345 uses wrong prefix.")
        findings = detect(blk)
        empids = [f for f in findings if f.entity_type == "EMPLOYEE_ID"]
        self.assertEqual(len(empids), 0)

    def test_too_few_digits(self):
        blk = _make_block("EMP-12 has too few digits.")
        findings = detect(blk)
        empids = [f for f in findings if f.entity_type == "EMPLOYEE_ID"]
        self.assertEqual(len(empids), 0)

    def test_too_many_digits(self):
        blk = _make_block("EMP-123456789 has too many digits.")
        findings = detect(blk)
        empids = [f for f in findings if f.entity_type == "EMPLOYEE_ID"]
        self.assertEqual(len(empids), 0)

    def test_embedded_in_longer_token(self):
        """EMP-12345 embedded in a longer alphanumeric token must not match."""
        blk = _make_block("XEMP-12345Y is a larger token.")
        findings = detect(blk)
        empids = [f for f in findings if f.entity_type == "EMPLOYEE_ID"]
        self.assertEqual(len(empids), 0)

    def test_lowercase_prefix_no_match(self):
        """Pattern is case-sensitive; 'emp-12345' must not match."""
        blk = _make_block("emp-12345 is lowercase.")
        findings = detect(blk)
        empids = [f for f in findings if f.entity_type == "EMPLOYEE_ID"]
        self.assertEqual(len(empids), 0)


# 7. Unicode offsets

class TestUnicodeOffsets(unittest.TestCase):

    def test_email_after_multibyte_chars(self):
        """Offsets must be Python Unicode code-point positions, not byte offsets.

        The em-dash (U+2014) is a single code point but takes 3 bytes in UTF-8.
        prefix = 'café\u2014 ' has 6 code points: c, a, f, é, —, <space>.
        The email therefore starts at code-point index 6.
        """
        prefix = "café\u2014 "   # 6 code points: c, a, f, é, —, <space>
        email_part = "synth@example.com"
        text = prefix + email_part
        blk = _make_block(text)
        findings = detect(blk)
        emails = [f for f in findings if f.entity_type == "EMAIL"]
        self.assertEqual(len(emails), 1)
        f = emails[0]
        expected_start = len(prefix)  # Unicode code points in prefix
        self.assertEqual(f.start, expected_start)
        self.assertEqual(f.end, expected_start + len(email_part))
        # Round-trip check: indexing the original string must recover the email.
        self.assertEqual(text[f.start:f.end], email_part)

    def test_emp_id_after_cjk_chars(self):
        """CJK characters are single code points; offsets must remain correct."""
        prefix = "\u4e2d\u6587 "  # "中文 " – 3 code points
        text = prefix + "EMP-55555 here"
        blk = _make_block(text)
        findings = detect(blk)
        empids = [f for f in findings if f.entity_type == "EMPLOYEE_ID"]
        self.assertEqual(len(empids), 1)
        f = empids[0]
        self.assertEqual(f.start, len(prefix))
        self.assertEqual(text[f.start:f.end], "EMP-55555")

    def test_emoji_before_phone(self):
        """Emoji are single code points in Python 3 (UCS-4 build)."""
        prefix = "\U0001F4DE "  # 📞 TELEPHONE RECEIVER + space – 2 code points
        text = prefix + "Tel: 01234567890"
        blk = _make_block(text)
        findings = detect(blk)
        phones = [f for f in findings if f.entity_type == "PHONE"]
        self.assertEqual(len(phones), 1)
        f = phones[0]
        self.assertGreater(f.start, len(prefix))
        matched = text[f.start:f.end]
        digit_count = sum(c.isdigit() for c in matched)
        self.assertGreaterEqual(digit_count, 7)


# 8. Repeated findings (same entity appearing twice)

class TestRepeatedFindings(unittest.TestCase):

    def test_same_email_twice_returns_two_findings(self):
        """Two occurrences of the same address at different positions → 2 findings."""
        text = "synth@example.com and also synth@example.com again."
        blk = _make_block(text)
        findings = detect(blk)
        emails = [f for f in findings if f.entity_type == "EMAIL"]
        self.assertEqual(len(emails), 2)
        self.assertNotEqual(emails[0].start, emails[1].start)

    def test_exact_duplicate_collapsed(self):
        """Calling _deduplicate on two structurally identical findings keeps one."""
        f = Finding(
            document_id="d1",
            block_id="b1",
            entity_type="EMAIL",
            start=0,
            end=10,
            confidence=0.9,
            detector=DETECTOR_ID,
            source_location="b1:0:10",
        )
        result = _deduplicate([f, f])
        self.assertEqual(len(result), 1)

    def test_two_emp_ids_in_text(self):
        blk = _make_block("EMP-11111 and EMP-22222 are different records.")
        findings = detect(blk)
        empids = [f for f in findings if f.entity_type == "EMPLOYEE_ID"]
        self.assertEqual(len(empids), 2)


# 9. Overlap resolution

class TestOverlapResolution(unittest.TestCase):

    def _make_finding(self, start, end, entity_type="EMAIL", confidence=0.9) -> Finding:
        return Finding(
            document_id="d1",
            block_id="b1",
            entity_type=entity_type,
            start=start,
            end=end,
            confidence=confidence,
            detector=DETECTOR_ID,
            source_location=f"b1:{start}:{end}",
        )

    def test_non_overlapping_both_kept(self):
        f1 = self._make_finding(0, 5)
        f2 = self._make_finding(5, 10)
        result = _resolve_overlaps([f1, f2])
        self.assertEqual(len(result), 2)

    def test_overlapping_higher_confidence_wins(self):
        f_low = self._make_finding(0, 10, confidence=0.5)
        f_high = self._make_finding(5, 15, confidence=0.9)
        result = _resolve_overlaps([f_low, f_high])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].confidence, 0.9)

    def test_overlapping_equal_confidence_larger_span_wins(self):
        f_narrow = self._make_finding(0, 5, confidence=0.8)
        f_wide = self._make_finding(0, 10, confidence=0.8)
        result = _resolve_overlaps([f_narrow, f_wide])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].end - result[0].start, 10)

    def test_overlapping_equal_confidence_equal_span_lower_start_wins(self):
        f1 = self._make_finding(0, 10, confidence=0.8)
        f2 = self._make_finding(1, 11, confidence=0.8)
        result = _resolve_overlaps([f1, f2])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].start, 0)

    def test_touching_spans_not_overlapping(self):
        """Adjacent spans (one ends where next begins) do NOT overlap."""
        f1 = self._make_finding(0, 5)
        f2 = self._make_finding(5, 10)
        result = _resolve_overlaps([f1, f2])
        self.assertEqual(len(result), 2)

    def test_contained_span_drops_inner(self):
        """A span fully contained within another is considered overlapping."""
        f_outer = self._make_finding(0, 20, confidence=0.9)
        f_inner = self._make_finding(5, 15, confidence=0.7)
        result = _resolve_overlaps([f_outer, f_inner])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].start, 0)
        self.assertEqual(result[0].end, 20)

    def test_resolve_overlaps_output_in_document_order(self):
        """Accepted findings are returned sorted by (start, end, entity_type)."""
        f1 = self._make_finding(10, 20)
        f2 = self._make_finding(0, 5)
        result = _resolve_overlaps([f1, f2])
        self.assertEqual(len(result), 2)
        self.assertLess(result[0].start, result[1].start)


# 10. Source metadata correctness

class TestSourceMetadata(unittest.TestCase):

    def test_document_id_forwarded(self):
        blk = Block(document_id="DOC-XYZ", block_id="BLK-001", text="synth@example.com")
        findings = detect(blk)
        self.assertTrue(all(f.document_id == "DOC-XYZ" for f in findings))

    def test_block_id_forwarded(self):
        blk = Block(document_id="DOC-XYZ", block_id="BLK-999", text="synth@example.com")
        findings = detect(blk)
        self.assertTrue(all(f.block_id == "BLK-999" for f in findings))

    def test_detector_id_correct(self):
        blk = Block(document_id="d", block_id="b", text="synth@example.com")
        findings = detect(blk)
        self.assertTrue(all(f.detector == DETECTOR_ID for f in findings))

    def test_source_location_present_and_non_empty(self):
        blk = Block(document_id="d", block_id="b", text="synth@example.com")
        findings = detect(blk)
        for f in findings:
            self.assertTrue(f.source_location, "source_location must be non-empty")

    def test_source_location_encodes_span(self):
        """Provisional source_location format: '<block_id>:<start>:<end>'."""
        blk = Block(document_id="d", block_id="myblock", text="synth@example.com")
        findings = detect(blk)
        self.assertEqual(len(findings), 1)
        f = findings[0]
        expected = f"myblock:{f.start}:{f.end}"
        self.assertEqual(f.source_location, expected)


# 11. Edge cases: empty / whitespace input

class TestEdgeCases(unittest.TestCase):

    def test_empty_text(self):
        blk = _make_block("")
        findings = detect(blk)
        self.assertEqual(findings, [])

    def test_whitespace_only(self):
        blk = _make_block("     \t\n  ")
        findings = detect(blk)
        self.assertEqual(findings, [])

    def test_no_pii_text(self):
        blk = _make_block("The quick brown fox jumps over the lazy dog.")
        findings = detect(blk)
        self.assertEqual(findings, [])

    def test_mixed_entities_no_false_positives(self):
        """A text with one of each well-formed type and assorted noise."""
        text = (
            "Order 9999999999 placed. "
            "Please email synth@example.com or call Tel: 01234567890. "
            "Record EMP-54321 filed. "
            "Reference number 1234-5678-9012 is not a phone."
        )
        blk = _make_block(text)
        findings = detect(blk)
        emails = [f for f in findings if f.entity_type == "EMAIL"]
        phones = [f for f in findings if f.entity_type == "PHONE"]
        empids = [f for f in findings if f.entity_type == "EMPLOYEE_ID"]
        self.assertEqual(len(emails), 1)
        self.assertEqual(len(phones), 1)
        self.assertEqual(len(empids), 1)



# 12. Phone – M-label (abbreviated mobile keyword) — G1

class TestPhoneMAbbreviation(unittest.TestCase):
    """Single-letter 'M' mobile label; uppercase only (see PHONE/FP-2)."""

    def test_M_space_e164_matches(self):
        """'M +1 (555) 0114' – the canonical form from the review spec."""
        blk = _make_block("M +1 (555) 0114")
        phones = [f for f in detect(blk) if f.entity_type == "PHONE"]
        self.assertEqual(len(phones), 1)

    def test_M_colon_matches(self):
        """'M: +1 (555) 0114' with a colon separator."""
        blk = _make_block("M: +1 (555) 0114")
        phones = [f for f in detect(blk) if f.entity_type == "PHONE"]
        self.assertEqual(len(phones), 1)

    def test_M_span_excludes_label(self):
        """Span must NOT include the 'M' label – only the number body."""
        text = "M +1 (555) 0114"
        blk = _make_block(text)
        phones = [f for f in detect(blk) if f.entity_type == "PHONE"]
        self.assertEqual(len(phones), 1)
        f = phones[0]
        self.assertGreater(f.start, 0)
        sliced = text[f.start:f.end]
        digit_count = sum(c.isdigit() for c in sliced)
        self.assertGreaterEqual(digit_count, 7)

    def test_M_span_round_trip(self):
        text = "M +1 (555) 0114"
        blk = _make_block(text)
        phones = [f for f in detect(blk) if f.entity_type == "PHONE"]
        self.assertEqual(len(phones), 1)
        f = phones[0]
        self.assertEqual(text[f.start:f.end], "+1 (555) 0114")

    def test_lowercase_m_no_match(self):
        """Lowercase 'm' must NOT match (avoids SI prefix / unit false positives)."""
        blk = _make_block("m: +1 (555) 0114")
        phones = [f for f in detect(blk) if f.entity_type == "PHONE"]
        self.assertEqual(len(phones), 0)

    def test_M_mid_word_no_match(self):
        """'M' embedded inside a longer word must not trigger the M keyword."""
        blk = _make_block("AMOUNT +1 (555) 0114")
        phones = [f for f in detect(blk) if f.entity_type == "PHONE"]
        self.assertEqual(len(phones), 0)

    def test_M_preceded_by_letter_no_match(self):
        """'aM' must not trigger the M keyword."""
        blk = _make_block("aM: +1 (555) 0114")
        phones = [f for f in detect(blk) if f.entity_type == "PHONE"]
        self.assertEqual(len(phones), 0)


# 13. Phone – complete span with parentheses and plus-sign — G2, G3

class TestPhoneCompleteSpan(unittest.TestCase):
    """Verify phone span includes +, parens, and spaces, and excludes the keyword."""

    def test_span_includes_plus_sign(self):
        """Leading '+' of an international number must be inside the span."""
        text = "Tel: +44 20 7946 0000"
        blk = _make_block(text)
        phones = [f for f in detect(blk) if f.entity_type == "PHONE"]
        self.assertEqual(len(phones), 1)
        self.assertTrue(
            text[phones[0].start:phones[0].end].startswith("+"),
            "Span should start with '+' for an international number",
        )

    def test_span_round_trip_plus(self):
        text = "Tel: +44 20 7946 0000"
        blk = _make_block(text)
        phones = [f for f in detect(blk) if f.entity_type == "PHONE"]
        self.assertEqual(len(phones), 1)
        f = phones[0]
        self.assertEqual(text[f.start:f.end], "+44 20 7946 0000")

    def test_span_includes_leading_parens(self):
        """Format '(555) 867-5309' – leading '(' must be inside the span."""
        text = "Phone: (555) 867-5309"
        blk = _make_block(text)
        phones = [f for f in detect(blk) if f.entity_type == "PHONE"]
        self.assertEqual(len(phones), 1)
        self.assertTrue(
            text[phones[0].start:phones[0].end].startswith("("),
            "Span should start with '(' when the number begins with area code parens",
        )

    def test_span_round_trip_parens(self):
        text = "Phone: (555) 867-5309"
        blk = _make_block(text)
        phones = [f for f in detect(blk) if f.entity_type == "PHONE"]
        self.assertEqual(len(phones), 1)
        f = phones[0]
        self.assertEqual(text[f.start:f.end], "(555) 867-5309")

    def test_span_parens_in_middle(self):
        """Parentheses around an area code in the middle: '+44 (20) 7946 0000'."""
        text = "Tel: +44 (20) 7946 0000"
        blk = _make_block(text)
        phones = [f for f in detect(blk) if f.entity_type == "PHONE"]
        self.assertEqual(len(phones), 1)
        f = phones[0]
        self.assertEqual(text[f.start:f.end], "+44 (20) 7946 0000")

    def test_M_label_complete_span(self):
        """M-label form: span covers the full number including +."""
        text = "M +1 (555) 0114"
        blk = _make_block(text)
        phones = [f for f in detect(blk) if f.entity_type == "PHONE"]
        self.assertEqual(len(phones), 1)
        f = phones[0]
        digit_count = sum(c.isdigit() for c in text[f.start:f.end])
        self.assertGreaterEqual(digit_count, 7)

    def test_keyword_not_in_span_slice(self):
        """Verify the keyword ('Phone') does not appear in the span slice."""
        text = "Phone: (555) 867-5309"
        blk = _make_block(text)
        phones = [f for f in detect(blk) if f.entity_type == "PHONE"]
        self.assertEqual(len(phones), 1)
        sliced = text[phones[0].start:phones[0].end]
        self.assertNotIn("Phone", sliced)


# 14. Phone – false-positive regressions — G4, G5

class TestPhoneFalsePositiveRegressions(unittest.TestCase):
    """Verify numeric strings without phone keywords do not produce PHONE findings."""

    def test_currency_amount_no_match(self):
        blk = _make_block("Invoice total GBP 1234567.00")
        phones = [f for f in detect(blk) if f.entity_type == "PHONE"]
        self.assertEqual(len(phones), 0)

    def test_iso_date_no_keyword_no_match(self):
        blk = _make_block("Effective date 2024-01-15 applies.")
        phones = [f for f in detect(blk) if f.entity_type == "PHONE"]
        self.assertEqual(len(phones), 0)

    def test_policy_control_id_no_match(self):
        blk = _make_block("See control CTRL-12345 for details.")
        self.assertEqual(detect(blk), [])

    def test_version_string_no_match(self):
        blk = _make_block("Version v1.2.3.456 released.")
        self.assertEqual(detect(blk), [])

    def test_reference_number_no_match(self):
        blk = _make_block("Policy REF-20241001 amended.")
        self.assertEqual(detect(blk), [])

    def test_domain_only_no_email_match(self):
        blk = _make_block("Visit example.com for information.")
        emails = [f for f in detect(blk) if f.entity_type == "EMAIL"]
        self.assertEqual(len(emails), 0)

    def test_phone_keyword_with_date_known_fp1_limitation(self):
        """PHONE/FP-1 limitation: keyword + date currently matches; see module docstring."""
        blk = _make_block("Tel: 2024-01-01")
        phones = [f for f in detect(blk) if f.entity_type == "PHONE"]
        self.assertEqual(
            len(phones),
            1,
            "PHONE/FP-1 known limitation: date-like strings with phone keyword "
            "currently produce a finding.  See module docstring for details.",
        )


# 15. Employee-ID – end-of-string and boundary — G6

class TestEmployeeIdBoundary(unittest.TestCase):

    def test_emp_id_at_end_of_string(self):
        """EMP-12345 at the very end of the string with no trailing chars."""
        text = "Record EMP-12345"
        blk = _make_block(text)
        empids = [f for f in detect(blk) if f.entity_type == "EMPLOYEE_ID"]
        self.assertEqual(len(empids), 1)
        f = empids[0]
        self.assertEqual(text[f.start:f.end], "EMP-12345")
        self.assertEqual(f.end, len(text))

    def test_emp_id_only_text(self):
        """Block text is exactly the EMP-ID token with nothing else."""
        text = "EMP-77777"
        blk = _make_block(text)
        empids = [f for f in detect(blk) if f.entity_type == "EMPLOYEE_ID"]
        self.assertEqual(len(empids), 1)
        self.assertEqual(empids[0].start, 0)
        self.assertEqual(empids[0].end, len(text))

    def test_emp_id_followed_by_punctuation(self):
        """EMP-12345 followed immediately by comma should still match."""
        text = "See EMP-12345, for review."
        blk = _make_block(text)
        empids = [f for f in detect(blk) if f.entity_type == "EMPLOYEE_ID"]
        self.assertEqual(len(empids), 1)
        f = empids[0]
        self.assertEqual(text[f.start:f.end], "EMP-12345")


# 16. Unicode offsets – extended coverage for new phone formats

class TestUnicodeOffsetsExtended(unittest.TestCase):

    def test_M_label_after_cjk(self):
        """M-label phone after CJK characters: offsets must be code-point-correct."""
        prefix = "\u4e2d\u6587\uff1a"  # "中文：" – 3 code points
        text = prefix + "M +1 (555) 0114"
        blk = _make_block(text)
        phones = [f for f in detect(blk) if f.entity_type == "PHONE"]
        self.assertEqual(len(phones), 1)
        f = phones[0]
        self.assertGreater(f.start, len(prefix))
        sliced = text[f.start:f.end]
        digit_count = sum(c.isdigit() for c in sliced)
        self.assertGreaterEqual(digit_count, 7)

    def test_phone_parens_after_emoji(self):
        """Parenthesised number after emoji: span must be code-point-correct."""
        prefix = "\U0001F4F1 "  # 📱 MOBILE PHONE + space – 2 code points
        text = prefix + "Phone: (555) 867-5309"
        blk = _make_block(text)
        phones = [f for f in detect(blk) if f.entity_type == "PHONE"]
        self.assertEqual(len(phones), 1)
        f = phones[0]
        self.assertGreater(f.start, len(prefix))
        self.assertEqual(text[f.start:f.end], "(555) 867-5309")


if __name__ == "__main__":
    unittest.main()
