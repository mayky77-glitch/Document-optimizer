"""Private offline inert candidate miner."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from report_processor.reconciliation_patterns.offline import (
    OfflineContractError,
    fingerprint,
    load_corpus_jsonl,
    mine_candidates,
    write_candidates,
)


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        self.exit(2, f"USAGE_INVALID: {message}\n")


def _positive(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a positive integer") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def _aliases(left: Path, right: Path) -> bool:
    try:
        return left.resolve(strict=False) == right.resolve(strict=False)
    except OSError as exc:
        raise OfflineContractError("OUTPUT_UNSAFE", "output is unsafe") from exc


def main(argv: list[str] | None = None) -> int:
    parser = _Parser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--min-support-atoms", type=_positive, default=2)
    parser.add_argument("--overwrite", action="store_true")
    try:
        args = parser.parse_args(argv)
        if _aliases(args.input, args.output):
            raise OfflineContractError("OUTPUT_UNSAFE", "output is unsafe")
        result = mine_candidates(
            load_corpus_jsonl(args.input), min_support_atoms=args.min_support_atoms
        )
        write_candidates(args.output, result, overwrite=args.overwrite)
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
