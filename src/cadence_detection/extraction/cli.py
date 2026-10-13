from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile
from .models import ExtractionOptions
from .pipeline import extract_document
from .ocr import default_ocr


def main(argv=None):
    parser = argparse.ArgumentParser(description="Local raw-text extraction; output may contain PII and is NOT safe for an LLM.")
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("data/extracted"))
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--min-ocr-confidence", type=float, default=60)
    parser.add_argument("--max-units", type=int, default=500)
    parser.add_argument("--regions", type=Path, help="JSON page-number to normalized crop-box list; PDF only")
    args = parser.parse_args(argv)
    regions = {}
    if args.regions:
        regions = {int(k): v for k, v in json.loads(args.regions.read_text(encoding="utf-8")).items()}
    options = ExtractionOptions(dpi=args.dpi, min_ocr_confidence=args.min_ocr_confidence, max_units=args.max_units, ocr_regions=regions)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    ocr = default_ocr()
    statuses = []
    try:
        for path in args.files:
            result = extract_document(path, options=options, ocr=ocr)
            target = args.output_dir/f"{path.stem}.{result.document_id}.json"
            # Readers must never observe a partially written result.
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=args.output_dir,
                                             prefix=".extract-", suffix=".json.tmp", delete=False) as stream:
                temporary = Path(stream.name)
                json.dump(result.to_dict(), stream, ensure_ascii=False, indent=2)
            try:
                os.replace(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)
            # Summary has no recovered text, exception messages, or document filename.
            print(json.dumps({"document_id": result.document_id, "status": result.processing_status,
                              "units": len(result.units), "blocks": len(result.blocks), "issues": len(result.issues)}))
            statuses.append(result.processing_status)
    finally:
        if ocr is not None:
            ocr.close()
    return 0 if all(s == "extracted" for s in statuses) else 2


if __name__ == "__main__":
    raise SystemExit(main())
