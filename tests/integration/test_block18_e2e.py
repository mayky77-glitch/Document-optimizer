"""StageRelationRAG suggestions never override Block 12 matching authority."""

from __future__ import annotations

import argparse
from pathlib import Path
from types import SimpleNamespace

from report_processor.stage_rag import StageRelationRAG, StageText

from fixtures.matching.builders import rule_set, source_row, target_row
from fixtures.stage_rag.builders import FakeEncoder
from report_processor.cli_process import add_process_parser, run_process
from report_processor.matching import MatchStatus, match_rows
from report_processor.processing import (
    DefaultProcessingAdapters,
    ProcessingExitCode,
    ProcessingResult,
    ProcessingState,
    ProcessReportRequest,
)


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


def test_cli_stage_rag_flags_are_opt_in_and_preserve_legacy_default_options(monkeypatch) -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    add_process_parser(subparsers)
    captured: list[ProcessReportRequest] = []

    def record(request: ProcessReportRequest) -> ProcessingResult:
        captured.append(request)
        return ProcessingResult(
            request, ProcessingState.SUCCEEDED, ProcessingExitCode.SUCCESS, "run"
        )

    monkeypatch.setattr("report_processor.cli_process.process_report", record)
    legacy = parser.parse_args(["process", "--source", "source.xlsx", "--target", "target.xlsx"])
    enabled = parser.parse_args(
        [
            "process",
            "--source",
            "source.xlsx",
            "--target",
            "target.xlsx",
            "--stage-rag",
            "--stage-rag-top-k",
            "2",
        ]
    )

    assert run_process(legacy) == 0
    assert run_process(enabled) == 0
    assert captured[0].options == {}
    assert captured[1].options == {"stage_rag": True, "stage_rag_top_k": 2}


def test_fake_encoder_wiring_is_deterministic_and_requires_manual_review(tmp_path: Path) -> None:
    request = ProcessReportRequest(
        tmp_path / "source.xlsx",
        tmp_path / "target.xlsx",
        options={"stage_rag": True, "stage_rag_top_k": 1},
    )
    source_rows = (
        SimpleNamespace(source_row_id="source-b", work_name="source-b"),
        SimpleNamespace(source_row_id="source-a", work_name="source-a"),
    )
    matches = (
        SimpleNamespace(
            result_id="target-a",
            status=MatchStatus.UNMATCHED,
            target_row=SimpleNamespace(stage="target-a", work_name="fallback"),
        ),
    )
    vector = (1.0,) + (0.0,) * 311
    adapters = DefaultProcessingAdapters(
        FakeEncoder({"source-a": vector, "source-b": vector, "target-a": vector})
    )

    first, first_warnings = adapters._stage_relation_suggestions(request, source_rows, matches)
    second, second_warnings = adapters._stage_relation_suggestions(
        request, tuple(reversed(source_rows)), matches
    )

    assert first == second
    assert first_warnings == second_warnings == ("STAGE_RAG_MANUAL_REVIEW_REQUIRED",)
    assert first["stage_rag_status"] == "MANUAL_REVIEW_REQUIRED"
    assert first["stage_rag_requires_manual_review"] is True
    suggestion = first["stage_relation_suggestions"][0]
    assert tuple(item.source_identity for item in suggestion.candidates) == ("source-a",)
