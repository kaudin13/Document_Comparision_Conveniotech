import pdfplumber
from pdf2image import convert_from_path
import pytesseract
import os

TESSERACT_PATH = os.getenv("TESSERACT_PATH")

if TESSERACT_PATH:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

def is_scanned_pdf(pdf_path, check_pages=2):
    """
    Returns True if PDF is scanned (image-based), False if text-based.
    """
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages[:check_pages]:
            text = page.extract_text()
            if text and text.strip():
                return False
    return True


def extract_text_pdfplumber(pdf_path):
    """
    Extract text from text-based PDF using pdfplumber.
    """
    text_pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                text_pages.append(text)
    return "\n".join(text_pages)


def extract_text_ocr(pdf_path):
    """
    Extract text from scanned PDF using OCR.
    """
    text_pages = []
    images = convert_from_path(pdf_path)
    for img in images:
        text = pytesseract.image_to_string(img)
        text_pages.append(text)
    return "\n".join(text_pages)


def extract_text(pdf_path, output_txt):
    try:
        print(f"\nProcessing: {pdf_path}")

        if is_scanned_pdf(pdf_path):
            print("→ Scanned PDF detected. Using OCR.")
            text = extract_text_ocr(pdf_path)
        else:
            print("→ Text-based PDF detected. Using pdfplumber.")
            text = extract_text_pdfplumber(pdf_path)

        with open(output_txt, "w", encoding="utf-8") as f:
            f.write(text)

        print(f"✓ Text saved to: {output_txt}")

    except Exception as e:
        raise RuntimeError(f"Failed to extract text from {pdf_path}: {e}")



