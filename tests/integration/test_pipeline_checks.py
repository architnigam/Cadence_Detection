import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from cadence_detection.evaluation.pipeline_checks import check_case


class PipelineCheckTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        (Path(self.folder.name) / "case.pdf").write_bytes(b"fixture")
        self.case = {"case_id": "CASE-1", "filename": "case.pdf", "allowed_statuses": ["failed", "quarantined"], "must_block_downstream": True}

    def run_case(self, result):
        return check_case(self.case, lambda _: result, self.folder.name)

    def test_controlled_failure_blocks_downstream(self):
        self.assertEqual(self.run_case({"status": "failed", "downstream_called": False, "sanitized_blocks": []})["status"], "passed")

    def test_quarantine_must_block_downstream(self):
        self.assertEqual(self.run_case({"status": "quarantined", "downstream_called": True, "sanitized_blocks": []})["status"], "failed")

    def test_missing_spy_is_failure(self):
        self.assertIn("missing_downstream_instrumentation", self.run_case({"status": "failed", "sanitized_blocks": []})["reasons"])

    def test_uncaught_exception_is_failure_without_raw_message(self):
        def runner(_):
            raise RuntimeError("raw_person@example.invalid")
        r = check_case(self.case, runner, self.folder.name)
        self.assertEqual(r["status"], "failed")
        self.assertNotIn("raw_person", json.dumps(r))

    def test_invalid_contract_is_failure(self):
        self.assertEqual(self.run_case(None)["status"], "failed")

    def test_valid_approval_needs_gate_evidence(self):
        self.case.update(allowed_statuses=["approved"], must_block_downstream=False)
        result = {"status": "approved", "downstream_called": False, "sanitized_blocks": [{"text": "[PERSON_1] control text"}], "extraction_complete": True, "verification_passed": True, "remaining_candidate_count": 0}
        self.assertEqual(self.run_case(result)["status"], "passed")
        del result["verification_passed"]
        self.assertEqual(self.run_case(result)["status"], "failed")

    def test_known_pii_survives_independent_check(self):
        self.case["forbidden_literals"] = ["noor@example.invalid"]
        self.assertIn("known_synthetic_pii_survives", self.run_case({"status": "quarantined", "downstream_called": False, "sanitized_blocks": [{"text": "noor@example.invalid"}]})["reasons"])

    def test_missing_input_is_not_run(self):
        self.case["filename"] = "missing.pdf"
        self.assertEqual(self.run_case({})["status"], "not_run")


if __name__ == "__main__":
    unittest.main()
