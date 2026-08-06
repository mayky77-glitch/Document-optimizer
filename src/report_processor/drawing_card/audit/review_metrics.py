"""Explicit, privacy-safe counters for the manual-review packet lifecycle."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(slots=True)
class ReviewMetrics:
    """Mutable only through explicit counter operations; rates never divide by zero."""

    review_candidates: int = 0
    queued_review_rows: int = 0
    packets: int = 0
    singleton_packets: int = 0
    opened_cards: int = 0
    feedback_hits: int = 0
    packet_exclusions: int = 0
    overrides: int = 0
    review_applies: int = 0
    post_review_errors: int = 0

    def increment(self, counter: str, amount: int = 1) -> None:
        """Increment exactly one named counter, rejecting accidental derived writes."""
        if counter not in _COUNTERS:
            raise ValueError(f"Unknown review metric: {counter}")
        if not isinstance(amount, int) or isinstance(amount, bool) or amount < 0:
            raise ValueError("Review metric increments must be non-negative integers")
        setattr(self, counter, getattr(self, counter) + amount)

    def record_review_candidate(self, amount: int = 1) -> None:
        self.increment("review_candidates", amount)

    def record_queued_review_row(self, amount: int = 1) -> None:
        self.increment("queued_review_rows", amount)

    def record_packet(self, *, singleton: bool = False) -> None:
        self.increment("packets")
        if singleton:
            self.increment("singleton_packets")

    def record_opened_card(self) -> None:
        self.increment("opened_cards")

    def record_feedback_hit(self) -> None:
        self.increment("feedback_hits")

    def record_packet_exclusion(self) -> None:
        self.increment("packet_exclusions")

    def record_override(self) -> None:
        self.increment("overrides")

    def record_review_apply(self) -> None:
        self.increment("review_applies")

    def record_post_review_error(self) -> None:
        self.increment("post_review_errors")

    def to_dict(self) -> dict[str, int | float]:
        """Serialize counters and safe rates using only JSON primitive values."""
        result: dict[str, int | float] = asdict(self)
        result.update(
            singleton_share=_safe_rate(self.singleton_packets, self.packets),
            feedback_hit_rate=_safe_rate(self.feedback_hits, self.review_candidates),
            post_review_error_rate=_safe_rate(self.post_review_errors, self.review_applies),
        )
        return result


_COUNTERS = frozenset(ReviewMetrics.__dataclass_fields__)


def _safe_rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0
