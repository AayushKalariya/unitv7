"""Supabase pgvector storage: insert chunks, similarity search.

Tables and the match_rag_chunks() function are defined in sql/schema.sql.
"""

from services.rag import config

_client = None


def _get_client():
    global _client
    if _client is None:
        if not config.is_configured():
            raise RuntimeError(
                "Supabase not configured. Set SUPABASE_URL and SUPABASE_KEY "
                "(or SUPABASE_SERVICE_KEY) in your .env."
            )
        from supabase import create_client
        _client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
    return _client


def add_document(
    session_id: str,
    filename: str,
    chunks: list[str],
    embeddings: list[list[float]],
) -> str:
    """Insert a document + its chunks. Returns the document id."""
    if len(chunks) != len(embeddings):
        raise ValueError("chunks and embeddings length mismatch")

    client = _get_client()

    doc_row = (
        client.table("rag_documents")
        .insert(
            {
                "session_id": session_id,
                "filename": filename,
                "n_chunks": len(chunks),
            }
        )
        .execute()
    )
    document_id = doc_row.data[0]["id"]

    rows = [
        {
            "document_id": document_id,
            "session_id": session_id,
            "filename": filename,
            "chunk_index": i,
            "content": chunk,
            "embedding": emb,
        }
        for i, (chunk, emb) in enumerate(zip(chunks, embeddings))
    ]
    # Insert in batches to stay well under request-size limits.
    batch = 100
    for start in range(0, len(rows), batch):
        client.table("rag_chunks").insert(rows[start : start + batch]).execute()

    return document_id


def search(
    query_embedding: list[float],
    session_id: str | None,
    top_k: int,
) -> list[dict]:
    """Return chunks most similar to `query_embedding`.

    Pass session_id=None to search across every session.
    Each result: {content, filename, session_id, similarity, ...}.
    """
    client = _get_client()
    resp = client.rpc(
        "match_rag_chunks",
        {
            "query_embedding": query_embedding,
            "match_count": top_k,
            "filter_session_id": session_id,
        },
    ).execute()
    return resp.data or []
