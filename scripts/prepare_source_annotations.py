"""Prepare LOCAL reference blocks and a review queue, never detector-derived gold.

Optional catalogue: independently reviewed literals/types plus manual PDF
transcriptions. No OCR is implemented here. Native parsing is an annotation aid
and does not claim extraction coverage. Requires python-docx and python-pptx.
"""

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def source_files(source_dir):
    names = {"source_pptx": "Cadence_Financial_Group_Organizational_Pack.pptx",
             "source_pdf": "Cadence_Group_Risk_Management_Policy__v6.0.pdf",
             "source_docx": "Cadence_TPRM_Training.docx"}
    files = {did: source_dir / name for did, name in names.items()}
    if not all(p.is_file() for p in files.values()):
        raise ValueError("Source directory must contain all three supplied artifacts.")
    return files


def prepare(source_dir, catalogue=None):
    from docx import Document
    from pptx import Presentation
    files = source_files(source_dir)
    bundle = {"schema_version": 1, "dataset_kind": "source_sample", "documents": [],
              "blocks": [], "gold": [], "predictions": [], "results": [], "structure_reviews": [],
              "annotation_notes": "Reference aid only. Canonical native blocks and manually transcribed PDF sections need human completeness review and adjudication. No detector/pipeline has run."}
    queue = []
    ppt = Presentation(files["source_pptx"])
    doc = Document(files["source_docx"])

    def add(did, bid, text, kind, location=None, image_only=False):
        if not text.strip():
            return
        bundle["blocks"].append({"document_id": did, "block_id": bid, "text": text,
                                  "source_kind": kind, "page_or_slide": location,
                                  "reading_order": len(bundle["blocks"]), "image_only": image_only,
                                  "extraction_complete": False, "annotation_status": "pending",
                                  "reference_text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()})

    def shapes(items):
        for shape in items:
            yield shape
            if hasattr(shape, "shapes"):
                yield from shapes(shape.shapes)

    for i, slide in enumerate(ppt.slides, 1):
        queue.append({"document_id": "source_pptx", "unit_id": f"slide:{i}", "status": "pending", "priority": "high" if i in [3, 6, 7, 8] else "normal"})
        for shape in shapes(slide.shapes):
            bid = f"slide:{i}:shape:{shape.shape_id}"
            if shape.has_text_frame:
                add("source_pptx", bid, shape.text, "text_box", i)
            if shape.has_table:
                for ri, row in enumerate(shape.table.rows):
                    for ci, cell in enumerate(row.cells):
                        if cell.is_spanned:
                            continue
                        add("source_pptx", f"{bid}:r:{ri}:c:{ci}", cell.text, "table", i)
        if slide.has_notes_slide:
            add("source_pptx", f"slide:{i}:notes", slide.notes_slide.notes_text_frame.text, "notes", i)
    for i, p in enumerate(doc.paragraphs, 1):
        add("source_docx", f"paragraph:{i}", p.text, "body")
    for ti, table in enumerate(doc.tables, 1):
        queue.append({"document_id": "source_docx", "unit_id": f"table:{ti}", "status": "pending", "priority": "high" if ti == 5 else "normal"})
        seen_cells = set()
        for ri, row in enumerate(table.rows):
            for ci, cell in enumerate(row.cells):
                if cell._tc in seen_cells:
                    continue
                seen_cells.add(cell._tc)
                add("source_docx", f"table:{ti}:r:{ri}:c:{ci}", cell.text, "table")
    for si, section in enumerate(doc.sections, 1):
        for label in ("header", "footer", "first_page_header", "first_page_footer", "even_page_header", "even_page_footer"):
            part = getattr(section, label)
            for pi, p in enumerate(part.paragraphs, 1):
                add("source_docx", f"section:{si}:{label}:p:{pi}", p.text, "header" if "header" in label else "footer")
    # Page count is verified against the supplied 35-page policy inventory.
    from pypdf import PdfReader
    pages = len(PdfReader(files["source_pdf"]).pages)
    for i in range(1, pages + 1):
        queue.append({"document_id": "source_pdf", "unit_id": f"page:{i}", "status": "pending",
                      "priority": "high" if i in [9, 18, 19, 20, 22, 23, 25, 28, 32] else "normal"})
    from zipfile import ZipFile
    with ZipFile(files["source_docx"]) as z:
        media = sorted(n for n in z.namelist() if n.startswith("word/media/"))
    for name in media:
        queue.append({"document_id": "source_docx", "unit_id": "media:" + Path(name).name,
                      "status": "pending", "priority": "high", "needs_conversion": Path(name).suffix.lower() in {".svg", ".emf"}})
    for extra in ("body", "headers_footers", "text_boxes", "nested_tables", "comments_hidden_content"):
        queue.append({"document_id": "source_docx", "unit_id": extra, "status": "pending", "priority": "normal"})
    for did, path in files.items():
        bundle["documents"].append({"document_id": did, "format": path.suffix[1:],
                                    "split": "held_out" if did == "source_pdf" else "development",
                                    "extraction_complete": False, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                                    "expected_units": [q["unit_id"] for q in queue if q["document_id"] == did], "unit_status": {}})
    if catalogue:
        for manual in catalogue.get("manual_blocks", []):
            add(manual["document_id"], manual["block_id"], manual["text"], manual["source_kind"], manual["page_or_slide"], True)
        for block in bundle["blocks"]:
            phrases = list(catalogue.get("catalogues", {}).get(block["document_id"], []))
            manual = next((m for m in catalogue.get("manual_blocks", []) if m["document_id"] == block["document_id"] and m["block_id"] == block["block_id"]), {})
            phrases += manual.get("labels", [])
            if manual.get("reviewed") or any(block["block_id"].startswith(prefix) for prefix in catalogue.get("reviewed_block_prefixes", {}).get(block["document_id"], [])):
                block["annotation_status"] = "reviewed"
            for item in phrases:
                value = item["value"]
                if not value:
                    raise ValueError("Catalogue literals cannot be empty.")
                start, occurrence = 0, 0
                while True:
                    start = block["text"].find(value, start)
                    if start < 0:
                        break
                    occurrence += 1
                    if item.get("occurrence") is not None and item["occurrence"] != occurrence:
                        start += len(value)
                        continue
                    bundle["gold"].append({"document_id": block["document_id"], "block_id": block["block_id"],
                                           "entity_type": item["entity_type"], "start": start, "end": start + len(value),
                                           "image_only": block["image_only"], "reviewer": "source_review_first_pass",
                                           "adjudication_status": "reviewed", "notes": "Independent source catalogue/manual transcription. Await block-completeness review and second reviewer."})
                    start += len(value)
    return bundle, queue


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=ROOT.parent / "Case Study 2 Supporting Material (1)/Case Study 2 Supporting Material")
    parser.add_argument("--catalogue", type=Path, help="LOCAL independently reviewed literal catalogue")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data/annotations/local_source")
    args = parser.parse_args()
    try:
        catalogue = json.loads(args.catalogue.read_text(encoding="utf-8")) if args.catalogue else None
        bundle, queue = prepare(args.source_dir, catalogue)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "source_reference.json").write_text(json.dumps(bundle, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        (args.output_dir / "review_queue.json").write_text(json.dumps(queue, indent=2) + "\n", encoding="utf-8")
    except (ImportError, OSError, ValueError, KeyError):
        print("Could not prepare annotations. Check source files, catalogue schema and optional document libraries.", file=sys.stderr)
        return 2
    print(f"Local annotation aid written: {len(bundle['blocks'])} reference blocks, {len(bundle['gold'])} provisional occurrences, {len(queue)} review units. No extraction/detection accuracy claimed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
