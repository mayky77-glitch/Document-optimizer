"""Controlled input errors for MatchingEngine-12.0."""

from __future__ import annotations


class MatchingError(ValueError):
    code = "MATCHING_ERROR"


class MatchingInputError(MatchingError):
    """Rejected input identity or public matching argument."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")
