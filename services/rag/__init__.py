"""Retrieval-augmented generation for Orb Assistant.

Pipeline: docling (parse any file → text) → chonkie (chunk) →
fastembed (local embeddings) → Supabase pgvector (store + similarity search).

Public entry points live in `pipeline`:
    from services.rag import ingest_file, retrieve, is_configured
"""

from services.rag.pipeline import ingest_file, retrieve, is_configured

__all__ = ["ingest_file", "retrieve", "is_configured"]
