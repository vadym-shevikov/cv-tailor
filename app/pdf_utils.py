"""Helpers for working with PDF files."""

from __future__ import annotations

import logging
from io import BytesIO

try:  # pragma: no cover - optional dependency guard
    from pypdf import PdfReader
except ImportError:  # pragma: no cover - FastAPI boot should still succeed
    PdfReader = None  # type: ignore

logger = logging.getLogger(__name__)


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract readable text from a PDF byte stream.

    Uses :mod:`pypdf` to iterate over all pages and concatenate their text.
    Falls back to an empty string if parsing fails so downstream components
    can still produce a helpful error message instead of crashing.
    """

    if not pdf_bytes:
        return ""

    if PdfReader is None:
        logger.warning("pypdf is missing; returning empty CV text")
        return ""

    try:
        reader = PdfReader(BytesIO(pdf_bytes))
        text_chunks = []
        for page in reader.pages:
            page_text = page.extract_text() or ""
            text_chunks.append(page_text)
        raw_text = "\n".join(text_chunks)
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.exception("Failed to parse PDF: %%s", exc)
        return ""

    cleaned_lines = [line.strip() for line in raw_text.splitlines()]
    # Collapse multiple blank lines without removing intentional spacing entirely
    normalized = []
    blank_streak = 0
    for line in cleaned_lines:
        if not line:
            blank_streak += 1
            if blank_streak <= 1:
                normalized.append("")
        else:
            blank_streak = 0
            normalized.append(line)

    return "\n".join(normalized).strip()
