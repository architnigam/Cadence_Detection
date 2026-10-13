# Person 5 readiness report

Prepared 13 October 2026. Scope: independent evaluation, QA and team handoff. Presentation work is deferred.

| Deliverable | Actual status | Evidence |
|---|---|---|
| Evaluation engine and CLI | Implemented | `src/cadence_detection/evaluation/engine.py`, `scripts/evaluate.py` |
| Exact and overlap metrics | Implemented, synthetic arithmetic verified | TP/FP/FN, per-type/format/origin/document and source-mapped error locations |
| Structure/context rubric | Defined and implemented | Five equal dimensions, explicit N/A, denominators, independent text accuracy |
| Residual/release audit | Implemented | Tests catch surviving passport, blank/missing outputs, incomplete extraction and failed verification |
| Regression checks | 36 passed | `python -m unittest discover -s tests/integration -p "test_*.py" -v` |
| Source annotation starter | Provisional, partial | 1,652 reference blocks, 178 source-catalogue/manual-transcription occurrences, 417 first-reviewed blocks, zero team-adjudicated blocks |
| Source review inventory | Prepared | 35 PDF pages, 9 slides, 16 DOCX tables, 41 media entries and five remaining DOCX content checks = 106 review units |
| Pipeline file checks | Inputs/runner contract ready, 12 not run | Three valid formats, empty/corrupt cases, unsupported, spoofed and encrypted files |
| Real-document detector accuracy | Not measured | Extraction/detector/redactor/integration dependencies absent |
| Per-document 80% structure target | Not measured on supplied sources | Person 2 and Person 5 must score source checks after extraction |
| Complete gold set | Pending | All source units need completeness review and second reviewer adjudication |

The starter labels the native organizational text, selected DOCX user names, and visually transcribed policy p22 section 16.5 and p23 section 16.8. It does not establish complete scanned policy or DOCX embedded-image coverage. One provisional label is in a still-pending DOCX block, so even exploratory scoring excludes it until the full block is reviewed. Default evaluation excludes all non-adjudicated labels.

The synthetic report's 18 text gold occurrences, 19 predictions, 16 TP, 3 FP and 2 FN are intentional QA fixture outcomes. They are not measurements of the team's detector. Its unsafe PDF approval is also intentional and tests whether independent residual checking catches the surviving passport.

For submission, use `docs/team/person5_handoff.md` as the implementation guide, `evaluation_contract.md` for teammate inputs, `qa_test_plan.md` for integration coverage and `defect_tracker.csv` for remaining dependencies. The existing overall project is still incomplete until Persons 1–4 supply their components and the team adjudicates the gold labels.
