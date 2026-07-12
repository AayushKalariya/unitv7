"""RAG configuration, read from environment (.env)."""

import os

# ── Supabase ──────────────────────────────────────────────────────────────
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
# Prefer the service-role key for server-side writes; fall back to anon key.
SUPABASE_KEY = (
    os.environ.get("SUPABASE_SERVICE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or os.environ.get("SUPABASE_ANON_KEY")
    or ""
).strip()

# ── Embeddings ────────────────────────────────────────────────────────────
# fastembed model name and its output dimension. Must match sql/schema.sql.
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5").strip()
EMBEDDING_DIM = int(os.environ.get("EMBEDDING_DIM", "384"))

# ── Chunking ──────────────────────────────────────────────────────────────
CHUNK_SIZE = int(os.environ.get("RAG_CHUNK_SIZE", "512"))        # tokens per chunk
CHUNK_OVERLAP = int(os.environ.get("RAG_CHUNK_OVERLAP", "64"))   # tokens of overlap

# ── Retrieval ─────────────────────────────────────────────────────────────
TOP_K = int(os.environ.get("RAG_TOP_K", "5"))
# Only inject chunks at or above this cosine similarity into the prompt.
MIN_SIMILARITY = float(os.environ.get("RAG_MIN_SIMILARITY", "0.3"))


def is_configured() -> bool:
    """True when Supabase credentials are present."""
    return bool(SUPABASE_URL and SUPABASE_KEY)
