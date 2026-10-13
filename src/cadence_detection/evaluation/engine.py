"""Evaluate independently annotated occurrences without emitting their values.

Python Unicode code-point offsets are inclusive/exclusive. Exact occurrence and
type matching is the primary text metric. Maximum one-to-one overlap matching is
a diagnostic, never a substitute for exact recall. No third-party dependencies.
"""

from collections import Counter, defaultdict
import math
import re


ENTITY_TYPES = {
    "PERSON", "EMAIL", "PHONE", "EMPLOYEE_ID", "DIRECTOR_ID", "VENDOR_PERSON_ID",
    "DATE_OF_BIRTH", "HOME_ADDRESS", "NATIONAL_ID", "TAX_ID", "PASSPORT",
    "BANK_ACCOUNT", "PAYMENT_CARD", "PARTIAL_IDENTIFIER", "PHOTOGRAPH_REGION",
    "SIGNATURE_REGION",
}
VISUAL_TYPES = {"PHOTOGRAPH_REGION", "SIGNATURE_REGION"}
STRUCTURE_DIMENSIONS = (
    "headings", "reading_order", "block_boundaries", "table_relationships",
    "neighboring_context",
)


class ValidationError(ValueError):
    """Invalid evaluation evidence. Messages deliberately omit input values."""


def _require(condition, message):
    if not condition:
        raise ValidationError(message)


def _integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _identifier(value):
    # IDs appear in safe reports; never use a person's name or an email as an ID.
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.:-]{1,100}", value)


def _bbox(value):
    return (isinstance(value, list) and len(value) == 4
            and all(isinstance(n, (int, float)) and not isinstance(n, bool)
                    and math.isfinite(n) for n in value)
            and 0 <= value[0] < value[2] <= 1
            and 0 <= value[1] < value[3] <= 1)


def validate_bundle(bundle):
    """Fail on ambiguous labels, wrong offsets, unknown blocks or mixed splits."""
    _require(isinstance(bundle, dict), "Bundle must be a JSON object.")
    _require(bundle.get("schema_version") == 1, "Expected schema_version 1.")
    _require(bundle.get("dataset_kind") in {"synthetic", "source_sample", "full_source"},
             "Declare dataset_kind.")
    for field in ("documents", "blocks", "gold", "predictions"):
        _require(isinstance(bundle.get(field), list), "Missing required list: " + field)
    docs, blocks, gold_keys = {}, {}, set()
    for doc in bundle["documents"]:
        _require(isinstance(doc, dict), "Document must be an object.")
        did = doc.get("document_id")
        _require(_identifier(did) and did not in docs, "Document IDs must be unique safe IDs.")
        _require(doc.get("format") in {"pdf", "pptx", "docx"}, "Invalid document format.")
        _require(doc.get("split") in {"development", "held_out"}, "Declare document split.")
        _require(isinstance(doc.get("extraction_complete"), bool), "Declare extraction completeness.")
        expected = doc.get("expected_units", [])
        _require(isinstance(expected, list) and all(_identifier(x) for x in expected)
                 and len(expected) == len(set(expected)), "Invalid expected source units.")
        statuses = doc.get("unit_status", {})
        _require(isinstance(statuses, dict) and set(statuses) <= set(expected)
                 and all(v in {"complete", "incomplete", "failed"} for v in statuses.values()),
                 "Invalid source unit coverage.")
        if expected and doc["extraction_complete"]:
            _require(all(statuses.get(x) == "complete" for x in expected),
                     "Complete extraction contradicts missing/failed source units.")
        docs[did] = doc
    _require(bool(docs), "At least one document is required.")
    for block in bundle["blocks"]:
        _require(isinstance(block, dict), "Block must be an object.")
        key = (block.get("document_id"), block.get("block_id"))
        _require(key[0] in docs and _identifier(key[1]) and key not in blocks,
                 "Blocks must have unique keys and known documents.")
        _require(isinstance(block.get("text"), str), "Block text must be a string.")
        _require(isinstance(block.get("image_only"), bool), "Declare image_only per block.")
        _require(block.get("source_kind") in {"body", "table", "narrative", "image", "header", "footer", "notes", "text_box"},
                 "Invalid block source_kind.")
        _require(block.get("annotation_status") in {"pending", "reviewed", "adjudicated"},
                 "Declare annotation status, including negative blocks.")
        _require(isinstance(block.get("extraction_complete"), bool), "Declare block extraction completeness.")
        location = block.get("page_or_slide")
        _require(location is None or (_integer(location) and location > 0), "Invalid page/slide number.")
        blocks[key] = block
    for role in ("gold", "predictions"):
        for finding in bundle[role]:
            _require(isinstance(finding, dict), "Finding must be an object.")
            key = (finding.get("document_id"), finding.get("block_id"))
            _require(key in blocks, "Finding refers to an unknown block.")
            et = finding.get("entity_type")
            _require(et in ENTITY_TYPES, "Finding has unknown entity_type.")
            if et in VISUAL_TYPES:
                _require(_bbox(finding.get("bbox")), "Visual findings need normalized [x0,y0,x1,y1] boxes.")
                _require(finding.get("start") is None and finding.get("end") is None,
                         "Visual regions cannot use text offsets.")
                unique = key + (et, tuple(finding["bbox"]))
            else:
                a, b = finding.get("start"), finding.get("end")
                _require(_integer(a) and _integer(b) and 0 <= a < b <= len(blocks[key]["text"]),
                         "Finding offsets are outside the exact block text.")
                unique = key + (et, a, b)
            if role == "gold":
                _require(finding.get("adjudication_status") in {"pending", "reviewed", "adjudicated"},
                         "Gold annotation needs adjudication_status.")
                _require(unique not in gold_keys, "Duplicate gold occurrence.")
                gold_keys.add(unique)
                if blocks[key]["annotation_status"] == "adjudicated":
                    _require(finding["adjudication_status"] == "adjudicated",
                             "Adjudicated block contains provisional gold.")
            if "confidence" in finding:
                c = finding["confidence"]
                _require(isinstance(c, (int, float)) and not isinstance(c, bool)
                         and math.isfinite(c) and 0 <= c <= 1, "Invalid confidence.")
    _require(isinstance(bundle.get("results", []), list), "Results must be a list.")
    _require(isinstance(bundle.get("structure_reviews", []), list), "Structure reviews must be a list.")
    return docs, blocks


def _key(f):
    return (f["document_id"], f["block_id"], f["entity_type"], f["start"], f["end"])


def _counts(tp, fp, fn):
    return {"tp": tp, "fp": fp, "fn": fn, "gold_occurrences": tp + fn,
            "predicted_occurrences": tp + fp,
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None,
            "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None}


def _exact(gold, predictions):
    g = Counter(_key(x) for x in gold)
    p = Counter(_key(x) for x in predictions)
    tp = sum((g & p).values())
    return _counts(tp, sum(p.values()) - tp, sum(g.values()) - tp)


def _iou(g, p):
    if (g["document_id"], g["block_id"], g["entity_type"]) != (p["document_id"], p["block_id"], p["entity_type"]):
        return 0.0
    if g["entity_type"] in VISUAL_TYPES:
        a, b = g["bbox"], p["bbox"]
        intersection = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
        union = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - intersection
    else:
        intersection = max(0, min(g["end"], p["end"]) - max(g["start"], p["start"]))
        union = max(g["end"], p["end"]) - min(g["start"], p["start"])
    return intersection / union if union else 0.0


def _overlap(gold, predictions, threshold):
    """Maximum cardinality bipartite matching avoids greedy order dependence."""
    adjacency = [[j for j, p in enumerate(predictions) if _iou(g, p) >= threshold] for g in gold]
    assignments = {}

    def augment(i, visited):
        for j in adjacency[i]:
            if j in visited:
                continue
            visited.add(j)
            if j not in assignments or augment(assignments[j], visited):
                assignments[j] = i
                return True
        return False

    tp = sum(augment(i, set()) for i in range(len(gold)))
    return _counts(tp, len(predictions) - tp, len(gold) - tp)


def _grouped(gold, predictions, getter, values=None):
    values = sorted(set(values or []) | {getter(x) for x in gold + predictions})
    return {v: _exact([x for x in gold if getter(x) == v],
                      [x for x in predictions if getter(x) == v]) for v in values}


def score_structure(reviews, docs, selected_ids):
    """Equal dimension weights, with explicit N/A reasons and denominators."""
    by_doc = {}
    for review in reviews:
        _require(isinstance(review, dict), "Structure review must be an object.")
        did = review.get("document_id")
        _require(did in docs and did not in by_doc, "Invalid/duplicate structure document.")
        dimensions = review.get("dimensions")
        _require(isinstance(dimensions, dict) and set(dimensions) == set(STRUCTURE_DIMENSIONS),
                 "Structure review must explicitly cover all five dimensions.")
        scores, details = [], {}
        for dim in STRUCTURE_DIMENSIONS:
            data = dimensions[dim]
            _require(isinstance(data, dict) and isinstance(data.get("applicable"), bool),
                     "Each structure dimension needs applicability.")
            if not data["applicable"]:
                _require(isinstance(data.get("reason"), str) and bool(data["reason"].strip()),
                         "N/A dimension requires a reason.")
                details[dim] = {"applicable": False, "passed": 0, "total": 0, "score": None}
                continue
            checks = data.get("checks")
            _require(isinstance(checks, list) and bool(checks), "Applicable dimension needs checks.")
            seen = set()
            for check in checks:
                _require(isinstance(check, dict) and _identifier(check.get("check_id"))
                         and check["check_id"] not in seen
                         and isinstance(check.get("passed"), bool), "Invalid/duplicate structure check.")
                _require(isinstance(check.get("source_location"), str) and bool(check["source_location"]),
                         "Structure check needs source evidence location.")
                seen.add(check["check_id"])
            passed = sum(c["passed"] for c in checks)
            score = passed / len(checks)
            scores.append(score)
            details[dim] = {"applicable": True, "passed": passed, "total": len(checks), "score": score}
        _require(bool(scores), "At least one structure dimension must apply.")
        average = sum(scores) / len(scores)
        accuracy = review.get("text_accuracy")
        if accuracy is not None:
            _require(isinstance(accuracy, dict) and _integer(accuracy.get("correct_characters"))
                     and _integer(accuracy.get("reference_characters"))
                     and 0 <= accuracy["correct_characters"] <= accuracy["reference_characters"]
                     and accuracy["reference_characters"] > 0, "Invalid independently aligned text accuracy.")
            accuracy = dict(accuracy, score=accuracy["correct_characters"] / accuracy["reference_characters"])
        by_doc[did] = {"status": "reviewed", "score": average,
                       "meets_80_percent": average >= 0.8,
                       "dimensions": details, "text_accuracy": accuracy}
    return {did: by_doc.get(did, {"status": "not_reviewed", "score": None,
                                "meets_80_percent": None}) for did in sorted(selected_ids)}


def _normalized(text):
    return " ".join(text.casefold().split())


def audit_results(results, docs, blocks, gold, selected_ids):
    """Audit claimed release states; this function never approves a document.

    Residual checks independently search known gold values in all sanitized
    blocks of their document. A zero count covers known labels only. Reports
    contain identifiers/locations/counts, never the sensitive strings.
    """
    by_doc = {}
    for result in results:
        _require(isinstance(result, dict), "Result must be an object.")
        did = result.get("document_id")
        _require(did in docs and did not in by_doc, "Unknown/duplicate result document.")
        _require(result.get("status") in {"approved", "quarantined", "failed"}, "Invalid release status.")
        sanitized = result.get("sanitized_blocks")
        _require(isinstance(sanitized, list), "Result needs sanitized_blocks.")
        output_ids, output_texts = set(), []
        empty_ids = []
        for block in sanitized:
            _require(isinstance(block, dict), "Sanitized block must be an object.")
            bid = block.get("block_id")
            _require((did, bid) in blocks and bid not in output_ids
                     and block.get("document_id", did) == did
                     and isinstance(block.get("text"), str), "Invalid/duplicate sanitized block.")
            output_ids.add(bid)
            output_texts.append(_normalized(block["text"]))
            if blocks[(did, bid)]["text"].strip() and not block["text"].strip():
                empty_ids.append(bid)
        candidates = result.get("remaining_candidate_count")
        _require(_integer(candidates) and candidates >= 0, "Declare remaining_candidate_count.")
        _require(isinstance(result.get("verification_passed"), bool), "Declare verification_passed.")
        input_ids = {bid for doc_id, bid in blocks if doc_id == did}
        missing = sorted(input_ids - output_ids)
        incomplete = (not docs[did]["extraction_complete"]
                      or any(not b["extraction_complete"] for (doc_id, _), b in blocks.items() if doc_id == did))
        values = defaultdict(list)
        for finding in gold:
            if finding["document_id"] == did and finding["entity_type"] not in VISUAL_TYPES:
                original = blocks[(did, finding["block_id"])]["text"]
                value = _normalized(original[finding["start"]:finding["end"]])
                values[value].append(finding)
        residuals = []
        for value, findings in values.items():
            count = sum(text.count(value) for text in output_texts)
            if count:
                residuals.append({"entity_types": sorted({f["entity_type"] for f in findings}),
                                  "source_block_ids": sorted({f["block_id"] for f in findings}),
                                  "gold_occurrences": len(findings), "residual_occurrences": count})
        reasons = []
        if incomplete:
            reasons.append("incomplete_extraction")
        if missing:
            reasons.append("missing_sanitized_blocks")
        if empty_ids:
            reasons.append("empty_sanitized_content")
        if not input_ids:
            reasons.append("no_extracted_blocks")
        if candidates:
            reasons.append("remaining_candidates")
        if not result["verification_passed"]:
            reasons.append("verification_not_passed")
        if residuals:
            reasons.append("known_gold_values_survive")
        by_doc[did] = {
            "status": result["status"], "known_residual_occurrences": sum(r["residual_occurrences"] for r in residuals),
            "checked_distinct_gold_values": len(values), "checked_gold_occurrences": sum(map(len, values.values())),
            "residuals": residuals, "missing_block_ids": missing, "empty_block_ids": sorted(empty_ids),
            "release_blockers": reasons,
            "unsafe_approval": result["status"] == "approved" and bool(reasons),
            "scope": "Known labeled text values only. Does not certify sanitized original files or unseen PII.",
        }
    return {did: by_doc.get(did, {"status": "not_run", "unsafe_approval": None,
                                "known_residual_occurrences": None}) for did in sorted(selected_ids)}


def evaluate_bundle(bundle, split="held_out", include_provisional=False, overlap_threshold=0.5):
    docs, blocks = validate_bundle(bundle)
    _require(split in {"held_out", "development", "all"}, "Invalid evaluation split.")
    _require(isinstance(overlap_threshold, (int, float)) and not isinstance(overlap_threshold, bool)
             and math.isfinite(overlap_threshold) and 0 < overlap_threshold <= 1, "Invalid overlap threshold.")
    selected_ids = {did for did, d in docs.items() if split == "all" or d["split"] == split}
    _require(bool(selected_ids), "No documents in selected split.")
    eligible = {key for key, b in blocks.items() if key[0] in selected_ids
                and (include_provisional or b["annotation_status"] == "adjudicated")}
    gold = [f for f in bundle["gold"] if (f["document_id"], f["block_id"]) in eligible]
    predictions = [f for f in bundle["predictions"] if (f["document_id"], f["block_id"]) in eligible]
    gt = [f for f in gold if f["entity_type"] not in VISUAL_TYPES]
    pt = [f for f in predictions if f["entity_type"] not in VISUAL_TYPES]
    gv = [f for f in gold if f["entity_type"] in VISUAL_TYPES]
    pv = [f for f in predictions if f["entity_type"] in VISUAL_TYPES]
    report = {
        "schema_version": 1, "dataset_kind": bundle["dataset_kind"], "split": split,
        "provisional_labels_included": include_provisional,
        "scope": {"selected_documents": len(selected_ids), "evaluated_blocks": len(eligible),
                  "excluded_unadjudicated_blocks": sum(k[0] in selected_ids and k not in eligible for k in blocks),
                  "excluded_predictions": sum(f["document_id"] in selected_ids and (f["document_id"], f["block_id"]) not in eligible for f in bundle["predictions"]),
                  "negative_blocks": sum(not any((f["document_id"], f["block_id"]) == k for f in gold) for k in eligible)},
        "exact_text": _exact(gt, pt),
        "overlap_text_diagnostic": dict(_overlap(gt, pt, overlap_threshold), iou_threshold=overlap_threshold),
        "visual_region_detection": dict(_overlap(gv, pv, overlap_threshold), iou_threshold=overlap_threshold),
        "by_category": _grouped(gt, pt, lambda f: f["entity_type"], ENTITY_TYPES - VISUAL_TYPES),
        "by_format": _grouped(gt, pt, lambda f: docs[f["document_id"]]["format"], {docs[d]["format"] for d in selected_ids}),
        "by_document": _grouped(gt, pt, lambda f: f["document_id"], selected_ids),
        "by_source_kind": _grouped(gt, pt, lambda f: blocks[(f["document_id"], f["block_id"])]["source_kind"]),
        "by_text_origin": _grouped(gt, pt, lambda f: "image_only" if blocks[(f["document_id"], f["block_id"])]["image_only"] else "native_text", {"native_text", "image_only"}),
        "structure": score_structure(bundle.get("structure_reviews", []), docs, selected_ids),
        "release_audit": audit_results(bundle.get("results", []), docs, blocks, gold, selected_ids),
        "extraction_coverage": {},
        "limitations": ["Exact metrics cover selected labeled blocks, including reviewed negatives.",
                        "Overlap matches are diagnostic and do not raise exact recall.",
                        "Visual regions have separate bbox metrics and no text offsets.",
                        "Zero known residuals does not guarantee future documents contain no PII.",
                        "Source sample and synthetic results do not establish full-source accuracy."],
    }
    for did in sorted(selected_ids):
        doc = docs[did]
        expected = doc.get("expected_units", [])
        statuses = doc.get("unit_status", {})
        complete = sum(statuses.get(u) == "complete" for u in expected)
        report["extraction_coverage"][did] = {
            "expected_units": len(expected), "complete_units": complete,
            "coverage": complete / len(expected) if expected else None,
            "missing_or_incomplete_units": [u for u in expected if statuses.get(u) != "complete"],
            "extraction_complete": doc["extraction_complete"],
        }
    return report


def _percent(n):
    return "N/A" if n is None else f"{100*n:.2f}%"


def render_markdown(report):
    """Render aggregate evidence only. Never copy raw input into this report."""
    lines = ["# Independent evaluation report", "",
             f"Dataset: **{report['dataset_kind']}**. Split: **{report['split']}**.", "",
             "These results evaluate the supplied predictions. Synthetic predictions exercise the evaluator, not a working detector.", "",
             f"Evaluated blocks: {report['scope']['evaluated_blocks']}. Negative blocks: {report['scope']['negative_blocks']}. "
             f"Excluded provisional blocks: {report['scope']['excluded_unadjudicated_blocks']}.", ""]
    if report["provisional_labels_included"]:
        lines.extend(["**Provisional labels included. These metrics are exploratory.**", ""])
    for title, mapping in (("Exact occurrence and type metrics", {"Overall": report["exact_text"]}),
                           ("Per format", report["by_format"]), ("Per category", report["by_category"]),
                           ("Text origin", report["by_text_origin"]), ("Per document", report["by_document"]),
                           ("Source kind", report["by_source_kind"])):
        lines += ["## " + title, "", "| Group | TP | FP | FN | Gold | Predictions | Precision | Recall | F1 |",
                  "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for name, m in mapping.items():
            lines.append(f"| {name} | {m['tp']} | {m['fp']} | {m['fn']} | {m['gold_occurrences']} | {m['predicted_occurrences']} | {_percent(m['precision'])} | {_percent(m['recall'])} | {_percent(m['f1'])} |")
        lines.append("")
    for title, key in (("Text overlap diagnostic", "overlap_text_diagnostic"), ("Visual region detection", "visual_region_detection")):
        m = report[key]
        lines += ["## " + title, "", f"IoU threshold {m['iou_threshold']}. TP {m['tp']}, FP {m['fp']}, FN {m['fn']}. Recall {_percent(m['recall'])}.", ""]
    lines += ["## Structure and context", "", "Equal weights across applicable dimensions. Target: at least 80% per document. Text accuracy remains separate.", "",
              "| Document | Status | Structure | Meets target | Text accuracy |", "|---|---|---:|---|---:|"]
    for did, m in report["structure"].items():
        lines.append(f"| {did} | {m['status']} | {_percent(m['score'])} | {m['meets_80_percent']} | {_percent((m.get('text_accuracy') or {}).get('score'))} |")
    lines += ["", "## Extraction coverage", "", "| Document | Complete / expected units | Complete extraction |", "|---|---:|---|"]
    for did, m in report["extraction_coverage"].items():
        lines.append(f"| {did} | {m['complete_units']} / {m['expected_units']} | {m['extraction_complete']} |")
    lines += ["", "## Independent release audit", "", "| Document | Claimed status | Known residuals | Unsafe approval |", "|---|---|---:|---|"]
    for did, m in report["release_audit"].items():
        lines.append(f"| {did} | {m['status']} | {m['known_residual_occurrences']} | {m['unsafe_approval']} |")
    lines += ["", "## Limitations", ""] + ["- " + s for s in report["limitations"]]
    return "\n".join(lines) + "\n"
