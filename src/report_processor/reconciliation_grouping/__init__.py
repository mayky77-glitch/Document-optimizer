"""Deterministic, safe global package grouping for reconciliation review."""

from .features import extract_all, extract_features, normalize_text, unit_family
from .models import (
    FEATURE_CONTRACT_VERSION,
    FEATURE_RULE_VERSION,
    PACKAGE_CONTRACT_VERSION,
    DecisionPackage,
    FeatureVector,
    GroupingException,
    GroupingResult,
    RowPartition,
    SemanticFamily,
    UnitFamily,
)
from .packages import build_reconciliation_packages, rank_with_local_assist
from .semantic_model import LocalSemanticAssist, SemanticAssistResult, VersionedEmbeddingCache
from .zero_activity import is_zero_activity, partition_rows

__all__ = [
    "FEATURE_CONTRACT_VERSION",
    "FEATURE_RULE_VERSION",
    "PACKAGE_CONTRACT_VERSION",
    "DecisionPackage",
    "FeatureVector",
    "GroupingException",
    "GroupingResult",
    "LocalSemanticAssist",
    "RowPartition",
    "SemanticAssistResult",
    "SemanticFamily",
    "UnitFamily",
    "VersionedEmbeddingCache",
    "build_reconciliation_packages",
    "extract_all",
    "extract_features",
    "is_zero_activity",
    "normalize_text",
    "partition_rows",
    "rank_with_local_assist",
    "unit_family",
]
