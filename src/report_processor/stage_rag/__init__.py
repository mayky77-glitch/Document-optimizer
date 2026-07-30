"""Optional deterministic semantic stage-relation suggestions (StageRelationRAG-18.0)."""

from .encoder import (
    EMBEDDING_DIMENSIONS,
    RUBERT_TINY2_MODEL_ID,
    RUBERT_TINY2_MODEL_REVISION,
    RuBERTTiny2Encoder,
    StageEncoder,
)
from .errors import StageRAGError, StageRAGInputError, StageRAGModelUnavailableError
from .models import (
    STAGE_RELATION_RAG_CONTRACT_VERSION,
    StageRelationCandidate,
    StageRelationSuggestion,
    StageText,
)
from .retrieval import StageRelationRAG, retrieve_stage_relations

__all__ = [
    "EMBEDDING_DIMENSIONS",
    "RUBERT_TINY2_MODEL_ID",
    "RUBERT_TINY2_MODEL_REVISION",
    "STAGE_RELATION_RAG_CONTRACT_VERSION",
    "RuBERTTiny2Encoder",
    "StageEncoder",
    "StageRAGError",
    "StageRAGInputError",
    "StageRAGModelUnavailableError",
    "StageRelationCandidate",
    "StageRelationRAG",
    "StageRelationSuggestion",
    "StageText",
    "retrieve_stage_relations",
]
