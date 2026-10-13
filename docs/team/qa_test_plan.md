# Person 5 QA test plan

## Automated evaluation checks

Run `python -m unittest discover -s tests/integration -p "test_*.py" -v`. Tests verify metric arithmetic, duplicate/wrong-type/partial/Unicode offsets, split isolation, zero-denominator behavior, provisional exclusion, visual boxes, structure N/A and missing evidence, residual leakage and release-state auditing. These are evaluator/contract tests. They do not prove that the unavailable integrated pipeline passed.

## Generated black-box cases

`scripts/build_pipeline_inputs.py` generates native-text PDF/PPTX/DOCX, empty/corrupt variants for all formats, unsupported TXT, a DOCX disguised as PDF and a password-protected PDF. `scripts/run_pipeline_checks.py --runner module:function` invokes the real local integration adapter. It requires controlled failure/quarantine, downstream spy evidence and safe nonempty approved output.

## Source integration and injected failures

| ID | Setup | Expected evidence | Owner dependency |
|---|---|---|---|
| SRC-01 | Upload supplied scanned policy | 35/35 pages accounted for, including small screenshot content | Person 2 |
| SRC-02 | Upload organizational deck | 9/9 slides, tables/grouped shapes and notes accounted for | Person 2 |
| SRC-03 | Upload training | 16 tables and 41 media entries enumerated, SVG/EMF conversion/errors explicit | Person 2 |
| OCR-01 | Inject OCR exception/low confidence on one page | Incomplete source unit, quarantine, downstream spy not called | Persons 1, 2, 4 |
| OCR-02 | Rotation/degraded scan and small screenshot crop | Correct location mapping, visible uncertainty, no silent dropped region | Person 2 |
| PII-01 | RACI initials, short synthetic phone, international/hyphenated name | Every known occurrence/type evaluated, no strict phone validator silently rejecting sample | Person 3 |
| PII-02 | Policy p22 narrative and p23 correspondence | IDs, birth date, home address and partial identifiers covered | Person 3 |
| NEG-01 | Product/organization names, control IDs, generic dates, SLA durations, money | No PII findings on adjudicated negative occurrences | Person 3 |
| RED-01 | Overlapping detections and repeated person/email | Deterministic span resolution, consistent typed replacements, retained context | Person 4 |
| RED-02 | Detector intentionally misses one known passport | Independent residual audit finds leak. No release based only on the same detector's rescan | Persons 3, 4 |
| RED-03 | Candidate remains after rescan | Quarantine and downstream spy not called | Person 4 |
| GATE-01 | Output missing one source block, blank output or incomplete OCR | Release blocked, missing location listed | Persons 1, 4 |
| FAIL-01 | Missing/corrupt/empty/unsupported/encrypted/oversized upload | Controlled failure, no raw stack/PII log, no downstream call | Persons 1, 4 |
| STRUCT-01 | Table cell swapping/paragraph merger/context loss | Relevant rubric checks fail even if OCR characters are correct | Persons 2, 5 |
| PRIV-01 | Inspect temporary files/logs/report/downloads | Raw values and identity mappings stay local, safe outputs do not contain recoverable originals | Person 4 |
| ORIGINAL-01 | Any claim of sanitized original PDF/PPTX/DOCX export | Verify text/image/metadata/comment removal, not a visual overlay | Person 4, only if implemented |

Oversized-file limits must come from Person 1's configured ingestion limits. OCR injections require the actual adapter's test seam. They are planned scenarios, not yet executed results. Sanitized text and sanitized original files are different scopes.

## Completion evidence

Every mandatory brief outcome maps to evidence in the README. For reliability, retain selected gold version, reviewed negative blocks, split policy, source-unit denominators, exact category/format metrics, independently checked residuals, per-document structure scores, unresolved cases and open blockers. Never claim universal 100% detection from fixture results.
