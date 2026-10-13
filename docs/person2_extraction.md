# Person 2 implementation and handoff guide

## Scope

`src/cadence_detection/extraction/` implements extraction independently of the UI and PII detector. It validates files/packages, routes PDF/DOCX/PPTX, preserves source context and locations, runs local OCR, and reports incomplete content. Person 1 can call this validation/entry point rather than duplicate it.

| Module | Responsibility |
|---|---|
| models.py | Options, block schema, issues, coverage and completeness |
| pipeline.py | Signature/package validation, hashing and routing |
| pdf.py | Native rectangles, scanned/mixed pages, rotation and detailed crop OCR |
| office.py | Word/PPTX text, tables, groups, notes, relationships and media audit |
| images.py | Pixel limits, alpha/EXIF, SVG/metafile conversion and coordinate mapping |
| ocr.py | Tesseract CLI and persistent local tesseract.js worker; TSV/word geometry |
| tesseract_worker.cjs | Local-only persistent OCR process |
| svg_to_png.cjs | Optional local Sharp SVG converter |
| cli.py | Batch commands and atomic raw JSON output |

## Run on this machine

The wrapper discovers the Codex bundled Python/Node modules and the provisioned English model, and uses workspace temporary storage. It never downloads dependencies or uploads evidence.

```powershell
# All supplied documents, standard page OCR.
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_person2.ps1

# Policy with supplementary crops for small screenshots.
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_person2.ps1 -Files data/source/Cadence_Group_Risk_Management_Policy__v6.0.pdf -Regions config/policy_ocr_regions.json

# Generate a report without raw recovered text.
python scripts/report_extraction_coverage.py
```

If the system Python lacks dependencies, use the bundled Python for the report; extraction's wrapper already does so. Raw JSON goes to ignored `data/extracted/`. Code 0 means no known extraction blockers; code 2 means at least one document was quarantined/failed, with recovered blocks and issues retained. Low-confidence screenshots can legitimately produce code 2.

Apply the region file only to this policy. Normalized crop coordinates are reviewable proposals based on the supplied page images, not a general screenshot detector. Results carry `supplementary_region=true` and can duplicate full-page OCR. Consumers must compare overlapping coordinates/text without deleting genuinely repeated occurrences elsewhere.

## Setup elsewhere

Python 3.10+ is required:

```powershell
python -m pip install -e ".[test]"
python scripts/extract_documents.py path/to/evidence.pdf --output-dir data/extracted --dpi 300
```

After installation, `cadence-extract` exposes the same CLI. Supply either a local Tesseract executable (PATH or `CADENCE_TESSERACT`) and English asset, or an installed Node `tesseract.js` module:

For an independent Node setup, the locally tested package versions were `tesseract.js@7.0.0` and `sharp@0.35.5`. Install them explicitly when network access is available, for example `npm install --prefix .local/node tesseract.js@7.0.0 sharp@0.35.5`, then point the variables below at `.local/node/node_modules/`. This is optional when using the existing bundled runtime.

```powershell
$env:CADENCE_NODE = 'C:/path/to/node.exe'
$env:CADENCE_TESSERACT_JS = 'C:/path/to/node_modules/tesseract.js'
$env:CADENCE_TESSDATA = (Resolve-Path .local/ocr).Path
$env:CADENCE_SHARP = 'C:/path/to/node_modules/sharp' # optional SVG converter
```

Explicitly provision the Node language asset once using `python scripts/provision_ocr_language.py` when network access is authorized. It fetches the official tesseract-ocr English model and checks SHA256 `7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2`. Extraction never downloads models. A changed upstream model requires checksum review; `.local/` stays ignored.

SVG uses optional CairoSVG (`pip install -e ".[svg]"`) or local Node/Sharp. EMF/WMF uses Pillow's Windows GDI renderer, tested on all five source EMFs. Other platforms may need a separate converter and receive explicit warnings. External SVG/image resources are not fetched. Multi-frame/damaged/unsupported media require review.

`--min-ocr-confidence` defaults to 60; lowering it changes completeness criteria, not OCR accuracy. `--max-units` defaults to 500. File/ZIP/image limits are configurable through the API. PDF passwords use `ExtractionOptions(password=...)`; passwords are deliberately not accepted on the command line.

## API for Persons 1 and 3

```python
from cadence_detection.extraction import extract_document, ExtractionOptions
result = extract_document('evidence.docx', options=ExtractionOptions())
for block in result.blocks:
    text = block.text  # Raw PII may be present.
    location = block.source_location
    # Person 3 returns offsets into this exact block.text.
payload = result.to_dict()
```

Document IDs derive from SHA256. Block IDs and global reading order are deterministic for fixed input, settings and OCR backend/model. OCR versions can change output; record them with evaluation evidence. Native tabs/breaks remain intact. OCR joins words with spaces and retains word offsets, confidence and boxes from TSV. Native table cells retain row/column indices and nested XML paths.

DOCX has no reliable fixed page numbering before rendering: `page_or_slide` is null, with paragraph/table/header/footer/text-box paths instead. Its coverage unit is the main XML document, not its page count. Notes/comments/fields/metadata are separately labeled. Generated Word list numbering is marked but not reconstructed.

PPTX uses one-based slide indices and XML shape order, including groups, tables, notes, hidden slides and template text. Template blocks have no slide index because they can serve several slides. Authoring order is not guaranteed visual reading order. Text boxes cover their whole shape; table-cell boxes currently cover the whole table, explicitly labeled `bbox_scope=whole_table`.

Boxes are `[left, top, right, bottom]`, with explicit coordinate spaces:

- `pdf_points_top_left_unrotated`: native PDF rectangles; rotation recorded separately.
- `pdf_points_top_left_displayed`: rendered/OCR PDF after page rotation.
- `slide_emu_top_left`: slide EMUs, with group scale/translation mapped.
- `image_pixels_top_left`: DOCX asset pixels plus media part and placement path.

Rotated/flipped groups, cropped-image placement and rotated mixed PDF pages require coordinate review and generate warnings. OCR upscale is mapped back to the declared system, including word boxes. Scanned PDF tables retain line/word geometry and hierarchy; semantic cell reconstruction is pending. No measured 80% structure score is claimed.

## Completion contract

`extracted` means no known extraction blockers. `quarantined` retains recovered text but reports incomplete/uncertain content. `failed` means validation/parsing prevented meaningful processing. Info notices are non-blocking; warnings/errors make the document and all blocks incomplete. Native text survives failure to OCR another image.

Explicit issues cover unavailable/failed/low-confidence OCR; nonblank images yielding no text; missing media; unsupported attachments/charts/SmartArt; revisions/hidden runs; skipped notes/metadata; and unprocessed units. PDF annotations/forms/attachments require dedicated review. External hyperlinks are recovered as text values; external images are never fetched. Unplaced assets receive OCR attempts and retain placement warnings. Macros are not executed.

No extraction status approves content for an LLM. Person 3 must detect PII and Person 4 must redact/rescan/build the release gate. OCR cannot establish photograph/signature privacy safety. Raw JSON, sources, caches and temporary files remain local and ignored by Git. CLI summaries contain counts/statuses/IDs rather than recovered values or parser exception text.

## Tests and independent review

```powershell
python -m unittest discover -s tests/extraction -v
# Also run actual local OCR/vector checks with the engine environment configured:
$env:CADENCE_TEST_REAL_OCR = '1'
python -m unittest discover -s tests/extraction -v
```

If sandbox temporary storage is restricted, set TEMP/TMP to a writable workspace directory first. The extraction wrapper already uses `tmp/extraction`. Test dependencies are in the `test` extra. Real-source metafile checks skip without local supporting material/Windows. Individual cases are listed in `tests/extraction/README.md`.

Real-file runs establish processing coverage and warning locations, not universal PII recall or the 80% structure target. Person 5 must independently score OCR accuracy, reading order, table relationships and context, especially policy pages 9, 18-20, 22-23, 25 and 28. No finite test suite covers every malformed or novel document; unknown content must remain reviewable.

The original `setup_case_study.py` generates the initial planning documents and can overwrite current README status. Use the extraction/report commands instead of rerunning that scaffold generator.
