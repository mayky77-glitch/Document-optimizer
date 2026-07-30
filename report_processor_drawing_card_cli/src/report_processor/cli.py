"""Command-line entrypoint for report_processor."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter
from dataclasses import replace
from pathlib import Path

from report_processor.drawing_card.audit import atomic_write_json
from report_processor.drawing_card.models import WorkflowRequest
from report_processor.drawing_card.output import analyze_template, validate_card
from report_processor.drawing_card.review import (
    append_approved_examples,
    import_review_approvals,
)
from report_processor.drawing_card.review.io import review_approvals_payload
from report_processor.drawing_card.sources import (
    build_manifest,
    expand_input_globs,
    inspect_source,
    select_inspections,
)
from report_processor.drawing_card.sources.identity import load_object_map
from report_processor.drawing_card.workflow import (
    default_examples_path,
    default_rules_path,
    default_template_path,
    run_workflow,
)
from report_processor.terminal_review import (
    collect_terminal_review,
    save_terminal_review_decisions,
)


def _add_source_group(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--inputs", nargs="+", help="Explicit Excel files; shell globs are supported"
    )
    group.add_argument("--input-dir", type=Path, help="Directory containing Excel files")
    group.add_argument("--archive", type=Path, help="ZIP archive containing Excel files")


def _add_common_processing_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--period", help="Requested period in YYYY-MM format")
    parser.add_argument(
        "--object-map", type=Path, help="JSON mapping from paths/patterns to object indexes"
    )
    parser.add_argument("--rules", type=Path, default=default_rules_path())
    parser.add_argument("--examples", type=Path, default=default_examples_path())
    parser.add_argument(
        "--rag-mode", choices=("off", "suggest", "review_required"), default="suggest"
    )
    parser.add_argument("--model-config", type=Path)
    parser.add_argument("--review-decisions", type=Path)
    parser.add_argument("--objects-per-sheet", type=int, default=4)
    parser.add_argument(
        "--drawing-code-mode",
        choices=("preserve_group", "split_confirmed"),
        default="preserve_group",
    )
    parser.add_argument(
        "--remaining-strategy",
        choices=("direct_remaining_columns", "calculate_contract_minus_cumulative"),
        default="direct_remaining_columns",
    )
    parser.add_argument("--strict", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--work-dir", type=Path, default=Path("work"))
    parser.add_argument(
        "--log-level", default="INFO", choices=("DEBUG", "INFO", "WARNING", "ERROR")
    )


def _request_from_args(
    args: argparse.Namespace, *, dry_run_override: bool | None = None
) -> WorkflowRequest:
    inputs = expand_input_globs(args.inputs or ())
    dry_run = args.dry_run if dry_run_override is None else dry_run_override
    return WorkflowRequest(
        inputs=inputs,
        input_dir=args.input_dir,
        archive=args.archive,
        template=args.template,
        existing_card=args.existing_card,
        output=args.output,
        mode=args.mode,
        period=args.period,
        object_map=args.object_map,
        rules=args.rules,
        examples=args.examples,
        rag_mode=args.rag_mode,
        model_config=args.model_config,
        review_decisions=args.review_decisions,
        objects_per_sheet=args.objects_per_sheet,
        drawing_code_mode=args.drawing_code_mode,
        remaining_strategy=args.remaining_strategy,
        update_policy=args.update_policy,
        strict=args.strict,
        dry_run=dry_run,
        work_dir=args.work_dir,
        log_level=args.log_level,
    )


def _build_command(args: argparse.Namespace) -> int:
    request = _request_from_args(args)
    result = run_workflow(request)
    _print_workflow_result(result)
    if not args.interactive_review or result.status != "BLOCKED" or result.manual_review_count == 0:
        return _workflow_exit_code(result.status)

    outcome = collect_terminal_review(result)
    decisions_path = result.work_dir / "terminal_review_decisions.json"
    combined_decisions = {
        **import_review_approvals(request.review_decisions),
        **outcome.decisions,
    }
    if combined_decisions:
        save_terminal_review_decisions(decisions_path, combined_decisions)
        print(f"Review decisions: {decisions_path}")
    if not outcome.proceed:
        print("Card generation cancelled. Source files were not changed.")
        return 3

    reviewed_request = replace(
        request,
        review_decisions=decisions_path,
        strict=request.strict and not outcome.allow_partial,
    )
    reviewed = run_workflow(reviewed_request)
    print("\nResult after terminal review:")
    _print_workflow_result(reviewed)
    return _workflow_exit_code(reviewed.status)


def _print_workflow_result(result) -> None:
    print(f"Run ID: {result.run_id}")
    print(f"Status: {result.status}")
    print(f"Audit: {result.work_dir}")
    print(f"Excel sources: {len(result.manifest)}")
    print(f"Extracted rows: {result.extracted_row_count}")
    print(f"Card rows: {len(result.card_rows)}")
    print(f"Review rows: {result.manual_review_count}")
    if result.output_path:
        print(f"Result: {result.output_path}")
    if result.warnings:
        print(f"Warnings: {len(result.warnings)}")
        counts = Counter(warning.partition(":")[0] for warning in result.warnings)
        for code, count in counts.most_common(12):
            print(f"  - {code}: {count}")
        hidden = len(counts) - 12
        if hidden > 0:
            print(f"  - Other warning types: {hidden}")
        if result.manual_review_count:
            print(f"Review file: {result.work_dir / 'manual_review.xlsx'}")
        print(f"Details: {result.work_dir / 'source_selections.json'}")


def _workflow_exit_code(status: str) -> int:
    return 0 if status not in {"BLOCKED", "OUTPUT_VALIDATION_FAILED"} else 3


def _inspect_command(args: argparse.Namespace) -> int:
    inputs = expand_input_globs(args.inputs or ())
    manifest = build_manifest(inputs, args.input_dir, args.archive)
    mapping = load_object_map(args.object_map)
    inspections = []
    for entry in manifest:
        try:
            inspections.append(inspect_source(entry, object_mapping=mapping))
        except (OSError, ValueError, KeyError) as error:
            inspections.append({"entry": entry.logical_path, "error": str(error)})
    valid_inspections = [item for item in inspections if not isinstance(item, dict)]
    selected, selections, selection_warnings = select_inspections(
        valid_inspections,
        explicit_inputs=bool(inputs),
        requested_period=args.period,
    )
    output = args.output or Path("source_inspection.json")
    atomic_write_json(
        output,
        {
            "manifest": manifest,
            "inspections": inspections,
            "selections": selections,
            "selected_file_ids": [item.entry.file_id for item in selected],
            "selection_warnings": selection_warnings,
        },
    )
    print(f"Excel entries: {len(manifest)}")
    usable = 0
    unresolved = 0
    for item in inspections:
        if isinstance(item, dict):
            unresolved += 1
            continue
        if item.usable_schemas:
            usable += 1
        if not item.object_identity.value:
            unresolved += 1
        object_value = item.object_identity.value or "не определён"
        schema_names = (
            ", ".join(schema.sheet_name for schema in item.usable_schemas)
            or "нет подходящего листа"
        )
        print(f"  - {item.entry.filename}: объект {object_value}; листы: {schema_names}")
        for warning in item.warnings:
            print(f"      warning: {warning}")
    print(f"Usable sources: {usable}")
    print(f"Selected sources: {len(selected)}")
    for item in selected:
        print(f"  * {item.entry.filename}: выбран ({item.score:.2f})")
    for warning in selection_warnings:
        print(f"Selection warning: {warning}")
    print(f"Sources requiring attention: {unresolved}")
    print(f"Inspection report: {output.resolve()}")
    return 0 if selected else 3


def _prepare_review_command(args: argparse.Namespace) -> int:
    request = _request_from_args(args, dry_run_override=True)
    result = run_workflow(request)
    print(f"Run ID: {result.run_id}")
    print(f"Review: {result.work_dir / 'manual_review.xlsx'}")
    print(f"Audit: {result.work_dir}")
    print(f"Status: {result.status}")
    return _workflow_exit_code(result.status)


def _apply_review_command(args: argparse.Namespace) -> int:
    approvals = import_review_approvals(args.review)
    atomic_write_json(args.output, review_approvals_payload(approvals))
    added = 0
    if args.update_examples:
        added = append_approved_examples(
            args.review,
            args.examples,
            confirmed_by=args.confirmed_by,
            rule_version=args.rule_version,
        )
    print(f"Imported decisions: {len(approvals)}")
    print(f"Decision JSON: {args.output.resolve()}")
    if args.update_examples:
        print(f"Added confirmed examples: {added}")
    return 0


def _validate_command(args: argparse.Namespace) -> int:
    report = validate_card(args.card)
    if args.output:
        atomic_write_json(args.output, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "OK" else 4


def _analyze_template_command(args: argparse.Namespace) -> int:
    report = analyze_template(args.template)
    if args.output:
        atomic_write_json(args.output, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="report-processor")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser(
        "build-drawing-card", help="Create or update an audited drawing card"
    )
    _add_source_group(build)
    _add_common_processing_args(build)
    build.add_argument("--template", type=Path, default=default_template_path())
    build.add_argument("--existing-card", type=Path)
    build.add_argument("--output", type=Path)
    build.add_argument("--mode", choices=("create", "update"), default="create")
    build.add_argument(
        "--update-policy",
        choices=("fill_empty_only", "overwrite", "keep_existing", "conflicts_to_review"),
        default="fill_empty_only",
    )
    build.add_argument("--dry-run", action="store_true")
    build.add_argument(
        "--interactive-review",
        action="store_true",
        help="Resolve disputed rows in terminal and rerun once",
    )
    build.set_defaults(handler=_build_command)

    inspect = subparsers.add_parser(
        "inspect-drawing-sources", help="Inspect files, sheets and logical columns"
    )
    _add_source_group(inspect)
    inspect.add_argument("--object-map", type=Path)
    inspect.add_argument("--period", help="Requested period in YYYY-MM format")
    inspect.add_argument("--output", type=Path)
    inspect.set_defaults(handler=_inspect_command)

    review = subparsers.add_parser(
        "prepare-drawing-review", help="Run extraction and create review workbook only"
    )
    _add_source_group(review)
    _add_common_processing_args(review)
    review.add_argument("--template", type=Path, default=default_template_path())
    review.add_argument("--existing-card", type=Path)
    review.add_argument("--output", type=Path)
    review.add_argument("--mode", choices=("create", "update"), default="create")
    review.add_argument(
        "--update-policy",
        choices=("fill_empty_only", "overwrite", "keep_existing", "conflicts_to_review"),
        default="fill_empty_only",
    )
    review.add_argument("--dry-run", action="store_true", default=True)
    review.set_defaults(handler=_prepare_review_command)

    apply_review = subparsers.add_parser(
        "apply-drawing-review", help="Import user review decisions"
    )
    apply_review.add_argument("--review", type=Path, required=True)
    apply_review.add_argument("--output", type=Path, required=True)
    apply_review.add_argument("--examples", type=Path, default=default_examples_path())
    apply_review.add_argument("--update-examples", action="store_true")
    apply_review.add_argument("--confirmed-by", default="manual-user")
    apply_review.add_argument("--rule-version", default="1.0")
    apply_review.set_defaults(handler=_apply_review_command)

    validate_parser = subparsers.add_parser("validate-drawing-card", help="Validate a ready card")
    validate_parser.add_argument("--card", type=Path, required=True)
    validate_parser.add_argument("--output", type=Path)
    validate_parser.set_defaults(handler=_validate_command)

    template_parser = subparsers.add_parser(
        "analyze-drawing-template", help="Inspect template contract"
    )
    template_parser.add_argument("--template", type=Path, default=default_template_path())
    template_parser.add_argument("--output", type=Path)
    template_parser.set_defaults(handler=_analyze_template_command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, getattr(args, "log_level", "INFO")),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        return int(args.handler(args))
    except (FileNotFoundError, NotADirectoryError, ValueError, OSError) as error:
        logging.getLogger(__name__).error("%s", error)
        return 2


if __name__ == "__main__":
    sys.exit(main())
