"""Person 5 evaluator and gate-audit regression tests, not detector accuracy tests."""

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from cadence_detection.evaluation import ValidationError, evaluate_bundle, render_markdown
from build_qa_fixture import make_fixture


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.b = make_fixture()

    def test_exact_and_diagnostic_are_distinct(self):
        r = evaluate_bundle(self.b)
        self.assertEqual((r["exact_text"]["tp"], r["exact_text"]["fp"], r["exact_text"]["fn"]), (16, 3, 2))
        self.assertEqual(r["overlap_text_diagnostic"]["tp"], 17)
        self.assertEqual(r["visual_region_detection"]["fn"], 1)
        self.assertEqual(r["by_text_origin"]["image_only"]["gold_occurrences"], 11)
        self.assertEqual(sum(e["count"] for e in r["exact_text_errors"]["false_negatives"]), 2)
        self.assertEqual(sum(e["count"] for e in r["exact_text_errors"]["false_positives"]), 3)

    def test_perfect_predictions_score_one(self):
        self.b["predictions"] = copy.deepcopy(self.b["gold"])
        r = evaluate_bundle(self.b)
        self.assertEqual(r["exact_text"]["f1"], 1)
        self.assertEqual(r["visual_region_detection"]["recall"], 1)

    def test_no_predictions_recall_zero_precision_undefined(self):
        self.b["predictions"] = []
        r = evaluate_bundle(self.b)
        self.assertEqual(r["exact_text"]["recall"], 0)
        self.assertIsNone(r["exact_text"]["precision"])
        self.assertEqual(r["exact_text"]["f1"], 0)

    def test_negative_only_has_no_fake_recall(self):
        self.b["gold"] = []
        self.b["predictions"] = []
        r = evaluate_bundle(self.b)
        self.assertIsNone(r["exact_text"]["recall"])
        self.assertIsNone(r["exact_text"]["f1"])

    def test_held_out_excludes_development(self):
        held = evaluate_bundle(self.b)
        all_data = evaluate_bundle(self.b, split="all")
        self.assertEqual(all_data["exact_text"]["gold_occurrences"], held["exact_text"]["gold_occurrences"] + 1)
        self.assertNotIn("syn_dev", held["by_document"])

    def test_provisional_labels_are_excluded_and_counted(self):
        for b in self.b["blocks"]:
            b["annotation_status"] = "reviewed"
        for g in self.b["gold"]:
            g["adjudication_status"] = "reviewed"
        r = evaluate_bundle(self.b)
        self.assertEqual(r["exact_text"]["gold_occurrences"], 0)
        self.assertGreater(r["scope"]["excluded_predictions"], 0)
        self.assertIsNone(r["exact_text"]["recall"])
        self.assertEqual(evaluate_bundle(self.b, include_provisional=True)["exact_text"]["gold_occurrences"], 18)

    def test_wrong_type_counts_false_positive_and_false_negative(self):
        self.b["predictions"] = copy.deepcopy(self.b["gold"])
        self.b["predictions"][0]["entity_type"] = "EMAIL"
        r = evaluate_bundle(self.b)
        self.assertEqual((r["exact_text"]["fp"], r["exact_text"]["fn"]), (1, 1))

    def test_duplicate_prediction_does_not_increase_recall(self):
        self.b["predictions"] = copy.deepcopy(self.b["gold"])
        self.b["predictions"].append(copy.deepcopy(self.b["predictions"][0]))
        r = evaluate_bundle(self.b)
        self.assertEqual(r["exact_text"]["fp"], 1)
        self.assertEqual(r["exact_text"]["recall"], 1)

    def test_invalid_offsets_and_unknown_block_fail(self):
        for edit in ({"start": -1}, {"end": 999999}, {"start": True}, {"block_id": "unknown"}):
            b = copy.deepcopy(self.b)
            b["predictions"][0].update(edit)
            with self.assertRaises(ValidationError):
                evaluate_bundle(b)

    def test_duplicate_gold_fails(self):
        self.b["gold"].append(copy.deepcopy(self.b["gold"][0]))
        with self.assertRaises(ValidationError):
            evaluate_bundle(self.b)

    def test_bbox_validation_and_no_text_offsets(self):
        g = next(g for g in self.b["gold"] if g["entity_type"] == "PHOTOGRAPH_REGION")
        for box in ([0, 0, 2, 1], [0.5, 0, 0.1, 1], [0, 0, float("nan"), 1]):
            g["bbox"] = box
            with self.assertRaises(ValidationError):
                evaluate_bundle(self.b)

    def test_structure_rubric_separate_from_accuracy(self):
        r = evaluate_bundle(self.b)
        m = r["structure"]["syn_pdf"]
        self.assertAlmostEqual(m["score"], 0.9)
        self.assertTrue(m["meets_80_percent"])
        self.assertEqual(m["text_accuracy"]["reference_characters"], 100)

    def test_structure_na_renormalizes_and_missing_review_is_unknown(self):
        s = self.b["structure_reviews"][0]
        s["dimensions"]["table_relationships"] = {"applicable": False, "reason": "No table in selected fixture"}
        r = evaluate_bundle(self.b)
        self.assertAlmostEqual(r["structure"]["syn_pdf"]["score"], 0.875)
        self.b["structure_reviews"] = []
        self.assertIsNone(evaluate_bundle(self.b)["structure"]["syn_pdf"]["meets_80_percent"])

    def test_missing_structure_dimension_cannot_pass(self):
        del self.b["structure_reviews"][0]["dimensions"]["headings"]
        with self.assertRaises(ValidationError):
            evaluate_bundle(self.b)

    def test_leaked_passport_blocks_claimed_approval(self):
        m = evaluate_bundle(self.b)["release_audit"]["syn_pdf"]
        self.assertTrue(m["unsafe_approval"])
        self.assertEqual(m["known_residual_occurrences"], 1)
        self.assertIn("known_gold_values_survive", m["release_blockers"])

    def test_clean_fixture_has_zero_known_residuals(self):
        result = self.b["results"][0]
        result["sanitized_blocks"][0]["text"] = result["sanitized_blocks"][0]["text"].replace("ZZ1234567", "[PASSPORT_1]")
        m = evaluate_bundle(self.b)["release_audit"]["syn_pdf"]
        self.assertFalse(m["unsafe_approval"])
        self.assertEqual(m["known_residual_occurrences"], 0)

    def test_missing_and_blank_outputs_are_blockers(self):
        for mutation in ("missing", "blank"):
            b = copy.deepcopy(self.b)
            output = b["results"][1]["sanitized_blocks"]
            if mutation == "missing":
                output.pop()
            else:
                output[0]["text"] = ""
            m = evaluate_bundle(b)["release_audit"]["syn_pptx"]
            self.assertTrue(m["unsafe_approval"])

    def test_incomplete_extraction_and_failed_rescan_block_approval(self):
        self.b["documents"][1]["extraction_complete"] = False
        self.b["results"][1]["verification_passed"] = False
        self.b["results"][1]["remaining_candidate_count"] = 2
        m = evaluate_bundle(self.b)["release_audit"]["syn_pptx"]
        self.assertTrue(m["unsafe_approval"])
        self.assertIn("incomplete_extraction", m["release_blockers"])
        self.b["results"][1]["status"] = "quarantined"
        self.assertFalse(evaluate_bundle(self.b)["release_audit"]["syn_pptx"]["unsafe_approval"])

    def test_missing_result_is_not_run(self):
        self.b["results"] = []
        m = evaluate_bundle(self.b)["release_audit"]["syn_pdf"]
        self.assertEqual(m["status"], "not_run")
        self.assertIsNone(m["known_residual_occurrences"])

    def test_source_coverage_cannot_claim_complete_with_missing_page(self):
        self.b["documents"][0]["expected_units"].append("unit:2")
        with self.assertRaises(ValidationError):
            evaluate_bundle(self.b)
        self.b["documents"][0]["extraction_complete"] = False
        m = evaluate_bundle(self.b)["extraction_coverage"]["syn_pdf"]
        self.assertEqual(m["coverage"], 0.5)
        self.assertEqual(m["missing_or_incomplete_units"], ["unit:2"])

    def test_reports_do_not_include_raw_pii(self):
        r = evaluate_bundle(self.b)
        encoded = json.dumps(r) + render_markdown(r)
        for value in ("ZZ1234567", "zoe@example.invalid", "Zoë Example", "19 Fiction Lane"):
            self.assertNotIn(value, encoded)

    def test_pending_negative_blocks_are_never_scored(self):
        for b in self.b["blocks"]:
            b["annotation_status"] = "pending"
        r = evaluate_bundle(self.b, include_provisional=True)
        self.assertEqual(r["scope"]["evaluated_blocks"], 0)
        self.assertEqual(r["scope"]["negative_blocks"], 0)

    def test_reference_hash_detects_offset_drift(self):
        block = self.b["blocks"][0]
        block["reference_text_sha256"] = hashlib.sha256(block["text"].encode("utf-8")).hexdigest()
        evaluate_bundle(self.b)
        block["text"] = block["text"].replace("Zoë", "Zoe")
        with self.assertRaises(ValidationError):
            evaluate_bundle(self.b)

    def test_malformed_nested_fields_are_controlled_validation_errors(self):
        edits = [("documents", "format"), ("documents", "split"), ("blocks", "document_id"),
                 ("blocks", "source_kind"), ("gold", "entity_type"), ("predictions", "block_id"),
                 ("results", "status"), ("structure_reviews", "document_id")]
        for collection, field in edits:
            b = copy.deepcopy(self.b)
            b[collection][0][field] = []
            with self.assertRaises(ValidationError, msg=collection + "." + field):
                evaluate_bundle(b)

    def test_overlap_uses_maximum_matching(self):
        b = copy.deepcopy(self.b)
        block = b["blocks"][0]
        block["text"] = "abcdefgh"
        block["document_id"] = "syn_pdf"
        block["block_id"] = "matching"
        b["blocks"] = [block]
        def finding(start, end):
            return {"document_id": "syn_pdf", "block_id": "matching", "entity_type": "PERSON",
                    "start": start, "end": end, "adjudication_status": "adjudicated"}
        b["gold"] = [finding(0, 4), finding(4, 8)]
        b["predictions"] = [finding(0, 8), finding(0, 4)]
        b["results"] = []
        r = evaluate_bundle(b)
        self.assertEqual(r["exact_text"]["tp"], 1)
        self.assertEqual(r["overlap_text_diagnostic"]["tp"], 2)

    def test_leak_found_when_moved_to_another_block(self):
        result = self.b["results"][1]
        result["sanitized_blocks"][0]["text"] += " zoe@example.invalid"
        m = evaluate_bundle(self.b)["release_audit"]["syn_pptx"]
        self.assertTrue(m["unsafe_approval"])
        self.assertEqual(m["known_residual_occurrences"], 1)

    def test_malformed_json_and_empty_file_return_validation_exit(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / "input.json"
            for text in ("", "not JSON", "{}"):
                p.write_text(text, encoding="utf-8")
                run = subprocess.run([sys.executable, str(ROOT / "scripts/evaluate.py"), str(p)], capture_output=True, text=True)
                self.assertEqual(run.returncode, 2)

    def test_cli_unsafe_approval_exit_and_private_reports(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / "input.json"
            out = Path(folder) / "report"
            p.write_text(json.dumps(self.b), encoding="utf-8")
            run = subprocess.run([sys.executable, str(ROOT / "scripts/evaluate.py"), str(p), "--output", str(out), "--fail-on-unsafe-approval"], capture_output=True, text=True)
            self.assertEqual(run.returncode, 1, run.stderr)
            self.assertTrue(out.with_suffix(".json").exists())
            self.assertNotIn("ZZ1234567", out.with_suffix(".md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
