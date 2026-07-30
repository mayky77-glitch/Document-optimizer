"""Deterministic source-to-target matching (MatchingEngine-12.0)."""

from .engine import match_rows
from .exceptions import MatchingError, MatchingInputError
from .models import (
    MATCHING_CONTRACT_VERSION,
    MATCHING_ENGINE_VERSION,
    MatchCandidate,
    MatchingPolicy,
    MatchResult,
    MatchStatus,
    MatchStrategy,
    strategy_ordinal,
)

__all__ = [
    "MATCHING_CONTRACT_VERSION",
    "MATCHING_ENGINE_VERSION",
    "MatchCandidate",
    "MatchResult",
    "MatchStatus",
    "MatchStrategy",
    "MatchingError",
    "MatchingInputError",
    "MatchingPolicy",
    "match_rows",
    "strategy_ordinal",
]
