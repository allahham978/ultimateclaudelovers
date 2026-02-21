# PDF text extraction wrapper — Iteration 2 will wire this into main.py
# Implementation is defined in PRD Section 7.
import pdfplumber
from io import BytesIO


def extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extract full text from a PDF file using pdfplumber.

    Args:
        pdf_bytes: Raw PDF file bytes from the multipart upload.

    Returns:
        Concatenated text from all pages, separated by page markers.
    """
    pages = []
    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            pages.append(f"--- PAGE {i} ---\n{text}")
    return "\n\n".join(pages)
