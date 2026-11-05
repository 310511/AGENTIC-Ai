"""
Document text extractor — PDF and image files.

PDF  → pdfplumber (text layer first, OCR fallback per page if text is empty)
Image → pytesseract OCR (PNG, JPG, TIFF, BMP, WEBP)

Returns plain text ready for chunking. Raises ValueError for unsupported types.
"""
from __future__ import annotations

import io
import logging

logger = logging.getLogger(__name__)

SUPPORTED_MIME = {
    "application/pdf",
    "image/png", "image/jpeg", "image/jpg",
    "image/tiff", "image/bmp", "image/webp",
}


def extract_text(data: bytes, mime_type: str) -> str:
    """Extract plain text from raw file bytes. Raises ValueError on unsupported type."""
    mime_type = mime_type.lower().split(";")[0].strip()
    if mime_type not in SUPPORTED_MIME:
        raise ValueError(
            f"Unsupported file type '{mime_type}'. "
            f"Supported: PDF, PNG, JPG, TIFF, BMP, WEBP."
        )
    if mime_type == "application/pdf":
        return _extract_pdf(data)
    return _extract_image(data)


def _extract_pdf(data: bytes) -> str:
    import pdfplumber

    pages: list[str] = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            if text.strip():
                pages.append(text)
            else:
                # Text layer empty — OCR the rendered page image
                logger.info("PDF page %d has no text layer, running OCR", i + 1)
                img = page.to_image(resolution=150).original
                pages.append(_ocr_pil(img))

    return "\n\n".join(p for p in pages if p.strip())


def _extract_image(data: bytes) -> str:
    from PIL import Image
    img = Image.open(io.BytesIO(data))
    return _ocr_pil(img)


def _ocr_pil(img) -> str:
    import pytesseract
    text = pytesseract.image_to_string(img)
    return text.strip()
