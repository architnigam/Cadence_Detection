"""Summarize extraction results without copying raw extracted content into a report."""
from pathlib import Path
import argparse
from collections import Counter
import json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, default=Path("data/extracted"))
    parser.add_argument("--output", type=Path, default=Path("output/reports/person2_extraction_coverage.md"))
    args = parser.parse_args()
    rows = []; details = []
    for path in sorted(args.input_dir.glob("*.json")):
        d = json.loads(path.read_text(encoding="utf-8"))
        if "coverage" not in d:
            continue
        cov = d["coverage"]; codes = Counter(i["code"] for i in d["issues"])
        rows.append(f"| {d['filename']} | {d['processing_status']} | {cov['processed_units']}/{cov['total_units']} | {cov['block_count']} | {cov['ocr_block_count']} |")
        details.append(f"## {d['filename']}\n\nSHA256: `{d['sha256']}`\n\nIssue counts: "+(", ".join(f"{k}: {v}" for k,v in sorted(codes.items())) or "none")+".\n")
        regions = sum(u.get("detail_region_blocks", 0) for u in d["units"])
        if regions:
            details.append(f"Supplementary OCR crop blocks: {regions}. Crops may repeat full-page text; evaluate/deduplicate by location and overlap, not by text alone.\n")
        if d["detected_format"] == "docx":
            details.append("DOCX units are XML document parts, not rendered pages. Native table rows/columns and paragraph paths are retained. Native Word pagination is not claimed.\n")
    text = """# Person 2 extraction coverage

This is a processing report, not a PII detection report or proof of the 80% structure target. JSON outputs contain raw PII and remain local/ignored by Git. `extracted` means no known extraction blockers; it never means sanitized or safe to send to an LLM.

| Source | Status | Processed units | Blocks | OCR blocks |
|---|---|---|---|---|
"""+"\n".join(rows)+"\n\n"+"\n".join(details)+"""
## Independent checks still required

- Person 5 must annotate OCR errors and evaluate headings, reading order, paragraphs, table relationships and context. Text/word positions are available for layout inspection; scanned table cells are not semantically reconstructed.
- Low-confidence lines and non-text images need review. Photographs and signatures are visual content; OCR cannot prove their privacy safety.
- Charts, SmartArt, unsupported attachments, revisions, cropped/rotated groups and unknown assets produce explicit warnings instead of false completeness.
- The real-file run is a regression check on supplied artifacts, not exhaustive validation of every possible PDF/Office file.
"""
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(text, encoding="utf-8")
    print(f"Wrote coverage report for {len(rows)} source files.")


if __name__ == "__main__":
    main()
