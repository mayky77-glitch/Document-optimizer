"""Offline RuBERT Tiny2 retrieval used only to enrich manual review."""

from __future__ import annotations

from threading import Lock

from report_processor.stage_rag import (
    RuBERTTiny2Encoder,
    StageRAGError,
    StageText,
    retrieve_stage_relations,
)

from .examples import ConfirmedExample, RetrievedExample


class SemanticExampleRetriever:
    """Retrieve confirmed examples from the pinned local model, never a network."""

    _encoder: RuBERTTiny2Encoder | None = None
    _encoder_lock = Lock()

    def __init__(self, examples: tuple[ConfirmedExample, ...]) -> None:
        self._examples = examples

    @classmethod
    def _shared_encoder(cls) -> RuBERTTiny2Encoder:
        with cls._encoder_lock:
            if cls._encoder is None:
                cls._encoder = RuBERTTiny2Encoder()
            return cls._encoder

    def search(self, text: str, *, top_k: int) -> tuple[RetrievedExample, ...]:
        if not self._examples:
            return ()
        sources = tuple(
            StageText(identity=example.example_id, text=example.normalized_text)
            for example in self._examples
        )
        try:
            suggestion = retrieve_stage_relations(
                self._shared_encoder(),
                sources,
                (StageText(identity="query", text=text),),
                k=min(top_k, len(sources)),
            )[0]
        except (StageRAGError, ValueError, TypeError):
            return ()
        by_id = {example.example_id: example for example in self._examples}
        return tuple(
            RetrievedExample(by_id[item.source_identity], item.score)
            for item in suggestion.candidates
        )
