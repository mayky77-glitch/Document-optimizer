"""Injectable encoder contract and lazy local RuBERT-tiny2 adapter."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from .errors import StageRAGModelUnavailableError

RUBERT_TINY2_MODEL_ID = "cointegrated/rubert-tiny2"
RUBERT_TINY2_MODEL_REVISION = "e8ed3b0c8bbf4fb6984c3de043bf7d2f4e5969ae"
EMBEDDING_DIMENSIONS = 312


class StageEncoder(Protocol):
    """Encodes text locally; test implementations need no model dependency."""

    def encode(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        """Return exactly one vector for every supplied text."""


class RuBERTTiny2Encoder:
    """Lazy adapter for a locally cached, exactly pinned Hugging Face model."""

    def __init__(self) -> None:
        self._tokenizer: object | None = None
        self._model: object | None = None
        self._torch: object | None = None

    def encode(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        if not texts:
            return ()
        self._load()
        assert self._tokenizer is not None
        assert self._model is not None
        assert self._torch is not None
        try:
            batch = self._tokenizer(list(texts), padding=True, truncation=True, return_tensors="pt")
            with self._torch.inference_mode():
                cls_vectors = self._model(**batch).last_hidden_state[:, 0, :]
            return tuple(tuple(float(value) for value in row.tolist()) for row in cls_vectors)
        except StageRAGModelUnavailableError:
            raise
        except Exception as exc:
            raise StageRAGModelUnavailableError(
                "Локальная модель RuBERT не смогла закодировать текст"
            ) from exc

    def _load(self) -> None:
        if self._model is not None:
            return
        try:
            import torch
            from transformers import AutoModel, AutoTokenizer

            tokenizer = AutoTokenizer.from_pretrained(
                RUBERT_TINY2_MODEL_ID,
                revision=RUBERT_TINY2_MODEL_REVISION,
                local_files_only=True,
            )
            model = AutoModel.from_pretrained(
                RUBERT_TINY2_MODEL_ID,
                revision=RUBERT_TINY2_MODEL_REVISION,
                local_files_only=True,
            )
            model.eval()
        except (ImportError, OSError, ValueError) as exc:
            raise StageRAGModelUnavailableError(
                "Не установлены RAG-зависимости или отсутствует локальная модель RuBERT"
            ) from exc
        self._tokenizer = tokenizer
        self._model = model
        self._torch = torch
