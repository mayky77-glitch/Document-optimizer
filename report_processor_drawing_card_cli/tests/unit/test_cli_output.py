from __future__ import annotations

from pathlib import Path

from report_processor.terminal_review import TerminalReviewOutcome

from report_processor import cli
from report_processor.drawing_card.matching.matcher import ReviewApproval
from report_processor.drawing_card.models import (
    TargetWorkCategory,
    WorkflowResult,
)


def _result(
    tmp_path: Path,
    *,
    status: str,
    review_count: int = 0,
    warnings: list[str] | None = None,
) -> WorkflowResult:
    return WorkflowResult(
        run_id=status.lower(),
        status=status,
        work_dir=tmp_path / status.lower(),
        manual_review_count=review_count,
        warnings=warnings or [],
    )


def test_warning_output_is_aggregated_and_bounded(tmp_path: Path, capsys) -> None:
    warnings = [f"CODE_{index}:detail" for index in range(20)]
    warnings.extend(["CODE_0:repeat"] * 30)

    cli._print_workflow_result(
        _result(tmp_path, status="BLOCKED", review_count=2, warnings=warnings)
    )

    output = capsys.readouterr().out
    assert "Warnings: 50" in output
    assert "CODE_0: 31" in output
    assert "Other warning types: 8" in output
    assert "CODE_12" not in output
    assert output.count("\n  - ") == 13


def test_interactive_review_flag_is_opt_in() -> None:
    parser = cli.build_parser()
    common = [
        "build-drawing-card",
        "--inputs",
        "source.xlsx",
        "--output",
        "result.xlsx",
    ]

    assert not parser.parse_args(common).interactive_review
    assert parser.parse_args([*common, "--interactive-review"]).interactive_review


def test_interactive_review_saves_decisions_and_reruns_once(
    tmp_path: Path,
    monkeypatch,
) -> None:
    parser = cli.build_parser()
    args = parser.parse_args(
        [
            "build-drawing-card",
            "--inputs",
            "source.xlsx",
            "--output",
            "result.xlsx",
            "--interactive-review",
        ]
    )
    first = _result(
        tmp_path,
        status="BLOCKED",
        review_count=1,
        warnings=["MANUAL_REVIEW_REQUIRED:1"],
    )
    second = _result(tmp_path, status="PARTIALLY_READY")
    results = iter((first, second))
    requests = []
    saved = []

    def fake_workflow(request):
        requests.append(request)
        return next(results)

    monkeypatch.setattr(cli, "run_workflow", fake_workflow)
    monkeypatch.setattr(
        cli,
        "collect_terminal_review",
        lambda _result: TerminalReviewOutcome(
            {
                "row-1": ReviewApproval(
                    "row-1",
                    "approve",
                    TargetWorkCategory.CONCRETE_WORKS,
                )
            },
            True,
            True,
        ),
    )
    monkeypatch.setattr(
        cli,
        "save_terminal_review_decisions",
        lambda path, decisions: saved.append((path, decisions)),
    )

    assert cli._build_command(args) == 0
    assert len(requests) == 2
    assert requests[1].review_decisions == first.work_dir / "terminal_review_decisions.json"
    assert not requests[1].strict
    assert saved[0][0] == first.work_dir / "terminal_review_decisions.json"


def test_cancel_does_not_rerun(tmp_path: Path, monkeypatch) -> None:
    parser = cli.build_parser()
    args = parser.parse_args(
        [
            "build-drawing-card",
            "--inputs",
            "source.xlsx",
            "--output",
            "result.xlsx",
            "--interactive-review",
        ]
    )
    first = _result(tmp_path, status="BLOCKED", review_count=1)
    calls = []
    monkeypatch.setattr(cli, "run_workflow", lambda request: calls.append(request) or first)
    monkeypatch.setattr(
        cli,
        "collect_terminal_review",
        lambda _result: TerminalReviewOutcome({}, False, False),
    )

    assert cli._build_command(args) == 3
    assert len(calls) == 1
