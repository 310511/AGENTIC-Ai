"""
spaCy NLP helper — named-entity recognition and sentence splitting.

Runs synchronously; callers should use asyncio.to_thread() in async contexts.
Extracted entities are candidate facts, not automatically trusted truth —
validate before storing in graph memory (Phase 4).
"""
from __future__ import annotations

import logging

import spacy
from spacy.language import Language

logger = logging.getLogger(__name__)


class NLPProcessor:
    def __init__(self, model: str) -> None:
        logger.info("Loading spaCy model %s", model)
        try:
            self._nlp: Language = spacy.load(model)
        except OSError:
            # Provide a clear action instead of a cryptic import error.
            raise RuntimeError(
                f"spaCy model '{model}' not found. "
                f"Install it with: python -m spacy download {model}"
            )
        logger.info("spaCy model ready")

    def extract(self, text: str) -> dict:
        """
        Return entities and sentences from *text*.

        Entity labels follow spaCy's OntoNotes scheme (PERSON, ORG, GPE, …).
        """
        doc = self._nlp(text)
        entities = [
            {
                "text": ent.text,
                "label": ent.label_,
                "start": ent.start_char,
                "end": ent.end_char,
            }
            for ent in doc.ents
        ]
        sentences = [sent.text.strip() for sent in doc.sents if sent.text.strip()]
        return {"entities": entities, "sentences": sentences}
