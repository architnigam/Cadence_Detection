# Actual local upload application

Run `python scripts/run_app.py --port 8767`, then open `http://127.0.0.1:8767`.

The frontend in index.html calls the real local runtime through cadence_detection.web. It accepts PDF/PPTX/DOCX, shows processing progress, findings and review warnings, and enforces approved-only plain-text export. No Streamlit installation or fixture substitution is required.
