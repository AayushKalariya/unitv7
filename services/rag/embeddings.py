"""Local text embeddings via fastembed (no external API key required).

Uses the model named by config.EMBEDDING_MODEL. The same model must embed both
stored chunks and query text so vectors are comparable.
"""

from services.rag import config

_model = None


def _get_model():
    global _model
    if _model is None:
        from fastembed import TextEmbedding
        _model = TextEmbedding(model_name=config.EMBEDDING_MODEL)
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of documents. Returns one vector (list[float]) per text."""
    if not texts:
        return []
    model = _get_model()
    return [vec.tolist() for vec in model.embed(texts)]


def embed_query(text: str) -> list[float]:
    """Embed a single query string."""
    model = _get_model()
    # fastembed exposes query_embed for asymmetric models; fall back to embed.
    embed_fn = getattr(model, "query_embed", None) or model.embed
    vec = next(iter(embed_fn([text])))
    return vec.tolist()
