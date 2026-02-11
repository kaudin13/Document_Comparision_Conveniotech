import html
import os
import re
import streamlit as st

st.markdown("""
<style>

/* ===== PAGE BACKGROUND ===== */
.stApp {
    background-color: #f5f7fb;
    color: #1f2937;
}

/* ===== TITLE ===== */
h1 {
    color: #1e3a8a !important;
    font-weight: 700;
}

/* ===== TEXT FIX (white text bug) ===== */
* {
    color: #1f2937 !important;
}

/* ===== FILE UPLOADER BOX ===== */
section[data-testid="stFileUploader"] {
    background: white !important;
    border: 2px solid #2563eb !important;
    border-radius: 12px !important;
    padding: 18px !important;
}

/* Drag & drop bar */
[data-testid="stFileUploaderDropzone"] {
    background: #eaf1ff !important;
    border: 2px dashed #2563eb !important;
    border-radius: 10px !important;
    padding: 30px !important;
}

/* Browse files button */
[data-testid="stFileUploader"] button {
    background-color: #2563eb !important;
    color: white !important;
    border-radius: 8px !important;
    border: none !important;
    font-weight: 600 !important;
}

[data-testid="stFileUploader"] button:hover {
    background-color: #1e40af !important;
}

/* Uploaded filename text fix */
[data-testid="stFileUploader"] span {
    color: #1f2937 !important;
}

/* ===== PRIMARY BUTTON ===== */
.stButton > button {
    background-color: #2563eb !important;
    color: white !important;
    border-radius: 10px !important;
    padding: 10px 20px !important;
    font-weight: 600 !important;
    border: none !important;
}

.stButton > button:hover {
    background-color: #1e40af !important;
}


/* ===== MAIN CARD ===== */
.change-card {
    background: white;
    border-radius: 14px;
    border: 1px solid #e5e7eb;
    padding: 22px;
    margin-top: 18px;
    margin-bottom: 18px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}

/* Force markdown text inside card */
.change-card p,
.change-card div,
.change-card span {
    color: #1f2937 !important;
    margin-bottom: 8px;
}

/* ===== SECTION LABELS ===== */
.change-card strong {
    color: #1e3a8a;
}

/* ===== EXPANDER HEADER ===== */
details summary {
    background: #eaf1ff !important;
    border-radius: 10px;
    padding: 10px 14px;
    font-weight: 600;
    color: #1e3a8a !important;
    border: 1px solid #dbeafe;
}

/* ===== EXPANDER BODY ===== */
details[open] {
    background: #f9fbff !important;
    border-radius: 12px;
    padding: 14px;
    border: 1px solid #dbeafe;
    margin-top: 10px;
}

/* ===== INNER CARD (old/new text) ===== */
.inner-card {
    background: white;
    border-radius: 10px;
    border: 1px solid #e5e7eb;
    padding: 14px;
    margin-top: 10px;
}

/* ===== HIGHLIGHT ===== */
mark {
    background-color: #dbeafe;
    padding: 2px 4px;
    border-radius: 3px;
}

/* ===== SUCCESS BOX ===== */
[data-testid="stAlert"] {
    border-radius: 10px !important;
}
            
/* File uploader label text color */
label[data-testid="stFileUploaderLabel"] {
    color: #1e3a8a !important;   /* blue formal */
    font-weight: 600;
}

/* Optional: make it slightly bigger */
label[data-testid="stFileUploaderLabel"] p {
    color: #1e3a8a !important;
    font-size: 15px;
}

/* Uploaded file name text (ui_input/old.pdf etc.) */
[data-testid="stFileUploader"] span {
    color: #1e3a8a !important;   /* formal blue */
    font-weight: 600 !important;
}

/* Small file path text */
[data-testid="stFileUploader"] small {
    color: #475569 !important;   /* softer grey-blue */
    font-weight: 500 !important;
}

/* File icon color */
[data-testid="stFileUploader"] svg {
    fill: #2563eb !important;
}

/* Remove white-on-white bug */
[data-testid="stFileUploader"] * {
    color: #1f2937 !important;
}

</style>
""", unsafe_allow_html=True)


from scripts.extract_text_unified import extract_text
from scripts.parse_sections import parse_sections
from scripts.compare_sections import compare_sections
from scripts.generate_ai_summary import generate_change_summary


DISPLAY_CHANGE_MAP = {
    "New rule added": "Added",
    "Rule removed": "Removed",
    "Numeric limit changed": "Modified",
    "Operational requirement changed": "Modified",
    "Applicability changed": "Modified",
}

HIGHLIGHT_REGEX = re.compile(
    r"(\b\d{1,2}:\d{2}\b(?:\s*(?:hours?|hrs?|minutes?|mins?|days?|landings?))?"
    r"|\b\d+(?:\.\d+)?\s*(?:hours?|hrs?|minutes?|mins?|days?|landings?)\b"
    r"|\b\d+(?:\.\d+)?\b"
    r"|\bnow\s+requires\b"
    r"|\bno\s+longer\b"
    r"|\bincrease(?:d|s)?\b"
    r"|\bdecrease(?:d|s)?\b"
    r"|\breduced\b"
    r"|\badded\b"
    r"|\bremoved\b"
    r"|\bextended\b"
    r"|\blimits?\b)",
    flags=re.IGNORECASE,
)


def highlight_summary(summary: str) -> str:
    safe_text = html.escape((summary or "").strip())

    def _mark(match: re.Match) -> str:
        return f"<mark>{match.group(0)}</mark>"

    return HIGHLIGHT_REGEX.sub(_mark, safe_text)


st.set_page_config(page_title="Tool for Document Comparison", layout="wide")

st.title("Comparison Tool")
st.write("Upload old and new Documents to detect meaningful regulatory changes.")

col1, col2 = st.columns(2)

with col1:
    st.write("**UPLOAD OLD DOCUMENT**")
    old_pdf = st.file_uploader(
        "Old version document",
        type=["pdf"],
        key="old_doc",
        
    )

with col2:
    st.write("**UPLOAD NEW DOCUMENT**")
    new_pdf = st.file_uploader(
        "New version document",
        type=["pdf"],
        key="new_doc",
        label_visibility="collapsed"
    )

if st.button("View Results"):
    if not old_pdf or not new_pdf:
        st.error("Please upload both old and new Document files.")
    else:
        os.makedirs("ui_input", exist_ok=True)
        os.makedirs("ui_output", exist_ok=True)

        old_pdf_path = "ui_input/old.pdf"
        new_pdf_path = "ui_input/new.pdf"

        with open(old_pdf_path, "wb") as f:
            f.write(old_pdf.getbuffer())

        with open(new_pdf_path, "wb") as f:
            f.write(new_pdf.getbuffer())

        with st.spinner("Processing documents..."):
            extract_text(old_pdf_path, "ui_output/old.txt")
            extract_text(new_pdf_path, "ui_output/new.txt")

            with open("ui_output/old.txt", encoding="utf-8") as f:
                old_text = f.read()
            with open("ui_output/new.txt", encoding="utf-8") as f:
                new_text = f.read()

            old_sections = parse_sections(old_text)
            new_sections = parse_sections(new_text)
            changes = compare_sections(
                old_sections,
                new_sections,
                strict_mode=True,
                include_non_true=False,
            )

        true_changes = [c for c in changes if c.get("type") == "TRUE_CHANGE"]

        if not true_changes:
            st.info("No meaningful regulatory changes detected.")
        else:
            st.success(f"Detected {len(true_changes)} true regulatory changes")

            for change in true_changes:
                subtype = change.get("subtype", "")
                display_change = DISPLAY_CHANGE_MAP.get(subtype, "Modified")

                old_section = change.get("old_section", "") or "-"
                new_section = change.get("new_section", "") or "-"
                old_rule = (change.get("old_text", "") or "").strip()
                new_rule = (change.get("new_text", "") or "").strip()

                summary = generate_change_summary(old_rule, new_rule, subtype)
                highlighted_summary = highlight_summary(summary)

                # --- MAIN CARD START ---
                st.markdown(f"""
                <div class="change-card">
                    <p><strong>CHANGE:</strong> {display_change}</p>
                    <p><strong>OLD_SECTION:</strong> {old_section}</p>
                    <p><strong>NEW_SECTION:</strong> {new_section}</p>
                    <p><strong>SUMMARY:</strong> {highlighted_summary}</p>
                </div>
                """, unsafe_allow_html=True)

                # --- EXPANDER ---
                with st.expander("View old and new text", expanded=False):
                    st.markdown(f"""
                    <div class="inner-card">
                        <p><strong>OLD_TEXT:</strong> {old_rule if old_rule else '-'}</p>
                        <p><strong>NEW_TEXT:</strong> {new_rule if new_rule else '-'}</p>
                    </div>
                    """, unsafe_allow_html=True)

                st.divider()

