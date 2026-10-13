"""Black-box pipeline contract checks. Runner belongs to Person 1's integration."""

from pathlib import Path


def check_case(case, runner, input_dir):
    """runner(Path) returns the agreed result plus a downstream_called boolean.

    Unexpected exceptions count as failures and their messages stay out of logs.
    The runner must run locally and must never call an actual external LLM.
    """
    path = Path(input_dir) / case["filename"]
    if not path.is_file():
        return {"case_id": case["case_id"], "status": "not_run", "reasons": ["input_not_generated"]}
    try:
        result = runner(path)
    except Exception:
        return {"case_id": case["case_id"], "status": "failed", "reasons": ["unhandled_pipeline_exception"]}
    reasons = []
    if not isinstance(result, dict):
        return {"case_id": case["case_id"], "status": "failed", "reasons": ["invalid_result_contract"]}
    status = result.get("status")
    if status not in case["allowed_statuses"]:
        reasons.append("unexpected_status")
    called = result.get("downstream_called")
    if not isinstance(called, bool):
        reasons.append("missing_downstream_instrumentation")
    if case["must_block_downstream"] and called is not False:
        reasons.append("downstream_not_blocked")
    sanitized = result.get("sanitized_blocks")
    if not isinstance(sanitized, list) or any(not isinstance(b, dict) or not isinstance(b.get("text"), str) for b in sanitized):
        reasons.append("invalid_sanitized_blocks")
        sanitized = []
    text = "\n".join(b["text"] for b in sanitized)
    if any(value.casefold() in text.casefold() for value in case.get("forbidden_literals", [])):
        reasons.append("known_synthetic_pii_survives")
    if status == "approved":
        if result.get("extraction_complete") is not True:
            reasons.append("approval_without_complete_extraction")
        if result.get("verification_passed") is not True:
            reasons.append("approval_without_verification")
        if type(result.get("remaining_candidate_count")) is not int or result["remaining_candidate_count"] != 0:
            reasons.append("approval_with_unresolved_candidates")
        if not sanitized or not text.strip():
            reasons.append("approval_without_content")
    return {"case_id": case["case_id"], "status": "failed" if reasons else "passed", "reasons": reasons}
