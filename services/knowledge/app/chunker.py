"""
Text chunker — splits a document into overlapping fixed-size chunks.

Uses a simple word-based split rather than a tokeniser so there is no
dependency on any model's tokeniser at chunk time. Actual token counts
will vary slightly from the chunk_size setting; that is acceptable for
a retrieval index.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Chunk:
    index: int        # 0-based position within the document
    text: str


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[Chunk]:
    """
    Split *text* into overlapping chunks of approximately *chunk_size* words.

    Returns at least one chunk even for very short text.
    """
    words = text.split()
    if not words:
        return [Chunk(index=0, text="")]

    step = max(1, chunk_size - overlap)
    chunks: list[Chunk] = []
    i = 0
    while i < len(words):
        chunk_words = words[i : i + chunk_size]
        chunks.append(Chunk(index=len(chunks), text=" ".join(chunk_words)))
        if i + chunk_size >= len(words):
            break
        i += step

    return chunks
