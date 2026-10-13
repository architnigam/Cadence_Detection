# Local QA walkthrough and demo fallback

This runbook covers Person 5's reliability evidence. It does not stand in for the required team live upload/extraction/detection demonstration.

1. Show the synthetic fixture's scope: all values are invented and predictions are deliberately imperfect. Run the evaluator locally.
2. Show exact metrics with TP/FP/FN and denominators. Explain why partial matches remain misses in exact scoring.
3. Show native-text versus image-only recall, then the separate visual-region metric.
4. Show the structure rubric and its source-check denominators. Explain why structure and OCR accuracy remain separate.
5. Show the deliberately surviving passport count and unsafe approval flag. Do not display real source values in routine reports.
6. Show local source review inventory and pending adjudication. Clearly state that real detector accuracy remains unmeasured until integration.
7. When the full pipeline is available, run all twelve black-box file cases and record safe screenshots of approved/quarantined/failed states. Capture a short local recording of all three real uploads using sanitized outputs.

If the live demo fails, use the most recent verified sanitized report/screenshots/recording. Label the evidence with the actual code/gold version and run date. Never present synthetic results as the real pipeline, or unexecuted checks as passed. Currently no full-pipeline recording/screenshots exist because the pipeline is pending.
