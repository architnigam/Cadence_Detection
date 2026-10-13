"""Local evaluation CLI. Input may contain PII; output contains counts only."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from cadence_detection.evaluation import ValidationError, evaluate_bundle, render_markdown


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Local JSON evaluation bundle")
    parser.add_argument("--output", type=Path, default=Path("output/reports/evaluation"), help="Report filename stem")
    parser.add_argument("--split", choices=["held_out", "development", "all"], default="held_out")
    parser.add_argument("--include-provisional", action="store_true", help="Exploratory scoring of unadjudicated blocks")
    parser.add_argument("--overlap-threshold", type=float, default=0.5)
    parser.add_argument("--fail-on-unsafe-approval", action="store_true", help="Exit 1 if release audit finds unsafe approval")
    args = parser.parse_args(argv)
    try:
        bundle = json.loads(args.input.read_text(encoding="utf-8"))
        report = evaluate_bundle(bundle, args.split, args.include_provisional, args.overlap_threshold)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.with_suffix(".json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        args.output.with_suffix(".md").write_text(render_markdown(report), encoding="utf-8")
    except (OSError, UnicodeError, json.JSONDecodeError):
        print("Cannot read/write evaluation files. Check paths and JSON encoding.", file=sys.stderr)
        return 2
    except ValidationError as exc:
        print("Invalid evaluation evidence: " + str(exc), file=sys.stderr)
        return 2
    print("Evaluation reports written. No raw values included.")
    if args.fail_on_unsafe_approval and any(m.get("unsafe_approval") for m in report["release_audit"].values()):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
