"""Named-entity recognition based on the pretrained Natasha model."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from app.extraction.readers import TextChunk


@dataclass(frozen=True)
class NamedEntity:
    text: str
    label: str
    chunk: TextChunk


@lru_cache(maxsize=1)
def _pipeline():
    """Load Natasha once; the model is reused for all uploaded documents."""
    from natasha import NewsEmbedding, NewsNERTagger, Segmenter

    return Segmenter(), NewsNERTagger(NewsEmbedding())


def extract_named_entities(chunks: list[TextChunk]) -> list[NamedEntity]:
    """Return Natasha ORG and PER candidates with their source fragments."""
    from natasha import Doc

    segmenter, ner_tagger = _pipeline()
    entities: list[NamedEntity] = []
    for chunk in chunks:
        document = Doc(chunk.text)
        document.segment(segmenter)
        document.tag_ner(ner_tagger)
        for span in document.spans:
            if span.type in {"ORG", "PER"}:
                entities.append(NamedEntity(span.text, span.type, chunk))
    return entities
