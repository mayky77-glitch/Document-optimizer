"""Private descriptive same-corpus candidate evaluator."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from report_processor.reconciliation_patterns.offline import (
    OfflineContractError,
    evaluate_candidates,
    fingerprint,
    load_candidate_jsonl,
    load_corpus_jsonl,
    write_evaluation,
)


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        self.exit(2, f"USAGE_INVALID: {message}\n")


def _aliases(left: Path, right: Path) -> bool:
    try:
        return left.resolve(strict=False) == right.resolve(strict=False)
    except OSError as exc:
        raise OfflineContractError("OUTPUT_UNSAFE", "output is unsafe") from exc


def main(argv: list[str] | None = None) -> int:
    parser = _Parser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--candidates", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--overwrite", action="store_true")
    try:
        args = parser.parse_args(argv)
        if _aliases(args.output, args.input) or _aliases(args.output, args.candidates):
            raise OfflineContractError("OUTPUT_UNSAFE", "output is unsafe")
        result = evaluate_candidates(
            load_corpus_jsonl(args.input), load_candidate_jsonl(args.candidates)
        )
        write_evaluation(args.output, result, overwrite=args.overwrite)
        print(f"OK {result.version} {fingerprint(result)}")
        return 0
    except OfflineContractError as exc:
        print(f"{exc.code}: {exc}", file=sys.stderr)
        if exc.code == "INVARIANT_VIOLATION":
            return 5
        return 4 if exc.code.startswith("OUTPUT_") else 3
    except SystemExit:
        raise
    except Exception:
        print("INVARIANT_VIOLATION: internal invariant failed", file=sys.stderr)
        return 5


if __name__ == "__main__":
    raise SystemExit(main())
