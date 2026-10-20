"""
BGE embedder — wraps sentence-transformers for BAAI/bge-base-en-v1.5.

BGE produces 768-dim vectors. For retrieval queries the model recommends
prepending a short instruction prefix; document chunks are embedded as-is.
All public methods are synchronous because sentence-transformers uses numpy
internally and is not async-safe. The FastAPI endpoint runs them in a
threadpool via asyncio.to_thread().
"""
from __future__ import annotations

import logging

import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 384  # all-MiniLM-L6-v2; change to 768 when switching back to BGE


class Embedder:
    def __init__(self, model_name: str, query_prefix: str) -> None:
        logger.info("Loading embedding model %s", model_name)
        self._model = SentenceTransformer(model_name)
        self._query_prefix = query_prefix
        logger.info("Embedding model ready")

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        """Embed a list of document chunks. Shape: (n, 768), float32."""
        if not texts:
            return np.empty((0, EMBEDDING_DIM), dtype=np.float32)
        vecs = self._model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return np.array(vecs, dtype=np.float32)

    def embed_query(self, query: str) -> np.ndarray:
        """Embed a single retrieval query with the BGE prefix. Shape: (768,), float32."""
        prefixed = self._query_prefix + query
        vec = self._model.encode([prefixed], normalize_embeddings=True, show_progress_bar=False)
        return np.array(vec[0], dtype=np.float32)
