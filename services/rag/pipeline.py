"""High-level RAG orchestration used by the app.

    ingest_file(session_id, path) -> dict   # parse → chunk → embed → store
    retrieve(query, session_id)   -> str    # context block for the prompt
"""

import os

from services.rag import config, documents, chunking, embeddings, vector_store


def is_configured() -> bool:
    """Whether RAG can run (Supabase creds present)."""
    return config.is_configured()


def ingest_file(session_id: str, path: str) -> dict:
    """Ingest one file into the vector store for `session_id`.

    Returns {"filename", "n_chunks", "document_id"}.
    Raises on failure (unreadable file, empty content, storage error).
    """
    if not is_configured():
        raise RuntimeError(
            "RAG storage not configured — add SUPABASE_URL and SUPABASE_KEY to .env."
        )

    filename = os.path.basename(path)
    text = documents.parse_file(path)
    chunks = chunking.chunk_text(text)
    if not chunks:
        raise ValueError(f"No extractable text found in {filename}.")

    vectors = embeddings.embed_texts(chunks)
    document_id = vector_store.add_document(session_id, filename, chunks, vectors)

    return {"filename": filename, "n_chunks": len(chunks), "document_id": document_id}


def retrieve(query: str, session_id: str | None) -> str:
    """Return a formatted context block of chunks relevant to `query`.

    Scoped to `session_id`. Returns "" when RAG is off, nothing is stored,
    or no chunk clears config.MIN_SIMILARITY — so the caller can always inject
    the result unconditionally.
    """
    if not is_configured() or not query.strip():
        return ""

    try:
        query_vec = embeddings.embed_query(query)
        results = vector_store.search(query_vec, session_id, config.TOP_K)
    except Exception as e:
        # RAG must never break the chat; degrade to no-context.
        print(f"[rag] retrieval failed: {e}")
        return ""

    kept = [r for r in results if r.get("similarity", 0) >= config.MIN_SIMILARITY]
    if not kept:
        return ""

    blocks = []
    for r in kept:
        src = r.get("filename", "uploaded file")
        sim = r.get("similarity", 0)
        blocks.append(f"[source: {src} · similarity {sim:.2f}]\n{r.get('content', '')}")

    joined = "\n\n---\n\n".join(blocks)
    return (
        "The user uploaded documents. The following excerpts were retrieved as "
        "relevant to their message. Use them to answer when applicable, and cite the "
        "source filename. If they do not contain the answer, say so.\n\n"
        f"{joined}"
    )
