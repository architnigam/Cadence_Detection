# Independent evaluation report

Dataset: **synthetic**. Split: **held_out**. Status: **evaluated**.

These results evaluate the supplied predictions. Synthetic predictions exercise the evaluator, not a working detector.

Evaluated blocks: 6. Negative blocks: 1. Excluded provisional blocks: 0.

## Exact occurrence and type metrics

| Group | TP | FP | FN | Gold | Predictions | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Overall | 16 | 3 | 2 | 18 | 19 | 84.21% | 88.89% | 86.49% |

## Per format

| Group | TP | FP | FN | Gold | Predictions | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| docx | 2 | 1 | 0 | 2 | 3 | 66.67% | 100.00% | 80.00% |
| pdf | 10 | 0 | 1 | 11 | 10 | 100.00% | 90.91% | 95.24% |
| pptx | 4 | 2 | 1 | 5 | 6 | 66.67% | 80.00% | 72.73% |

## Per category

| Group | TP | FP | FN | Gold | Predictions | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| BANK_ACCOUNT | 1 | 0 | 0 | 1 | 1 | 100.00% | 100.00% | 100.00% |
| DATE_OF_BIRTH | 1 | 0 | 0 | 1 | 1 | 100.00% | 100.00% | 100.00% |
| DIRECTOR_ID | 1 | 0 | 0 | 1 | 1 | 100.00% | 100.00% | 100.00% |
| EMAIL | 2 | 1 | 0 | 2 | 3 | 66.67% | 100.00% | 80.00% |
| EMPLOYEE_ID | 1 | 0 | 0 | 1 | 1 | 100.00% | 100.00% | 100.00% |
| HOME_ADDRESS | 1 | 0 | 0 | 1 | 1 | 100.00% | 100.00% | 100.00% |
| NATIONAL_ID | 1 | 0 | 0 | 1 | 1 | 100.00% | 100.00% | 100.00% |
| PARTIAL_IDENTIFIER | 1 | 0 | 0 | 1 | 1 | 100.00% | 100.00% | 100.00% |
| PASSPORT | 0 | 0 | 1 | 1 | 0 | N/A | 0.00% | 0.00% |
| PAYMENT_CARD | 1 | 0 | 0 | 1 | 1 | 100.00% | 100.00% | 100.00% |
| PERSON | 3 | 2 | 1 | 4 | 5 | 60.00% | 75.00% | 66.67% |
| PHONE | 1 | 0 | 0 | 1 | 1 | 100.00% | 100.00% | 100.00% |
| TAX_ID | 1 | 0 | 0 | 1 | 1 | 100.00% | 100.00% | 100.00% |
| VENDOR_PERSON_ID | 1 | 0 | 0 | 1 | 1 | 100.00% | 100.00% | 100.00% |

## Text origin

| Group | TP | FP | FN | Gold | Predictions | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| image_only | 10 | 0 | 1 | 11 | 10 | 100.00% | 90.91% | 95.24% |
| native_text | 6 | 3 | 1 | 7 | 9 | 66.67% | 85.71% | 75.00% |

## Per document

| Group | TP | FP | FN | Gold | Predictions | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| syn_docx | 2 | 1 | 0 | 2 | 3 | 66.67% | 100.00% | 80.00% |
| syn_pdf | 10 | 0 | 1 | 11 | 10 | 100.00% | 90.91% | 95.24% |
| syn_pptx | 4 | 2 | 1 | 5 | 6 | 66.67% | 80.00% | 72.73% |

## Source kind

| Group | TP | FP | FN | Gold | Predictions | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| body | 0 | 1 | 0 | 0 | 1 | 0.00% | N/A | 0.00% |
| narrative | 10 | 0 | 1 | 11 | 10 | 100.00% | 90.91% | 95.24% |
| table | 6 | 2 | 1 | 7 | 8 | 75.00% | 85.71% | 80.00% |

## Text overlap diagnostic

IoU threshold 0.5. TP 17, FP 2, FN 1. Recall 94.44%.

## Visual region detection

IoU threshold 0.5. TP 1, FP 0, FN 1. Recall 50.00%.

## Structure and context

Equal weights across applicable dimensions. Target: at least 80% per document. Text accuracy remains separate.

| Document | Status | Structure | Meets target | Text accuracy |
|---|---|---:|---|---:|
| syn_docx | reviewed | 90.00% | True | 90.00% |
| syn_pdf | reviewed | 90.00% | True | 90.00% |
| syn_pptx | reviewed | 90.00% | True | 90.00% |

## Extraction coverage

| Document | Complete / expected units | Complete extraction |
|---|---:|---|
| syn_docx | 1 / 1 | True |
| syn_pdf | 1 / 1 | True |
| syn_pptx | 1 / 1 | True |

## Independent release audit

| Document | Claimed status | Known residuals | Unsafe approval |
|---|---|---:|---|
| syn_docx | approved | 0 | False |
| syn_pdf | approved | 1 | True |
| syn_pptx | approved | 0 | False |

## Exact error locations

Values remain in the local annotation bundle. Offsets refer to original frozen block text.

| Error | Document | Block | Type | Start | End | Count |
|---|---|---|---|---:|---:|---:|
| false_negatives | syn_pdf | narrative | PASSPORT | 225 | 234 | 1 |
| false_negatives | syn_pptx | contacts | PERSON | 0 | 11 | 1 |
| false_positives | syn_docx | negative | PERSON | 0 | 8 | 1 |
| false_positives | syn_pptx | contacts | EMAIL | 32 | 51 | 1 |
| false_positives | syn_pptx | contacts | PERSON | 0 | 10 | 1 |

## Limitations

- Exact metrics cover selected labeled blocks, including reviewed negatives.
- Overlap matches are diagnostic and do not raise exact recall.
- Visual regions have separate bbox metrics and no text offsets.
- Zero known residuals does not guarantee future documents contain no PII.
- Source sample and synthetic results do not establish full-source accuracy.
