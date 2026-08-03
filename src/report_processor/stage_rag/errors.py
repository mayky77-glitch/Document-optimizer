"""Controlled errors for the optional StageRelationRAG-18.0 boundary."""

from __future__ import annotations


class StageRAGError(ValueError):
    """Base error for semantic stage-relation suggestions."""

    code = "STAGE_RAG_ERROR"


class StageRAGInputError(StageRAGError):
    """An input, embedding, or retrieval argument violates the contract."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


class StageRAGModelUnavailableError(StageRAGError):
    """The optional local embedding dependencies or model files are unavailable."""

    code = "RAG_MODEL_UNAVAILABLE"


class StageRAGStoreError(StageRAGError):
    """The vector store returned data that violates the Dense RAG contract."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


class StageRAGStoreUnavailableError(StageRAGError):
    """A vector store cannot be reached within its bounded request timeout."""

    code = "RAG_STORE_UNAVAILABLE"
