"""Direct source-tree launcher; package installation is optional."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from report_processor.cli import main as cli_main  # noqa: E402

if __name__ == "__main__":
    if len(sys.argv) == 1:
        from report_processor.terminal_ui import run  # noqa: E402

        raise SystemExit(run(cli_main))
    raise SystemExit(cli_main())
