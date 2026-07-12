"""Split parsed document text into chunks using chonkie.

RecursiveChunker respects document structure (paragraphs, sentences) and keeps
chunks near a target token size — a good default for RAG without needing an
embedding model at chunk time.
"""

from services.rag import config

_chunker = None


def _get_chunker():
    global _chunker
    if _chunker is None:
        from chonkie import RecursiveChunker
        _chunker = RecursiveChunker(
            chunk_size=config.CHUNK_SIZE,
        )
    return _chunker


def chunk_text(text: str) -> list[str]:
    """Return a list of non-empty chunk strings for `text`."""
    text = (text or "").strip()
    if not text:
        return []

    chunks = _get_chunker().chunk(text)
    out: list[str] = []
    for c in chunks:
        # chonkie chunk objects expose `.text`; be defensive for plain strings.
        piece = getattr(c, "text", c)
        if isinstance(piece, str) and piece.strip():
            out.append(piece.strip())
    return out
