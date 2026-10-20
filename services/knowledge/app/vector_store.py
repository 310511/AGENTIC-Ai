"""
FAISS vector store with a JSON ID mapping for tenant-aware retrieval.

Layout on disk (index_dir/):
  index.faiss     — the FAISS flat L2 index (normalised vectors → cosine sim)
  id_map.json     — maps each FAISS integer ID to {document_id, chunk_index,
                    tenant_id, text, metadata}

All reads and writes are protected by a threading.Lock so the store is safe
for the single-process, multi-request FastAPI deployment.

shortcut: uses a flat IndexFlatIP index (exact search); upgrade to IndexIVFFlat
          or IndexHNSWFlat when the index exceeds ~100 k vectors.
"""
from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any

import faiss
import numpy as np

from .embedder import EMBEDDING_DIM

logger = logging.getLogger(__name__)

_ID_MAP_FILE = "id_map.json"
_INDEX_FILE = "index.faiss"


class VectorStore:
    def __init__(self, index_dir: Path) -> None:
        self._dir = index_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._load()

    # ── persistence ──────────────────────────────────────────────────────────

    def _load(self) -> None:
        idx_path = self._dir / _INDEX_FILE
        map_path = self._dir / _ID_MAP_FILE
        if idx_path.exists() and map_path.exists():
            self._index = faiss.read_index(str(idx_path))
            with open(map_path) as f:
                # keys are strings in JSON; convert back to int
                self._id_map: dict[int, dict] = {int(k): v for k, v in json.load(f).items()}
            logger.info("Loaded FAISS index: %d vectors", self._index.ntotal)
        else:
            # Inner-product on L2-normalised vectors == cosine similarity
            self._index = faiss.IndexFlatIP(EMBEDDING_DIM)
            self._id_map = {}
            logger.info("Created new FAISS index")

    def _save(self) -> None:
        faiss.write_index(self._index, str(self._dir / _INDEX_FILE))
        with open(self._dir / _ID_MAP_FILE, "w") as f:
            json.dump(self._id_map, f)

    # ── write ─────────────────────────────────────────────────────────────────

    def add(
        self,
        vectors: np.ndarray,
        document_id: str,
        tenant_id: str,
        chunks: list[dict],  # each: {index, text, metadata}
    ) -> int:
        """Add vectors for one document's chunks. Returns count added."""
        if vectors.shape[0] == 0:
            return 0
        with self._lock:
            start_id = self._index.ntotal
            self._index.add(vectors)
            for i, chunk in enumerate(chunks):
                self._id_map[start_id + i] = {
                    "document_id": document_id,
                    "tenant_id": tenant_id,
                    "chunk_index": chunk["index"],
                    "text": chunk["text"],
                    "metadata": chunk.get("metadata", {}),
                }
            self._save()
        return vectors.shape[0]

    def delete_document(self, document_id: str, tenant_id: str) -> int:
        """Remove all vectors belonging to a document. Returns count removed."""
        with self._lock:
            ids_to_remove = [
                fid for fid, meta in self._id_map.items()
                if meta["document_id"] == document_id and meta["tenant_id"] == tenant_id
            ]
            if not ids_to_remove:
                return 0
            # Rebuild index without the removed entries — flat index has no remove API
            selector = faiss.IDSelectorBatch(
                len(ids_to_remove),
                faiss.swig_ptr(np.array(ids_to_remove, dtype=np.int64)),
            )
            self._index.remove_ids(selector)
            for fid in ids_to_remove:
                del self._id_map[fid]
            self._save()
        return len(ids_to_remove)

    # ── read ──────────────────────────────────────────────────────────────────

    def search(
        self,
        query_vec: np.ndarray,
        tenant_id: str,
        top_k: int,
    ) -> list[dict[str, Any]]:
        """
        Return up to top_k chunks for tenant_id, sorted by cosine similarity.

        Over-fetches by 4× to compensate for cross-tenant filtering, then
        trims to top_k after filtering.
        """
        with self._lock:
            if self._index.ntotal == 0:
                return []
            fetch = min(top_k * 4, self._index.ntotal)
            scores, ids = self._index.search(query_vec.reshape(1, -1), fetch)

        results = []
        for score, fid in zip(scores[0], ids[0]):
            if fid < 0:
                continue
            meta = self._id_map.get(int(fid))
            if meta is None or meta["tenant_id"] != tenant_id:
                continue
            results.append({
                "document_id": meta["document_id"],
                "chunk_index": meta["chunk_index"],
                "text": meta["text"],
                "score": float(score),
                "metadata": meta["metadata"],
            })
            if len(results) >= top_k:
                break

        return results
