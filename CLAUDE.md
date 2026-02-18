# CLAUDE.md

This file provides guidance for AI agents working on this project.

## Project Overview

pushfill is a single-purpose CLI tool that fills a disk with pseudo-random data as fast
as possible, then deletes the files. Used to push out old data from SSDs.

Uses multiprocessing with a seed XOR counter strategy for maximum throughput (~7 GB/s
on Apple Silicon). Each worker process generates its own random seed, then XORs with
an incrementing counter to produce data blocks and writes them directly to disk.

## Language and Spelling

Use **Australian English** throughout:
- colour (not color)
- initialise (not initialize)
- organisation (not organization)

## Code Style

### Python Files

- **Python 3.9+** — every file must have `from __future__ import annotations`
- stdlib only — zero external runtime dependencies
- Use type hints throughout (pyright strict mode)
- Prefer pathlib.Path over os.path
- Single-line imports, no blank lines between import groups (configured in pyproject.toml)
- Run `make format` to auto-fix import ordering

Every Python file should have:
1. A file header block with description, authors, and version history
2. Section headers separating major sections (Imports, Constants, Functions, etc.)
3. Horizontal separators (96 chars) above each function definition

Example structure:
```python
# ────────────────────────────────────────────────────────────────────────────────────────
#   filename.py
#   ───────────
#
#   Brief description of what this module does.
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
from __future__ import annotations

# ────────────────────────────────────────────────────────────────────────────────────────
#   Imports
# ────────────────────────────────────────────────────────────────────────────────────────

import sys
from pathlib import Path

# ────────────────────────────────────────────────────────────────────────────────────────
#   Functions
# ────────────────────────────────────────────────────────────────────────────────────────


# ────────────────────────────────────────────────────────────────────────────────────────
def my_function() -> None:
    """Docstring here."""
    pass
```

## Common Commands

```bash
make help       # Show all available targets
make check      # Run ruff + pyright
make format     # Auto-fix and format code
make build      # Build wheel into output/
make clean      # Remove build artefacts
make dev        # Just create dev (.venv) setup
```

## Project Structure

```
pushfill/
├── pushfill/             # Main package
│   ├── __init__.py       # Package init, exports __version__
│   ├── __main__.py       # Entry point for python -m pushfill
│   ├── argbuilder.py     # CLI argument parsing wrapper
│   ├── cli.py            # CLI entry point and argument parsing
│   ├── version.py        # Version string handling
│   ├── colour.py         # ANSI colour helpers
│   ├── display.py        # Live terminal status display
│   └── filler.py         # Core multiprocessing fill logic
├── Makefile              # Build automation
└── pyproject.toml        # Project metadata and dependencies
```

## Architecture

- **No subcommands** — single-purpose tool with flat argument list
- **Multiprocess workers** — each worker generates random data and writes to its own file
- **Seed XOR counter** — one `random.randbytes` call per worker at startup, then fast
  integer XOR with incrementing counter for all subsequent blocks
- **Shared counters** — `multiprocessing.Value(ctypes.c_uint64)` for progress tracking
- **OSError catch** — workers catch disk-full (ENOSPC) as normal termination

## Testing Changes

After making changes:
1. Run `make check` to verify linting and types pass
2. Run `make build` to verify the full build works
3. Test CLI with `uv run pushfill --help`
4. Test a small fill: `uv run pushfill /tmp --size 100M`

## Versioning

- Version is derived from git tags via Makefile
- Create a tag like `1.0.0` before running `make build` for a release (no `v` prefix)
- The Makefile generates `_version.py` at build time, which is not committed

## Commits

When committing:
- Use clear, descriptive commit messages
- Include `Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>` in commits made with AI assistance
- **Never rewrite git history** unless explicitly asked to

## Licence

Unlicense — public domain; see LICENSE in the project root.
