"""StageRelationRAG suggestions never override Block 12 matching authority."""

from __future__ import annotations

from report_processor.stage_rag import StageRelationRAG, StageText

from fixtures.matching.builders import rule_set, source_row, target_row
from fixtures.stage_rag.builders import FakeEncoder
from report_processor.matching import match_rows


def test_semantic_suggestions_remain_manual_review_only_alongside_block12_result() -> None:
    target = target_row(work_name="target work")
    source = source_row(work_name="source work")
    block12 = match_rows(
        (source,),
        (target,),
        rule_set(literal="unrelated"),
        target_source_id="target-a",
        target_fingerprint="sha256:abc",
    )
    authoritative_selection = block12[0].selected_candidate
    assert authoritative_selection is not None

    suggestion = StageRelationRAG(
        FakeEncoder({"source work": (1, 0), "target work": (1, 0)}), embedding_dimensions=2
    ).suggest(
        (StageText(source.source_row_id, "source work"),),
        (StageText(block12[0].target_row_id, "target work"),),
        k=1,
    )[0]

    assert suggestion.candidates[0].source_identity == source.source_row_id
    assert suggestion.requires_manual_review is True
    assert suggestion.auto_accepted is False
    assert block12[0].selected_candidate is authoritative_selection
