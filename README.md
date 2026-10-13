# Cadence Detection - integrated local application

The merged project now has a real PDF/PPTX/DOCX upload and command-line pipeline: validation -> extraction/OCR -> local PII detection -> redaction -> rescan -> checked export or quarantine.

## Quick start on this workstation

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_local.ps1 app
```

Open http://127.0.0.1:8765 and upload an actual source file. The interface shows real stage progress, categories, source locations, masked previews and review warnings. Only approved jobs can export text. The original text is available only through an explicit restricted local inspection action.

```powershell
# Real CLI processing; code 2 means review is required for at least one input.
python scripts/run_project.py data/source/Cadence_Financial_Group_Organizational_Pack.pptx
# Full regression suite, including live HTTP upload/download checks.
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_local.ps1 tests
# All 12 real black-box acceptance cases.
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_local.ps1 acceptance
```

The PowerShell helper selects the bundled Python if available. Standard Python commands require the declared dependencies and local models. Run from the repository checkout.

## Setup on another machine

```powershell
python -m pip install -e ".[nlp,test]"
python -m spacy download en_core_web_sm
```

Provision a local Tesseract executable with English language data, or configure the Node Tesseract backend as described in [the extraction guide](docs/person2_extraction.md). The supported English NER model is `en_core_web_sm` 3.8.0 with spaCy 3.8.x. Model installation is an explicit setup action; runtime uploads do not download models or send documents outside the machine. SVG conversion additionally needs CairoSVG or configured local Sharp. Windows metafile conversion uses Pillow/GDI; unsupported conversions block release.

`python scripts/run_app.py --port 8765` launches the dependency-light local UI. Streamlit is no longer required. The legacy `app/app.py` entry point launches the same real application.

## Team ownership and beginner guide

| Person | Work | Main paths |
|---|---|---|
| 1 | Architecture, validation, contracts, orchestration | src/cadence_detection/ingestion/, docs/design/ |
| 2 | PDF/DOCX/PPTX extraction, OCR, media conversion and source mapping | src/cadence_detection/extraction/, tests/extraction/ |
| 3 | Rules, local NER, classification and aliases | src/cadence_detection/detection/ |
| 4 | Safe span replacement, verification, real upload UI and export control | src/cadence_detection/redaction/, web.py, app/ |
| 5 | Independent annotation, metrics, acceptance checks and submission evidence | src/cadence_detection/evaluation/, tests/integration/ |

The final integration adds real adapters in `runtime.py`, fixes model/offset incompatibilities, unions crossing spans, rejects invalid findings, removes fixture-only UI behavior and tests the release boundary. The earlier baseline detector and stubs remain for historical component/fail-closed tests; the supported CLI/UI use the real runtime.

- Beginner document: [project and team guide](output/documents/Cadence_Project_and_Team_Guide_Final.docx).
- Editable stakeholder deck: [case-study presentation](presentation/Cadence_Case_Study_Solution.pptx).
- Detailed original allocation: [team plan](docs/team/work_allocation.md).

## Verification evidence and scope

The integrated suite has 288 passing tests with no failures, errors or skips in the configured workstation run. All 12 generated supported/error file acceptance cases pass. The supplied synthetic text benchmark has 18/18 exact occurrence/type matches with zero false positives. These are bounded test results, not universal recognition guarantees. See `output/reports/final_tests.json`, `final_acceptance.json` and `final_source_runs/` for local evidence.

Real source files are processed through all stages. The organizational pack can pass configured export checks. The scanned policy and training document retain legitimate OCR/review blockers. Quarantine means the software is enforcing the review boundary; it must not be bypassed to obtain a green status.

The >=80% real-source structure score and near-100% real-source PII coverage still require independently adjudicated source labels and manual structure comparison. Existing evaluator demonstrations are deliberately synthetic and must not be reported as real-source accuracy. Scanned table semantic reconstruction and visual photograph/signature classification are review limitations. The output is plain text: original file layers, photos and signatures are not exported.

## Privacy and operation

- Loopback-only HTTP server; no external fonts, images, analytics or LLM calls.
- Session token plus host/origin checks protect upload and review endpoints.
- Two processing workers; at most eight retained local jobs. Completed jobs older than 20 minutes are pruned on the next upload; restart clears session memory.
- Quarantined jobs have no releasable public text and download returns HTTP 403.
- Raw text, source evidence, caches, mappings and temporary files remain local and ignored by Git. Released JSON excludes reversible mappings and OCR word values.
- Missing OCR/NER, invalid spans, incomplete extraction and residual candidates block release.
- This is a local learning/demo application. Internet deployment needs additional authentication, storage isolation, TLS and operational controls.

No program can establish perfect recognition for all possible future documents using this finite test suite. Keep the scope, confidence and independent review evidence visible in the stakeholder walkthrough.
