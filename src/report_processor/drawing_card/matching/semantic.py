"""Offline RuBERT Tiny2 retrieval used only to enrich manual review."""

from __future__ import annotations

from report_processor.stage_rag import (
    RuBERTTiny2Encoder,
    StageRAGError,
    StageText,
    retrieve_stage_relations,
)

from .examples import ConfirmedExample, RetrievedExample


class SemanticExampleRetriever:
    """Retrieve confirmed examples from the pinned local model, never a network."""

    def __init__(self, examples: tuple[ConfirmedExample, ...]) -> None:
        self._examples = examples
        self._encoder = RuBERTTiny2Encoder()

    def search(self, text: str, *, top_k: int) -> tuple[RetrievedExample, ...]:
        if not self._examples:
            return ()
        sources = tuple(
            StageText(identity=example.example_id, text=example.normalized_text)
            for example in self._examples
        )
        try:
            suggestion = retrieve_stage_relations(
                self._encoder,
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
