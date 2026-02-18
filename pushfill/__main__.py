# ────────────────────────────────────────────────────────────────────────────────────────
#   __main__.py
#   ───────────
#
#   Entry point for python -m pushfill.
#
#   (c) 2026 WaterJuice — Unlicense; see LICENSE in the project root.
#
#   Authors
#   ───────
#   bena (via Claude)
#
#   Version History
#   ───────────────
#   Feb 2026 - Created
# ────────────────────────────────────────────────────────────────────────────────────────

import sys

MIN_PYTHON = (3, 9)
if sys.version_info < MIN_PYTHON:
    print(
        f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ is required. "
        f"You are using Python {sys.version_info.major}.{sys.version_info.minor}.",
        file=sys.stderr,
    )
    sys.exit(1)

from pushfill.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
