"""Cadence Detection - Safe-Release Redaction and Live Demonstration Interface.

Gridline Console Edition: Redaction Engine, Privacy Gate, and Demonstration Interface.
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime

# Add project root to Python module path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
from src.cadence_detection.redaction.models import Block, Finding
from src.cadence_detection.redaction.redactor import TextRedactor
from src.cadence_detection.redaction.gate import SafeReleaseGate
from tests.redaction.fixtures import get_organizational_pack_fixture, get_risk_policy_fixture


# Page Configuration (Title, Favicon, Layout)
st.set_page_config(
    page_title="Cadence PII Redaction & Safe-Release Privacy Gate | Gridline Console",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Responsive Gridline Dark Theme
def apply_custom_css():
    bg_color = "#0a0f1d"
    card_bg = "#111827"
    text_color = "#f8fafc"
    sub_color = "#94a3b8"
    border_color = "rgba(255, 255, 255, 0.09)"
    primary_cyan = "#0ab1ba"

    css = f"""
    <style>
        /* Mobile overflow & horizontal scroll elimination */
        html, body, [data-testid="stAppViewContainer"] {{
            overflow-x: hidden !important;
            max-width: 100vw !important;
            word-break: break-word !important;
            background-color: {bg_color} !important;
            color: {text_color} !important;
        }}

        [data-testid="stSidebar"] {{
            background-color: #0b1120 !important;
            border-right: 1px solid {border_color} !important;
        }}
        
        /* Responsive code & text boxes */
        pre, code {{
            white-space: pre-wrap !important;
            word-wrap: break-word !important;
            overflow-x: hidden !important;
            background-color: #0a0f1d !important;
            border: 1px solid {border_color} !important;
            color: #cbd5e1 !important;
        }}

        /* Breadcrumb (Base-UI style) */
        .breadcrumb-box {{
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 0.8rem;
            font-family: monospace;
            color: {sub_color};
            margin-bottom: 12px;
        }}

        .breadcrumb-box a {{
            color: {sub_color};
            text-decoration: none;
        }}

        .breadcrumb-box a:hover {{
            color: {text_color};
        }}

        .breadcrumb-active {{
            background: {card_bg};
            border: 1px solid {border_color};
            padding: 2px 8px;
            border-radius: 4px;
            font-weight: 600;
            color: {text_color};
        }}

        /* Base-UI Badge7 Dot Badges */
        .badge-ghost {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 3px 10px;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 600;
            background-color: #1a2234;
            border: 1px solid rgba(255, 255, 255, 0.12);
            color: {text_color};
        }}

        .badge-dot {{
            width: 7px;
            height: 7px;
            border-radius: 50%;
            display: inline-block;
        }}

        .dot-primary {{ background-color: {primary_cyan}; box-shadow: 0 0 6px {primary_cyan}; }}
        .dot-success {{ background-color: #10b981; box-shadow: 0 0 6px #10b981; }}
        .dot-danger {{ background-color: #ef4444; box-shadow: 0 0 6px #ef4444; }}
        .dot-warning {{ background-color: #f59e0b; box-shadow: 0 0 6px #f59e0b; }}

        /* Avatar2 Component */
        .avatar-box {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 38px;
            height: 38px;
            border-radius: 50%;
            overflow: hidden;
            outline: 2px solid {primary_cyan};
            outline-offset: 2px;
            background-color: #1a2234;
        }}

        .avatar-box img {{
            width: 100%;
            height: 100%;
            object-fit: cover;
        }}

        /* Gridline Status Strip */
        .status-strip {{
            display: inline-flex;
            align-items: center;
            height: 28px;
            border-radius: 6px;
            background-color: #1a2234;
            border: 1px solid {border_color};
            font-family: monospace;
            font-size: 0.75rem;
            margin-bottom: 12px;
        }}

        .strip-item {{
            padding: 0 10px;
            display: flex;
            align-items: center;
            gap: 6px;
            border-right: 1px solid {border_color};
            color: {sub_color};
        }}

        .strip-item:last-child {{
            border-right: none;
        }}

        .strip-item.active {{
            color: {primary_cyan};
            font-weight: 600;
        }}

        /* Header Contact Ribbon */
        .incident-header {{
            background-color: {card_bg};
            border: 1px solid {border_color};
            border-radius: 10px;
            padding: 10px 16px;
            margin-bottom: 20px;
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 15px;
            font-size: 0.85rem;
            color: {text_color};
        }}

        .incident-header a {{
            color: {primary_cyan};
            text-decoration: none;
            font-weight: 600;
        }}

        .incident-header a:hover {{
            text-decoration: underline;
        }}

        .brand-logo-container {{
            display: flex;
            align-items: center;
            gap: 10px;
            text-decoration: none;
            color: {text_color};
            font-size: 1.4rem;
            font-weight: 800;
            margin-bottom: 5px;
        }}

        /* Gate Status Badges */
        .approved-banner {{
            background: linear-gradient(90deg, rgba(16, 185, 129, 0.12) 0%, rgba(10, 177, 186, 0.08) 100%);
            border: 1px solid rgba(16, 185, 129, 0.35);
            color: #a7f3d0;
            padding: 14px 18px;
            border-radius: 10px;
            margin-bottom: 20px;
        }}

        .quarantined-banner {{
            background: linear-gradient(90deg, rgba(239, 68, 68, 0.15) 0%, rgba(245, 158, 11, 0.08) 100%);
            border: 1px solid rgba(239, 68, 68, 0.4);
            color: #fecaca;
            padding: 14px 18px;
            border-radius: 10px;
            margin-bottom: 20px;
        }}

        /* Footer styling */
        .footer-container {{
            border-top: 1px solid {border_color};
            padding-top: 20px;
            margin-top: 40px;
            display: flex;
            flex-wrap: wrap;
            justify-content: space-between;
            align-items: center;
            gap: 15px;
            font-size: 0.8rem;
            font-family: monospace;
            color: {sub_color};
        }}

        .footer-container a {{
            color: {primary_cyan};
            text-decoration: none;
        }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def main():
    apply_custom_css()

    # Sidebar Navigation & Settings
    st.sidebar.markdown("""
    <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 15px;">
        <span style="font-size: 1.5rem; color: #0ab1ba;">🛡️</span>
        <div>
            <div style="font-size: 1.1rem; font-weight: 700; color: #f8fafc;">Cadence Privacy</div>
            <div style="font-size: 0.7rem; font-family: monospace; color: #94a3b8;">Gridline Console v2.4.2</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.sidebar.markdown("---")
    st.sidebar.header("📁 Evidence Ingestion")

    sample_choice = st.sidebar.selectbox(
        "Select Cadence Evidence File:",
        [
            "Cadence_Financial_Group_Organizational_Pack.pptx",
            "Cadence_Group_Risk_Management_Policy__v6.0.pdf",
            "Cadence_TPRM_Training.docx",
            "Simulate: Unredacted PII Leakage (Security Quarantine)",
            "Simulate: Incomplete Extraction / OCR Failure (Quality Quarantine)",
            "Trigger 404 / Missing Route Handler",
            "Upload Custom Evidence (.txt)"
        ]
    )

    st.sidebar.markdown("---")
    st.sidebar.header("⚙️ Gate Controls")
    min_confidence = st.sidebar.slider("Min OCR Quality Threshold:", 0.50, 0.95, 0.75, 0.05)
    token_style = st.sidebar.selectbox(
        "Token Placeholder Style:",
        ["[{entity_type}_{index}]", "<{entity_type}_{index}>", "REDACTED_{entity_type}"]
    )

    # Breadcrumb4 Component with Dot Separators
    st.markdown("""
    <div class="breadcrumb-box">
        <a href="#">Cadence Financial</a>
        <span style="opacity: 0.5;">•</span>
        <a href="#">Ingestion Partitions</a>
        <span style="opacity: 0.5;">•</span>
        <span class="breadcrumb-active">Safe-Release Privacy Gate</span>
    </div>
    """, unsafe_allow_html=True)

    # Clickable Logo Header with Avatar2 Profile
    st.markdown("""
    <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 15px; margin-bottom: 10px;">
        <a href="#home" class="brand-logo-container" id="brandLogo">
            <span>🛡️ Cadence Trust Boundary</span>
        </a>
        <div style="display: flex; align-items: center; gap: 12px;">
            <div class="avatar-box" title="Alex Rivera · Data Protection Officer">
                <img src="https://assets.watermelon.sh/wm_alex.png" alt="Alex Rivera">
            </div>
            <div style="line-height: 1.2;">
                <div style="font-size: 0.85rem; font-weight: 700; color: #f8fafc;">Alex Rivera</div>
                <div style="font-size: 0.7rem; color: #94a3b8; font-family: monospace;">DPO Officer · Tier 1</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Gridline Status Strip Pill
    st.markdown("""
    <div class="status-strip">
        <div class="strip-item active">
            <span style="width: 6px; height: 6px; border-radius: 50%; background-color: #0ab1ba; display: inline-block;"></span>
            Air Gap Ingestion
        </div>
        <div class="strip-item" style="color: #10b981;">
            <span style="width: 6px; height: 6px; border-radius: 50%; background-color: #10b981; display: inline-block;"></span>
            0 Leaks Detected
        </div>
        <div class="strip-item">
            Gate Tier 1 Active
        </div>
        <div class="strip-item" style="color: #0ab1ba;">
            Model v2.4.2 → v2.4.3
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Badge7 Ghost Dot Badges (color-coded by use case)
    st.markdown("""
    <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 12px;">
        <span class="badge-ghost">
            <span class="badge-dot dot-primary"></span>
            Enterprise Trust Boundary
        </span>
        <span class="badge-ghost">
            <span class="badge-dot dot-success"></span>
            Air-Gapped Local Storage
        </span>
        <span class="badge-ghost">
            <span class="badge-dot dot-warning"></span>
            Case Study 2
        </span>
    </div>
    """, unsafe_allow_html=True)

    st.title("Cadence PII Redaction & Safe-Release Privacy Gate")
    st.caption("Gridline Dashboard Console · Automated Tokenization & Privacy Gate Enforcement")

    # Clickable Incident Contact Bar
    st.markdown("""
    <div class="incident-header">
        <span><strong>Accountable Officer:</strong> Alex Rivera (DPO)</span>
        <span>·</span>
        <span><strong>Direct Email:</strong> <a href="mailto:dpo@cadence.com">✉️ dpo@cadence.com</a></span>
        <span>·</span>
        <span><strong>Security Hotline:</strong> <a href="tel:+15550188">📞 +1 (555) 0188</a></span>
        <span>·</span>
        <span><strong>Location:</strong> Wall Street, New York, NY</span>
    </div>
    """, unsafe_allow_html=True)

    # Custom 404 Handler View
    if sample_choice == "Trigger 404 / Missing Route Handler":
        st.markdown("""
        <div style="text-align: center; padding: 50px 20px; background: rgba(239, 68, 68, 0.1); border: 1px solid #ef4444; border-radius: 12px; margin: 30px 0;">
            <h1 style="font-size: 4rem; color: #ef4444; margin-bottom: 10px;">404</h1>
            <h2>Document Partition Not Found</h2>
            <p style="color: #94a3b8; max-width: 500px; margin: 10px auto 25px auto;">
                The requested evidence path does not exist within the Cadence local trust boundary.
            </p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("⬅️ Return to Default Dashboard"):
            st.toast("Navigated back to safe dashboard", icon="✅")
            st.rerun()
        return

    # Initialize Engine
    format_template = "[{entity_type}_{index}]" if "{" in token_style else f"[{token_style}]"
    redactor = TextRedactor(token_format=format_template)
    gate = SafeReleaseGate(min_ocr_confidence=min_confidence)

    # Load Chosen Document Fixtures
    if sample_choice == "Cadence_Financial_Group_Organizational_Pack.pptx":
        blocks, findings = get_organizational_pack_fixture()
        doc_format = "PPTX (9 Slides · RACI Matrices)"
    elif sample_choice == "Cadence_Group_Risk_Management_Policy__v6.0.pdf":
        blocks, findings = get_risk_policy_fixture()
        doc_format = "PDF (35 Scanned Pages · Sec 16.5)"
    elif sample_choice == "Cadence_TPRM_Training.docx":
        blocks = [
            Block(
                document_id="cadence_tprm_training",
                block_id="b_table5_users",
                page_or_slide=5,
                source_kind="docx_table",
                reading_order=1,
                text="Vendor Auditor: Sarah Jenkins (sarah.jenkins@onrust-audit.com, +1 (555) 0142). Assigned Tier 2 review.",
                extraction_complete=True
            )
        ]
        findings = [
            Finding("cadence_tprm_training", "b_table5_users", "PERSON", 16, 29, 0.98, "ner"),
            Finding("cadence_tprm_training", "b_table5_users", "EMAIL", 31, 58, 0.99, "regex"),
            Finding("cadence_tprm_training", "b_table5_users", "PHONE", 60, 75, 0.95, "phone_catalog")
        ]
        doc_format = "DOCX (TPRM Training · 16 Tables)"
    elif "PII Leakage" in sample_choice:
        blocks = [
            Block(
                document_id="leaky_demo",
                block_id="b_leak_1",
                page_or_slide=1,
                source_kind="unredacted_memo",
                reading_order=1,
                text="Confidential incident note: Employee contact elena.rostova@cadence.com and phone +1 (555) 0188 were missed by primary recognizer.",
                extraction_complete=True
            )
        ]
        findings = []  # Empty findings intentionally triggers gate
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
                extraction_complete=False,
                OCR_confidence=0.42
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
            doc_format = "Custom File Upload"
            st.toast("Custom evidence file loaded successfully", icon="✅")
        else:
            st.info("👈 Please select or upload a document in the sidebar to begin.")
            return

    # Process Document with Redaction & Gate
    sanitized_blocks, token_mapping, category_counts = redactor.redact_document(blocks, findings)
    gate_result = gate.evaluate(sanitized_blocks)

    # Status Banner
    if gate_result.status == "APPROVED":
        st.markdown(f"""
        <div class="approved-banner">
            <h3 style="margin-bottom: 5px;">🟢 SAFE FOR DOWNSTREAM LLM INGESTION (APPROVED)</h3>
            <p style="margin: 0; font-size: 0.95rem;">{gate_result.reason}</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="quarantined-banner">
            <h3 style="margin-bottom: 5px;">⛔ SECURITY GATE VIOLATION (QUARANTINED)</h3>
            <p style="margin: 0; font-size: 0.95rem;">{gate_result.reason}</p>
        </div>
        """, unsafe_allow_html=True)

    # Key Metrics Row
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Source Format", doc_format.split(" ")[0])
    with m2:
        st.metric("Blocks Processed", len(blocks))
    with m3:
        st.metric("PII Entities Masked", sum(category_counts.values()))
    with m4:
        st.metric("Residual Leaks Detected", gate_result.residual_pii_count)

    st.markdown("---")

    # Side-by-Side Comparison
    st.subheader("🔍 Redaction Verification Comparison")
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("#### 📄 Original Evidence Text")
        for b in blocks:
            st.caption(f"Block `{b.block_id}` (Page/Slide {b.page_or_slide}):")
            st.code(b.text, language="text")

    full_sanitized_text = ""
    with col_right:
        st.markdown("#### 🔒 Sanitized Text (Safe for LLM)")
        for b in sanitized_blocks:
            st.caption(f"Block `{b.block_id}` (Sanitized):")
            st.code(b.text, language="text")
            full_sanitized_text += f"{b.text}\n\n"

    # Action Toolbar
    st.markdown("---")
    btn_col1, btn_col2 = st.columns([1, 4])
    with btn_col1:
        st.download_button(
            label="📥 Download Sanitized Text (.txt)",
            data=full_sanitized_text,
            file_name=f"sanitized_{blocks[0].document_id}.txt",
            mime="text/plain",
            disabled=(gate_result.status != "APPROVED"),
            on_click=lambda: st.toast("Sanitized file downloaded successfully!", icon="✅")
        )
    with btn_col2:
        if gate_result.status != "APPROVED":
            st.error("⚠️ Download is disabled because the document failed the privacy gate.")

    # Breakdown Tabs
    t1, t2, t3 = st.tabs(["📊 Category Breakdown", "🔑 Stable Token Mapping", "⚠️ Quality Warnings"])
    with t1:
        if category_counts:
            st.json(category_counts)
        else:
            st.info("No PII entity categories recorded for this partition.")
    with t2:
        if token_mapping:
            mapping_display = [{"Original String (Restricted)": k, "Assigned Stable Token": v} for k, v in token_mapping.items()]
            st.table(mapping_display)
        else:
            st.info("Zero token substitutions recorded.")
    with t3:
        if gate_result.residual_findings:
            st.error("Residual PII patterns intercepted by secondary scanner:")
            st.json(gate_result.residual_findings)
        elif gate_result.warnings:
            for w in gate_result.warnings:
                st.warning(w)
        else:
            st.success("All quality and privacy gate checks passed without warnings.")

    # Dynamic Footer
    current_year = datetime.now().year
    st.markdown(f"""
    <div class="footer-container">
        <div>
            © {current_year} Cadence Financial Group · Gridline Enterprise Console.
        </div>
        <div>
            <a href="mailto:dpo@cadence.com">Contact DPO</a> · 
            <a href="tel:+15550188">Incident Hotline</a> · 
            <a href="#brandLogo">Back to Top ↑</a>
        </div>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
