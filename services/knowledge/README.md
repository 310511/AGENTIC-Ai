# Knowledge Service

**Status:** Placeholder — Phase 3

## Responsibility

Handles document ingestion, chunking, embedding generation, and vector
retrieval. Uses `BAAI/bge-base-en-v1.5` via Sentence Transformers to produce
**768-dimensional** embeddings stored in a FAISS index. Also houses the spaCy
NLP pipeline for entity and relationship extraction.

## Planned components

```
knowledge/
├── app/
│   ├── main.py              # Internal FastAPI app
│   ├── config.py
│   ├── ingestion/
│   │   ├── chunker.py       # Configurable text chunking strategy
│   │   └── pipeline.py      # Ingest → chunk → embed → index pipeline
│   ├── embedding/
│   │   └── bge.py           # BGE embedder using SentenceTransformers
│   ├── retrieval/
│   │   └── faiss_store.py   # FAISS index wrapper + ID mapping
│   └── nlp/
│       └── spacy_extractor.py  # NLP entity/relationship extraction
├── requirements.txt
└── Dockerfile
```

## Key design rules (from context.md)

- Always use the BGE query instruction prefix for query embeddings:
  `"Represent this sentence for searching relevant passages: "`.
- Keep document and query embeddings in the same model/vector space.
- Persist the FAISS index and its ID-to-chunk mapping; FAISS is an index,
  not a database.
- Apply tenant filters before returning retrieved content — FAISS has no
  application-level row security.
- Treat spaCy-extracted entities as **candidate facts**, not verified truth.

## Phase 3 dependencies

- `sentence-transformers`
- `faiss-cpu`
- `spacy`
- `en_core_web_sm` (spaCy model)
- `numpy`
