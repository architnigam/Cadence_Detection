# src/cadence_detection/evaluation

Person 5: metrics and release checks.

Implemented: standard-library independent evaluator in `engine.py` and black-box contract checks in `pipeline_checks.py`. See `docs/team/person5_handoff.md` and `docs/team/evaluation_contract.md`. This component evaluates supplied findings/results; it does not implement extraction, detection, redaction or release approval.
