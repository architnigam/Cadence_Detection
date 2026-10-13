# tests/integration

Person 5: full pipeline and failure-path checks.

Implemented: evaluator and black-box runner contract regression tests. Run `python -m unittest discover -s tests/integration -p "test_*.py" -v` from the project root. The real pipeline is still pending. These tests check Person 5's QA code; generated real-format inputs are exercised against the pipeline only when `scripts/run_pipeline_checks.py --runner module:function` has an implemented adapter.
