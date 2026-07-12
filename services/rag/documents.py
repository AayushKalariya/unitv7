"""Parse arbitrary files into plain text using docling.

docling handles PDF, DOCX, PPTX, XLSX, HTML, Markdown, images (OCR), and more,
returning a structured document we export to Markdown. Plain-text files are read
directly to avoid unnecessary conversion overhead.
"""

import os

# Extensions we just read as UTF-8 text — no docling needed.
_PLAIN_TEXT_EXTS = {".txt", ".md", ".markdown", ".text", ".log", ".csv", ".json"}

# Lazily-initialised docling converter (first call is slow: loads models).
_converter = None


def _get_converter():
    global _converter
    if _converter is None:
        from docling.document_converter import DocumentConverter
        _converter = DocumentConverter()
    return _converter


def parse_file(path: str) -> str:
    """Return the text content of `path` as Markdown/plain text.

    Raises on unreadable/unsupported files so the caller can surface an error.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(path)

    ext = os.path.splitext(path)[1].lower()
    if ext in _PLAIN_TEXT_EXTS:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()

    result = _get_converter().convert(path)
    return result.document.export_to_markdown()
