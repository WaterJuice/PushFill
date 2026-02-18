# ────────────────────────────────────────────────────────────────────────────────────────
#   cli.py
#   ──────
#
#   CLI entry point for pushfill. Parses arguments and orchestrates the
#   disk fill operation.
#
#   (c) 2026 WaterJuice — Unlicense; see LICENSE in the project root.
#
#   Authors
#   ───────
#   bena (via Claude)
# ────────────────────────────────────────────────────────────────────────────────────────

# ────────────────────────────────────────────────────────────────────────────────────────
#   Imports
# ────────────────────────────────────────────────────────────────────────────────────────

import os
import re
import sys
import traceback
from pathlib import Path
from typing import Optional
from pushfill.argbuilder import ArgsParser
from pushfill.argbuilder import Namespace
from pushfill.version import VERSION_STR

# ────────────────────────────────────────────────────────────────────────────────────────
#   Descriptions
# ────────────────────────────────────────────────────────────────────────────────────────

DESCRIPTION = """\
Fill a disk with pseudo-random data as fast as possible, then clean up.

Designed to push out old data from SSDs by writing pseudo-random bytes
until the target size is reached or the disk is full.

Each worker process writes its own file using a seed-XOR-counter strategy
for maximum throughput using only the Python standard library.

Examples:
  pushfill /tmp                    # Fill /tmp until disk is full, then delete
  pushfill /tmp --size 10G         # Write 10 GB then delete
  pushfill /tmp --size 500M --keep # Write 500 MB and keep files
  pushfill . --workers 4           # Use 4 worker processes
"""

# ────────────────────────────────────────────────────────────────────────────────────────
#   Size Parsing
# ────────────────────────────────────────────────────────────────────────────────────────

_SIZE_UNITS = {
    "B": 1,
    "K": 1024,
    "KB": 1024,
    "M": 1024 * 1024,
    "MB": 1024 * 1024,
    "G": 1024 * 1024 * 1024,
    "GB": 1024 * 1024 * 1024,
    "T": 1024 * 1024 * 1024 * 1024,
    "TB": 1024 * 1024 * 1024 * 1024,
}


# ────────────────────────────────────────────────────────────────────────────────────────
def parse_size(s: str) -> int:
    """
    Parse a human-readable size string into bytes.

    Accepts formats like: 100M, 10G, 1T, 500MB, 1024, 4096B
    """
    s = s.strip().upper()
    m = re.match(r"^(\d+(?:\.\d+)?)\s*([A-Z]*)\s*$", s)
    if not m:
        raise ValueError(f"Invalid size: {s!r}")
    value = float(m.group(1))
    unit = m.group(2) or "B"
    if unit not in _SIZE_UNITS:
        raise ValueError(f"Unknown size unit: {unit!r}")
    return int(value * _SIZE_UNITS[unit])


# ────────────────────────────────────────────────────────────────────────────────────────
#   Argument Parsing
# ────────────────────────────────────────────────────────────────────────────────────────


# ────────────────────────────────────────────────────────────────────────────────────────
def create_parser() -> ArgsParser:
    """Create the argument parser."""
    parser = ArgsParser(
        prog="pushfill",
        description=DESCRIPTION,
        version=f"pushfill {VERSION_STR}",
    )

    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Directory to fill with data (default: current directory)",
    )
    parser.add_argument(
        "--size",
        default=None,
        help="Target size to write (e.g. 10G, 500M, 1T). Default: fill disk",
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="Keep generated files instead of deleting them",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Number of worker processes (default: CPU count)",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=4,
        help="Chunk size in MiB per write (default: 4)",
    )
    parser.add_argument(
        "--no-colour",
        "--no-color",
        action="store_true",
        dest="no_colour",
        help="Disable coloured output",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show verbose output",
    )

    return parser


# ────────────────────────────────────────────────────────────────────────────────────────
#   Main Entry Point
# ────────────────────────────────────────────────────────────────────────────────────────


# ────────────────────────────────────────────────────────────────────────────────────────
def main(argv: Optional[list[str]] = None) -> int:
    """
    Main entry point for pushfill CLI.

    Parameters:
        argv: Command line arguments (without program name). If None, uses sys.argv[1:].

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    if argv is None:
        argv = sys.argv[1:]

    try:
        return _main_inner(argv)
    except KeyboardInterrupt:
        print()
        print("---- Manually Terminated ----")
        print()
        return 1
    except SystemExit:
        raise
    except BaseException as e:
        t = "-----------------------------------------------------------------------------\n"
        t += "UNHANDLED EXCEPTION OCCURRED!!\n"
        t += "\n"
        t += traceback.format_exc()
        t += "\n"
        t += f"EXCEPTION: {type(e)} {e}\n"
        t += "-----------------------------------------------------------------------------\n"
        t += "\n"
        print(t, file=sys.stderr)
        return 1


# ────────────────────────────────────────────────────────────────────────────────────────
def _main_inner(argv: list[str]) -> int:
    """Inner main function that does the actual work."""
    from pushfill.colour import set_colours_enabled
    from pushfill.filler import Filler

    parser = create_parser()
    args: Namespace = parser.parse(argv)

    # If no args were given at all, help was shown
    if not argv:
        return 0

    # Handle colour settings
    if args.no_colour:
        set_colours_enabled(False)

    # Resolve target path
    target_dir = Path(args.path).resolve()
    if not target_dir.is_dir():
        print(f"Error: {target_dir} is not a directory", file=sys.stderr)
        return 1

    # Parse target size
    target_size: Optional[int] = None
    if args.size is not None:
        try:
            target_size = parse_size(args.size)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    # Determine worker count
    num_workers = args.workers if args.workers is not None else (os.cpu_count() or 4)
    if num_workers < 1:
        print("Error: --workers must be at least 1", file=sys.stderr)
        return 1

    # Chunk size (argument is in MiB)
    chunk_size = args.chunk_size * 1024 * 1024

    # Run
    filler = Filler(
        target_dir=target_dir,
        num_workers=num_workers,
        chunk_size=chunk_size,
        target_size=target_size,
        verbose=args.verbose,
    )

    filler.run()

    if not args.keep:
        filler.cleanup()
    else:
        print(f"  Files kept in {target_dir}")

    return 0
