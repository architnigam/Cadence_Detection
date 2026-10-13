# Person 5 handoff: independent evaluation and QA

## Implemented

- Standard-library evaluator and CLI for exact occurrence/type precision, recall, F1, TP/FP/FN and denominators. Repeated occurrences count separately and duplicate predictions count as false positives.
- Breakdowns by document, format, entity category, source kind and native/image-only text. A separate maximum one-to-one IoU match diagnoses imperfect boundaries. Photograph/signature boxes use a separate visual metric.
- Five-dimension structure/context rubric, explicit N/A handling and separate text/OCR accuracy counts.
- Independent known-gold residual checks and audits of claimed release states. Missing/blank output, incomplete extraction, failed verification or surviving gold values invalidate a claimed approval. This audits Person 4's gate and does not replace it.
- Synthetic evidence covering all 16 proposed entity types, negative business context, deliberately imperfect predictions and a deliberately leaked passport. These are evaluator demonstrations, not measured detector results.
- Local source annotation preparation, review queue, independently reviewed starter labels and manual policy transcriptions. Real labels remain provisional until team adjudication.
- Twelve generated black-box pipeline inputs with an integration adapter contract. Full-pipeline execution remains pending because Persons 1–4's pipeline is absent.

No detector, OCR adapter, redactor or upload UI is implemented by this handoff. Those remain the other owners' responsibilities. Presentation work is deferred at the user's request.

## Run from Cadence_Detection

Use Python 3.10 or newer. Evaluation and tests require no third-party libraries.

```powershell
python -m unittest discover -s tests/integration -p "test_*.py" -v
python scripts/build_qa_fixture.py
python scripts/evaluate.py data/synthetic/evaluation_fixture.json --output output/reports/synthetic_example
```

The synthetic example intentionally has imperfect recall and an unsafe PDF approval. Add `--fail-on-unsafe-approval` for regression use. Exit codes: 0 = report written, 1 = unsafe approval when requested, 2 = invalid evidence/read/write error. Exit 0 does not certify a document safe.

This workstation's bundled Python is available at:

```powershell
& 'C:\Users\Priyanshi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -m unittest discover -s tests/integration -p 'test_*.py' -v
```

To prepare source annotation aids and valid file fixtures, use the optional `python-docx`, `python-pptx`, `pypdf` and `reportlab` dependencies from the existing planned dependency list/bundled runtime.

```powershell
python scripts/prepare_source_annotations.py --catalogue data/annotations/local_source_catalogue.json
python scripts/build_pipeline_inputs.py
python scripts/run_pipeline_checks.py
```

Without `--runner`, pipeline checks deliberately return `not_run` and exit 1. Once Person 1 exposes a local adapter, run:

```powershell
python scripts/run_pipeline_checks.py --runner cadence_detection.integration_adapter:run_for_qa
```

The adapter module name is an interface example, not an implemented module. Replace it with the actual team adapter. It receives a Path and returns `status`, `sanitized_blocks`, `extraction_complete`, `verification_passed`, `remaining_candidate_count` and `downstream_called`. Replace the external LLM with a local spy. Reuse actual ingestion, extraction, detection and redaction code, so these checks exercise the integrated pipeline.

## Teammate handoffs

| Owner | Needed by Person 5 | Acceptance evidence |
|---|---|---|
| Person 1 | Document IDs, local runner and integrated result bundle | All three formats, all 12 file cases, consistent failure states |
| Person 2 | Frozen normalized blocks and unit coverage | All 35 policy pages, 9 slides, 16 DOCX tables and 41 media entries accounted for |
| Person 3 | Findings on the exact frozen block text | Valid Unicode offsets, type, block ID and confidences, no raw values in reports |
| Person 4 | Sanitized blocks and gate evidence | Local spy proves failed/quarantined inputs never cross the downstream boundary |
| All four | Independent annotation review and adjudication | Every selected block reviewed, including negatives, unresolved cases recorded |

## Remaining work and definition of completion

1. Agree stable block IDs with Person 1. Current reference IDs are annotation aids and require explicit mapping to Person 2's outputs.
2. Freeze development/held-out units before detector tuning. The starter reserves the policy as held out and treats PPTX/DOCX as development. Do not tune on held-out labels. If the team needs policy development examples, change and record the split before tuning.
3. Complete source gold review, including OCR screenshot text and visual regions. All starter annotations need second review. No complete gold set or real accuracy result is claimed.
4. Replace empty source predictions/results with actual pipeline outputs. Keep text hashes to prevent silently scoring offsets against changed text.
5. Run the integrated file checks plus the manual/injected scenarios in `qa_test_plan.md`. Resolve release blockers.
6. Have Person 2 and Person 5 review the structure rubric with source evidence, then report each document separately. An average must not hide a document below 80%.
7. Record real evaluation and remaining defects. Assemble slides only when the user resumes that work.

Supporting guides: [annotation guide](../../data/annotations/annotation_guide.md), [evaluation contract](evaluation_contract.md), [QA test plan](qa_test_plan.md), [defect/dependency register](defect_tracker.csv), [demo fallback runbook](demo_fallback.md).
