1) PS (Problem Statement)
The problem statement is to build a regulatory document comparison tool for DGCA circulars/manuals that:

accepts an Old version document and New version document,
extracts structured content from both,
compares them semantically (not just line-by-line),
detects meaningful changes relevant to operational compliance,
and presents the changes in a readable UI for quick review.
The core challenge is avoiding false positives from:

section renumbering,
formatting changes,
reordered content,
and OCR noise.
2) Project Objective and Approach
Objective
Create a reliable “old vs new” DGCA document change detection system focused on operationally meaningful differences.

Current Approach (Pipeline)
Upload documents in UI
via Streamlit (app.py).

Extract text from PDFs
using hybrid path:

text-based extraction (pdfplumber)
OCR extraction (pytesseract + pdf2image) for scanned PDFs
in extract_text_unified.py.
Parse into logical sections

detect headings/section IDs,
strip noise/TOC/page artifacts,
build structured section objects
in parse_sections.py.
Build semantic meaning blocks

pick important regulatory sentences (modal words + numeric phrases)
in meaning_block.py.
Compare old vs new sections semantically

section-independent matching,
numeric/applicability/operational change categorization,
dedup and validation layers
in compare_sections.py using semantic_utils.py.
Generate concise operational summary
per detected change subtype in generate_ai_summary.py.

Render final results in UI

card view with change type, section references, summary, expandable details
in app.py.
3) Technology Used / Using / Learning
Language + App Framework
Python
Streamlit
PDF / OCR Stack
pdfplumber (text PDF extraction)
pdf2image (PDF page to image conversion)
pytesseract (OCR for scanned docs)
system Tesseract binaries (present in repo)
NLP / Similarity Stack
regex-based rule extraction
difflib.SequenceMatcher for lexical similarity
token/Jaccard similarity
optional transformer embeddings through sentence-transformers (enabled via env var)
spaCy (en_core_web_sm) for sentence segmentation and meaning block extraction
ML/NLP Libraries in environment
transformers
sentence-transformers
torch
spacy
plus support libs in requirements.txt
4) File-by-File Documentation
Main UI
app.py
Responsibilities:
Streamlit UI rendering and CSS theme.
Upload old/new documents.
Run extraction → parsing → comparison.
Map internal subtype to user-facing Added/Removed/Modified.
Highlight key values in summaries.
Render result cards and expandable old/new text blocks.
Comparison Engine
compare_sections.py
Core intelligence layer:
section-independent matching,
semantic + lexical pair scoring,
change classification (TRUE_CHANGE, structural/minor/noise internal categories),
numeric change gating,
applicability/operational change detection,
dedupe + validation + over-detection control.
Section Parser
parse_sections.py
Converts raw extracted text into structured sections:
identifies numbered headings and uppercase headings,
removes TOC/header/footer-like noise,
builds section dict with section, heading, body, meaning.
Meaning Extraction
meaning_block.py
Creates compressed “meaning block”:
filters to high-signal regulatory sentences (shall/must/limits/numbers),
spaCy sentence split with fallback regex split.
Semantic Utilities
semantic_utils.py
Similarity primitives:
normalize/tokenize,
lexical similarity (SequenceMatcher + Jaccard),
optional embedding similarity (ENABLE_EMBEDDINGS=1),
final semantic similarity blending.
Summary Generator
generate_ai_summary.py
Generates concise change summaries based on change subtype:
numeric change summary,
applicability summary,
add/remove/modify summary templates.
(Current version is deterministic, not model-sampled summarization.)
Text Extraction Module
extract_text_unified.py
Detects scanned vs text PDF and extracts accordingly:
is_scanned_pdf
extract_text_pdfplumber
extract_text_ocr
unified extract_text orchestration.
Package marker
__init__.py
Empty marker file for package import behavior.
Other root files
numeric_detector.py
Lightweight legacy utility for numeric token extraction/change check.
extract_text_unified.py (root)
Currently empty/unused in active flow (active one is in scripts/).
requirements.txt
Python dependency lock list.
5) Current Data Model (Observed)
A parsed section (from parse_sections) typically includes:

section
heading
body
meaning
A change object (from compare_sections) includes:

identity/context fields (old_section, new_section, topic)
classification (type, subtype)
text payload (old_text, new_text)
scoring + metadata (similarity_score, numeric deltas, etc.)
app currently displays a simplified subset.
6) Output Behavior (Current)
UI focuses on:

CHANGE (Added/Removed/Modified),
OLD_SECTION,
NEW_SECTION,
SUMMARY,
expandable block for old/new text evidence.
This keeps user output concise while preserving backend detail internally.

7) Strengths of Current Implementation
Section-number independent matching.
Strong filtering against purely structural edits.
Numeric change awareness with operational context checks.
Multi-stage validation/dedup to reduce noisy results.
Clean reviewer-facing UI with clear evidence expansion.
Ready for iterative precision improvements with baseline testing.
8) Risks / Improvement Opportunities (Documentation View)
OCR quality variance can still influence extraction quality.
Very complex table-heavy PDFs may require specialized table parsing.
app.py contains large inline CSS block; can be externalized later for maintainability.
Root extract_text_unified.py is empty and may confuse future maintainers (can be documented or removed later).
9) End-to-End Summary
This project is a DGCA regulatory change intelligence tool that combines:

PDF extraction (text/OCR),
structural parsing,
semantic comparison,
domain-aware change classification,
and reviewer-friendly presentation.
It is designed to prioritize meaningful operational differences over superficial textual differences, which is the right strategy for compliance document workflows.
