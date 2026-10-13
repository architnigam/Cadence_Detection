"""Build deterministic, deliberately imperfect synthetic evaluator evidence.

No detector is invoked. Safe to version: all values are invented test data.
"""

import copy
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def make_fixture():
    bundle = {"schema_version": 1, "dataset_kind": "synthetic", "documents": [],
              "blocks": [], "gold": [], "predictions": [], "results": [],
              "structure_reviews": []}
    for did, fmt in (("syn_pdf", "pdf"), ("syn_pptx", "pptx"), ("syn_docx", "docx"), ("syn_dev", "docx")):
        bundle["documents"].append({"document_id": did, "format": fmt,
                                    "split": "development" if did == "syn_dev" else "held_out",
                                    "extraction_complete": True,
                                    "expected_units": ["unit:1"], "unit_status": {"unit:1": "complete"}})

    def add(did, bid, text, phrases, kind="body"):
        block = {"document_id": did, "block_id": bid, "page_or_slide": 1,
                 "source_kind": kind, "reading_order": len(bundle["blocks"]),
                 "text": text, "image_only": did == "syn_pdf", "extraction_complete": True,
                 "annotation_status": "adjudicated"}
        bundle["blocks"].append(block)
        for value, et in phrases:
            start = 0
            while True:
                start = text.find(value, start)
                if start < 0:
                    break
                bundle["gold"].append({"document_id": did, "block_id": bid, "entity_type": et,
                                       "start": start, "end": start + len(value),
                                       "adjudication_status": "adjudicated", "reviewer": "synthetic_fixture"})
                start += len(value)

    add("syn_pptx", "contacts", "Zoë Example is the DPO. Contact zoe@example.invalid or +1 (555) 0114. Zoë Example chairs the review.",
        [("Zoë Example", "PERSON"), ("zoe@example.invalid", "EMAIL"), ("+1 (555) 0114", "PHONE")], "table")
    add("syn_pptx", "raci", "Z. Example is accountable. R, A, C and I describe roles.", [("Z. Example", "PERSON")], "table")
    cases = [("EMP-TEST-001", "EMPLOYEE_ID"), ("DIR-TEST-002", "DIRECTOR_ID"),
             ("VENDOR-PERSON-003", "VENDOR_PERSON_ID"), ("7 May 1994", "DATE_OF_BIRTH"),
             ("19 Fiction Lane, Test City", "HOME_ADDRESS"), ("000-12-3456", "NATIONAL_ID"),
             ("EXAMP1234L", "TAX_ID"), ("ZZ1234567", "PASSPORT"),
             ("TEST-ACCOUNT-004", "BANK_ACCOUNT"), ("4111 1111 1111 1111", "PAYMENT_CARD"),
             ("6790", "PARTIAL_IDENTIFIER")]
    add("syn_pdf", "narrative", "Customer record: " + "; ".join(et + " " + value for value, et in cases) + ".", cases, "narrative")
    add("syn_docx", "users", "Reviewer Noor Example uses noor@example.invalid.", [("Noor Example", "PERSON"), ("noor@example.invalid", "EMAIL")], "table")
    add("syn_docx", "negative", "OneTrust and Ironclad support Tier 2 reviews every 24 months. Policy GRP-POL-001, question DDQ-004, USD 2.4m and 11 March 2026 are business context.", [], "body")
    add("syn_dev", "dev", "Development contact Ava Example.", [("Ava Example", "PERSON")])
    add("syn_pdf", "visual", "Employee badge and signed attestation.", [], "image")
    for et, bbox in (("PHOTOGRAPH_REGION", [0.1, 0.1, 0.3, 0.4]), ("SIGNATURE_REGION", [0.4, 0.7, 0.8, 0.9])):
        bundle["gold"].append({"document_id": "syn_pdf", "block_id": "visual", "entity_type": et,
                               "bbox": bbox, "start": None, "end": None,
                               "adjudication_status": "adjudicated", "reviewer": "synthetic_fixture"})
    bundle["predictions"] = copy.deepcopy(bundle["gold"])
    # Deliberate miss, partial name, duplicate and false positive.
    bundle["predictions"] = [p for p in bundle["predictions"] if p["entity_type"] not in {"PASSPORT", "SIGNATURE_REGION"}]
    next(p for p in bundle["predictions"] if p["block_id"] == "contacts" and p["entity_type"] == "PERSON")["end"] -= 1
    bundle["predictions"].append(copy.deepcopy(next(p for p in bundle["predictions"] if p["entity_type"] == "EMAIL")))
    negative = next(b for b in bundle["blocks"] if b["block_id"] == "negative")
    bundle["predictions"].append({"document_id": "syn_docx", "block_id": "negative", "entity_type": "PERSON", "start": 0, "end": len("OneTrust")})
    for doc in bundle["documents"]:
        did = doc["document_id"]
        outputs = []
        for b in bundle["blocks"]:
            if b["document_id"] != did:
                continue
            text = b["text"]
            spans = [g for g in bundle["gold"] if g["document_id"] == did and g["block_id"] == b["block_id"] and g["start"] is not None]
            for g in sorted(spans, key=lambda f: f["start"], reverse=True):
                # Deliberately leave the passport behind to test independent leakage auditing.
                if g["entity_type"] != "PASSPORT":
                    text = text[:g["start"]] + "[" + g["entity_type"] + "_1]" + text[g["end"]:]
            outputs.append({"block_id": b["block_id"], "text": text})
        bundle["results"].append({"document_id": did, "status": "approved", "sanitized_blocks": outputs,
                                  "remaining_candidate_count": 0, "verification_passed": True})
        dimensions = {}
        for dim in ("headings", "reading_order", "block_boundaries", "table_relationships", "neighboring_context"):
            dimensions[dim] = {"applicable": True, "checks": [
                {"check_id": dim + ":1", "passed": True, "source_location": "synthetic unit 1"},
                {"check_id": dim + ":2", "passed": dim != "neighboring_context", "source_location": "synthetic unit 1"}]}
        bundle["structure_reviews"].append({"document_id": did, "dimensions": dimensions,
                                             "text_accuracy": {"correct_characters": 90, "reference_characters": 100}})
    return bundle


if __name__ == "__main__":
    out = ROOT / "data/synthetic/evaluation_fixture.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(make_fixture(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("Synthetic QA fixture written. Predictions are intentionally imperfect.")
