# Person 2 validation record

Date: 13 October 2026.

## Automated tests

83 tests passed, 0 failures/errors/skips, including the opt-in real local OCR, SVG conversion and five supplied EMF conversion checks. Synthetic tests cover supported adapters and explicit failure paths; the exact list is in `tests/extraction/README.md`.

Command: `python -m unittest discover -s tests/extraction` with local OCR environment configured and `CADENCE_TEST_REAL_OCR=1`. Workspace TEMP/TMP was used.

`python -m compileall -q src` and `git diff --check` passed.

## Runtime used

- pypdf: 6.10.0
- pypdfium2: 5.13.0
- Pillow: 12.3.0
- lxml: 6.1.1
- python-docx: 1.2.0
- python-pptx: 1.0.2
- reportlab: 4.4.9
- tesseract.js: 7.0.0
- sharp: 0.35.5

English model SHA256: `7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2`.

## Supplied-document evidence

All three sources were processed locally. See `output/reports/person2_extraction_coverage.md` for the final counts and warning categories. The organization pack has 9 slides; the policy has 35 scanned pages; DOCX units are document parts rather than rendered pages. The risk policy was also run with the configured screenshot crops.

OCR text is not ground truth. Remaining low-confidence/non-text-image issues must be reviewed. No PII recall, secure redaction, or measured >=80% structure claim is made by this extraction implementation.
