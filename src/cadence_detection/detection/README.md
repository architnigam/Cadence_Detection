# src/cadence_detection/detection

Person 3: recognizers, classification and span resolution.

Status: increment 1 implemented (Person 3).

## Modules

- `pii_detector.py` – Baseline EMAIL, contextual PHONE, and synthetic EMPLOYEE_ID
  detection.  Stdlib-only; no third-party dependencies.  See module docstring for
  open ambiguities (source_location format, overlap policy, real EMPLOYEE_ID
  pattern) that require review by Person 1 / Person 4 before the next increment.
