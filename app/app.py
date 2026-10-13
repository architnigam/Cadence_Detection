"""Cadence Detection - Safe-Release Redaction and Live Demonstration Interface.

Redaction Engine, Privacy Gate, and Demonstration Interface.
"""

import sys
import os
import json
from pathlib import Path

# Add project root to Python module path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
from src.cadence_detection.redaction.models import Block, Finding
from src.cadence_detection.redaction.redactor import TextRedactor
from src.cadence_detection.redaction.gate import SafeReleaseGate
from tests.redaction.fixtures import get_organizational_pack_fixture, get_risk_policy_fixture


# Set Streamlit Page Config
st.set_page_config(
    page_title="Cadence PII Redaction & Privacy Gate",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 15px;
        border-left: 5px solid #0d6efd;
    }
    .approved-badge {
        background-color: #d1e7dd;
        color: #0f5132;
        padding: 8px 16px;
        border-radius: 6px;
        font-weight: bold;
        font-size: 1.1rem;
        display: inline-block;
    }
    .quarantined-badge {
        background-color: #f8d7da;
        color: #842029;
        padding: 8px 16px;
        border-radius: 6px;
        font-weight: bold;
        font-size: 1.1rem;
        display: inline-block;
    }
</style>
""", unsafe_allow_html=True)


def main():
    st.title("🛡️ Cadence PII Detection & Safe-Release Privacy Gate")
    st.caption("Case Study 2 · Downstream LLM Redaction Boundary · Privacy Gate Dashboard")

    # Sidebar: Document Ingestion & Mode Selection
    st.sidebar.header("📁 Document Ingestion")

    sample_choice = st.sidebar.selectbox(
        "Choose Cadence Evidence Document:",
        [
            "Cadence_Financial_Group_Organizational_Pack.pptx",
            "Cadence_Group_Risk_Management_Policy__v6.0.pdf",
            "Simulate: Unredacted PII Leakage (Security Gate Failure)",
            "Simulate: Incomplete Extraction / OCR Failure (Quality Gate Failure)",
            "Upload Custom Text (.txt)"
        ]
    )

    st.sidebar.markdown("---")
    st.sidebar.header("⚙️ Gate Configuration")
    min_confidence = st.sidebar.slider("Min OCR Confidence Threshold:", 0.50, 0.95, 0.65, 0.05)
    token_style = st.sidebar.selectbox(
        "Placeholder Token Format:",
        ["[{entity_type}_{index}]", "<{entity_type}_{index}>", "REDACTED_{entity_type}"]
    )

    # Initialize modules
    format_template = "[{entity_type}_{index}]" if "{" in token_style else f"[{token_style}]"
    redactor = TextRedactor(token_format=format_template)
    gate = SafeReleaseGate(min_ocr_confidence=min_confidence)

    # Load Document Data based on selection
    if sample_choice == "Cadence_Financial_Group_Organizational_Pack.pptx":
        blocks, findings = get_organizational_pack_fixture()
        doc_format = "PPTX (9 Slides · Org Charts & RACI Matrices)"
    elif sample_choice == "Cadence_Group_Risk_Management_Policy__v6.0.pdf":
        blocks, findings = get_risk_policy_fixture()
        doc_format = "PDF (35 Scanned Pages · Risk Policy v6.0 OCR)"
    elif "PII Leakage" in sample_choice:
        blocks = [
            Block(
                document_id="leaky_demo",
                block_id="b_leak_1",
                page_or_slide=1,
                source_kind="unredacted_memo",
                reading_order=1,
                text="Direct confidential memo: DPO contact elena.rostova@cadence.com and phone +1 (555) 0188 escaped the primary detector.",
                extraction_complete=True
            )
        ]
        findings = []  # Upstream detector missed findings to test the gate
        doc_format = "Synthetic Security Failure Test"
    elif "Incomplete Extraction" in sample_choice:
        blocks = [
            Block(
                document_id="incomplete_demo",
                block_id="b_dropped_media",
                page_or_slide=4,
                source_kind="docx_embedded_image",
                reading_order=1,
                text="Vendor onboarding architecture diagram (EMF image format not fully rendered).",
                extraction_complete=False,  # Dropped content
                OCR_confidence=0.45
            )
        ]
        findings = []
        doc_format = "Synthetic Completeness Failure Test"
    else:
        uploaded_file = st.sidebar.file_uploader("Upload .txt File", type=["txt"])
        if uploaded_file is not None:
            raw_text = uploaded_file.read().decode("utf-8")
            blocks = [
                Block(
                    document_id="uploaded_custom",
                    block_id="b_custom_1",
                    page_or_slide=1,
                    source_kind="custom_upload",
                    reading_order=1,
                    text=raw_text,
                    extraction_complete=True
                )
            ]
            findings = []
            doc_format = "Custom Text Upload"
        else:
            st.info("👈 Please select or upload a document in the sidebar to begin.")
            return

    # Process Document
    sanitized_blocks, token_mapping, category_counts = redactor.redact_document(blocks, findings)
    gate_result = gate.evaluate(sanitized_blocks)

    # Top Status Banner
    st.markdown("### 🚦 Privacy Gate Status")
    if gate_result.status == "APPROVED":
        st.markdown(
            f"""<div class="approved-badge">🟢 APPROVED FOR DOWNSTREAM LLM</div>
            <p style="margin-top: 8px; color: #198754;"><b>Verification Passed:</b> {gate_result.reason}</p>""",
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            f"""<div class="quarantined-badge">⛔ QUARANTINED — DOWNSTREAM ACCESS BLOCKED</div>
            <p style="margin-top: 8px; color: #dc3545;"><b>Violation Detected:</b> {gate_result.reason}</p>""",
            unsafe_allow_html=True
        )

    # Key Metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Source Format", doc_format.split(" ")[0])
    with col2:
        st.metric("Blocks Processed", len(blocks))
    with col3:
        st.metric("Total PII Masked", sum(category_counts.values()))
    with col4:
        st.metric("Residual Leaks Detected", gate_result.residual_pii_count)

    st.markdown("---")

    # Side-by-Side Comparison
    st.subheader("🔍 Redaction Verification Comparison")
    left_col, right_col = st.columns(2)

    with left_col:
        st.markdown("#### 📄 Original Evidence Text")
        for b in blocks:
            st.markdown(f"**Block `{b.block_id}` (Page/Slide {b.page_or_slide}):**")
            st.code(b.text, language="text")

    with right_col:
        st.markdown("#### 🔒 Sanitized Text (Safe for LLM)")
        full_sanitized_text = ""
        for b in sanitized_blocks:
            st.markdown(f"**Block `{b.block_id}` (Sanitized):**")
            st.code(b.text, language="text")
            full_sanitized_text += f"{b.text}\n\n"

    # Entities and Tokens Section
    st.markdown("---")
    tab1, tab2, tab3 = st.tabs(["📊 Entity Breakdown", "🔑 Stable Placeholder Map", "⚠️ Security Warnings & Residuals"])

    with tab1:
        if category_counts:
            st.write("**Detected & Classified PII Categories:**")
            st.json(category_counts)
        else:
            st.write("No PII findings passed for this document.")

    with tab2:
        st.write("**Document-Local Token Mapping (Maintained strictly inside local memory boundary):**")
        if token_mapping:
            mapping_display = [{"Original Identity (Restricted Local)": k, "Assigned Stable Token": v} for k, v in token_mapping.items()]
            st.table(mapping_display)
        else:
            st.write("No entity replacements recorded.")

    with tab3:
        if gate_result.residual_findings:
            st.error(f"Potential residual PII detected by conservative gate scanner:")
            st.json(gate_result.residual_findings)
        elif gate_result.warnings:
            st.warning("Warnings flagged during verification:")
            for w in gate_result.warnings:
                st.write(f"- {w}")
        else:
            st.success("Zero residual PII or completeness warnings. Safe-release boundary intact.")

    # Export sanitized file
    st.markdown("---")
    st.download_button(
        label="📥 Download Sanitized Safe Derivative (.txt)",
        data=full_sanitized_text,
        file_name=f"sanitized_{blocks[0].document_id}.txt",
        mime="text/plain",
        disabled=(gate_result.status != "APPROVED")
    )
    if gate_result.status != "APPROVED":
        st.caption("⚠️ Download is disabled because the document is quarantined.")


if __name__ == "__main__":
    main()
