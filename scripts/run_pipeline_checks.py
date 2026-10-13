"""Run Person 5 black-box failure/success checks via a local integration adapter."""

import argparse
import importlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from cadence_detection.evaluation.pipeline_checks import check_case


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runner", help="module:function. Must run locally with downstream LLM replaced by a spy.")
    parser.add_argument("--cases", type=Path, default=ROOT / "data/synthetic/pipeline_cases.json")
    parser.add_argument("--input-dir", type=Path, default=ROOT / "data/synthetic/pipeline_inputs")
    parser.add_argument("--output", type=Path, default=ROOT / "output/reports/pipeline_checks.json")
    args = parser.parse_args()
    try:
        cases = json.loads(args.cases.read_text(encoding="utf-8"))
        if args.runner:
            module, name = args.runner.split(":", 1)
            runner = getattr(importlib.import_module(module), name)
            checks = [check_case(c, runner, args.input_dir) for c in cases]
        else:
            checks = [{"case_id": c["case_id"], "status": "not_run", "reasons": ["pipeline_adapter_pending"]} for c in cases]
        report = {"scope": "Local black-box checks. Not detector metrics.", "checks": checks,
                  "passed": sum(c["status"] == "passed" for c in checks),
                  "failed": sum(c["status"] == "failed" for c in checks),
                  "not_run": sum(c["status"] == "not_run" for c in checks)}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, ImportError, AttributeError, KeyError, TypeError):
        print("Cannot run checks. Verify local adapter and case manifest.", file=sys.stderr)
        return 2
    print(f"Pipeline checks: {report['passed']} passed, {report['failed']} failed, {report['not_run']} not run.")
    # Unexecuted mandatory cases also fail a regression job.
    return 1 if report["failed"] or report["not_run"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
