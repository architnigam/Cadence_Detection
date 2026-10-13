# data/synthetic

Additional synthetic positive and negative fixtures.

Implemented: `evaluation_fixture.json` covers all 16 proposed entity types and deliberate misses/false positives/leakage. It exercises the evaluator, not detector accuracy. `pipeline_cases.json` defines twelve local file cases. Generate their inputs using `scripts/build_pipeline_inputs.py`; generated binaries stay local and can be rebuilt. See `docs/team/person5_handoff.md`.
