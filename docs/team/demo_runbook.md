# Demonstration Runbook & Walkthrough Script

**Component:** Redaction Engine, Privacy Gate, and Live Demonstration  
**Presentation Slot:** ~4 minutes during stakeholder walkthrough  
**Artifacts:** `src/cadence_detection/redaction/`, `tests/redaction/`, `app/app.py`, `output/redacted/`

---

## 1. Quick Launch Instructions
To launch the interactive demonstration application locally on your machine:

```bash
# In the repository root:
streamlit run app/app.py
```
This automatically opens the live web dashboard at `http://localhost:8501`.

---

## 2. 4-Minute Presentation Script & Flow

### Minute 1: The Trust Boundary & Safe-Release Philosophy (Slide Context)
> *"Welcome everyone. I'm presenting the Redaction Engine and Privacy Gate for Cadence.  
> Our primary objective is ensuring that **zero sensitive financial or personal data ever reaches an external LLM** while preserving enough text context so the model can still understand business meaning.  
> Rather than just blanking out text, we implemented two key innovations:  
> 1. **Stable Document-Local Placeholders**: Recurring individuals like our Chief Risk Officer or DPO receive identical tokens (such as `[PERSON_1]`), preserving relationship context without exposing identity.  
> 2. **The Safe-Release Gate**: A strict verification boundary that quarantines incomplete extractions or suspicious residuals instead of assuming the detector was 100% perfect."*

### Minute 2: Live Demo — Cadence Organizational Pack (PPTX)
- **Action**: Select `Cadence_Financial_Group_Organizational_Pack.pptx` in the sidebar dropdown.
- **Explain**:
  - Show the 🟢 **APPROVED** badge.
  - Point to the side-by-side view: Chief Risk Officer Marcus Vance and DPO Elena Rostova are cleanly masked.
  - Highlight the phone numbers (`+1 (555) 0114`) and corporate emails (`@cadence.com`).
  - Point out that on Slide 6 (the RACI matrix), Elena Rostova and Marcus Vance map to the exact same tokens as Slide 2, proving relational stability.

### Minute 3: Live Demo — Risk Management Policy v6.0 (Scanned PDF)
- **Action**: Select `Cadence_Group_Risk_Management_Policy__v6.0.pdf` in the dropdown.
- **Explain**:
  - Point out the handling of Section 16.5 incident narratives, employee ID (`EMP-49821`), and customer bank account numbers (`ACC-910283`).
  - Demonstrate that surrounding punctuation, paragraph structure, and non-PII terms remain intact.
  - Show the **"Download Sanitized Safe Derivative"** button enabling clean ingestion by downstream LLMs.

### Minute 4: The Hero Feature — Demonstrating the Quarantine Fail-Safe
- **Action**: Select `Simulate: Unredacted PII Leakage (Security Gate Failure)` in the sidebar.
- **Explain**:
  - Show the instant switch to ⛔ **QUARANTINED — DOWNSTREAM ACCESS BLOCKED**.
  - Show that the download button is immediately disabled to prevent data leakage.
  - Explain: *"If an OCR misread or edge-case finding escapes upstream models, our conservative secondary scanner catches it at the gate and halts downstream release for human triage."*

---

## 3. Architecture & Algorithm Details
1. **Deterministic Overlap Resolution**: Sorts findings by start offset ascending, prioritizing longest span and highest confidence to avoid corrupted text slices.
2. **Reverse Offset Substitution**: Replaces text spans in descending order of `start` index so subsequent character positions remain mathematically valid.
3. **Local Identity Registry**: Sensitive original identity strings and token registries are held in transient memory and never written to routine unencrypted log files.
4. **Verification Gate Criteria**:
   - `APPROVED`: 100% extraction complete, zero residual regex patterns, OCR confidence $\ge 0.65$.
   - `QUARANTINED`: Residual pattern detected or upstream extraction flagged incomplete (e.g., unsupported media format).
   - `FAILED`: Document corrupt or unparseable.
