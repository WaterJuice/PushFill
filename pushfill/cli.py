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

import argparse
import os
import re
import signal
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

Each worker process writes its own file(s) using a seed-XOR-counter
strategy for maximum throughput using only the Python standard library.

Examples:
  pushfill                         # Fill current directory until disk is full
  pushfill /tmp                    # Fill /tmp until disk is full, then delete
  pushfill /tmp/fill.bin           # Write to a single file
  pushfill /tmp --size 10G         # Write 10 GB then delete
  pushfill /tmp --size 500M --keep # Write 500 MB and keep files
  pushfill /mnt/usb --fat32        # Fill a FAT32 drive (4 GiB file limit)
"""

LICENCE_TEXT = """\
This is free and unencumbered software released into the public domain.

Anyone is free to copy, modify, publish, use, compile, sell, or
distribute this software, either in source code form or as a compiled
binary, for any purpose, commercial or non-commercial, and by any
means.

In jurisdictions that recognize copyright laws, the author or authors
of this software dedicate any and all copyright interest in the
software to the public domain. We make this dedication for the benefit
of the public at large and to the detriment of our heirs and
successors. We intend this dedication to be an overt act of
relinquishment in perpetuity of all present and future rights to this
software under copyright law.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
OTHER DEALINGS IN THE SOFTWARE.

For more information, please refer to <https://unlicense.org>
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
        help="Directory or file path to fill (default: current directory)",
    )
    parser.add_argument(
        "-s",
        "--size",
        default=None,
        help="Target size to write (e.g. 10G, 500M, 1T). Default: fill disk",
    )
    parser.add_argument(
        "-k",
        "--keep",
        action="store_true",
        help="Keep generated files instead of deleting them",
    )
    parser.add_argument(
        "-w",
        "--workers",
        type=int,
        default=None,
        help="Number of worker processes (default: CPU count)",
    )
    parser.add_argument(
        "-c",
        "--chunk-size",
        type=int,
        default=4,
        help="Chunk size in MiB per write (default: 4)",
    )
    parser.add_argument(
        "-f",
        "--fat32",
        action="store_true",
        help="Limit each file to 4 GiB (for FAT32 filesystems)",
    )
    parser.add_argument(
        "-m",
        "--max-file-size",
        default=None,
        help="Maximum size per file (e.g. 2G). Overrides --fat32",
    )
    parser.add_argument(
        "-n",
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
    parser.add_argument(
        "--license",
        "--licence",
        action="store_true",
        dest="license",
        help=argparse.SUPPRESS,
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
        return 0  # Already handled gracefully by Filler
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
    from pushfill.filler import FAT32_MAX_FILE_SIZE
    from pushfill.filler import Filler
    from pushfill.filler import detect_filesystem_limit

    parser = create_parser()
    args: Namespace = parser.parse(argv)

    # Handle colour settings
    if args.no_colour:
        set_colours_enabled(False)

    # Hidden --license flag — print colourised licence and exit
    if args.license:
        from pushfill.colour import bold
        from pushfill.colour import cyan
        from pushfill.colour import dim
        from pushfill.colour import green
        from pushfill.colour import magenta
        from pushfill.colour import yellow

        print()
        print(f"  {bold(cyan(f'pushfill {VERSION_STR}'))}")
        print(f"  {dim('─' * 40)}")
        print()
        print(f"  {bold(green('This is free and unencumbered software'))}")
        print(f"  {green('released into the public domain.')}")
        print()
        print(
            f"  {cyan('Anyone is free to')} {bold(cyan('copy'))}{cyan(',')}"
            f" {bold(cyan('modify'))}{cyan(',')}"
            f" {bold(cyan('publish'))}{cyan(',')}"
            f" {bold(cyan('use'))}{cyan(',')}"
            f" {bold(cyan('compile'))}{cyan(',')}"
            f" {bold(cyan('sell'))}{cyan(', or')}"
        )
        print(f"  {cyan('distribute this software, either in source code form')}")
        print(
            f"  {cyan('or as a compiled binary, for')} {bold(cyan('any purpose'))}"
            f"{cyan(', commercial')}"
        )
        print(f"  {cyan('or non-commercial, and by any means.')}")
        print()
        print(f"  {magenta('In jurisdictions that recognize copyright laws,')}")
        print(f"  {magenta('the author or authors of this software dedicate')}")
        print(f"  {magenta('any and all copyright interest in the software to')}")
        print(f"  {magenta('the public domain.')}")
        print()
        warranty = (
            'THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY\n'
            "OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT\n"
            "LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS\n"
            "FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT."
        )
        for wline in warranty.splitlines():
            print(f"  {dim(wline)}")
        print()
        print(
            f"  {yellow('For more information:')} {bold(cyan('https://unlicense.org'))}"
        )
        print()
        return 0

    # Resolve target path — detect file vs directory
    raw_path = Path(args.path).resolve()
    output_path: Optional[Path] = None

    if raw_path.is_dir():
        target_dir = raw_path
    elif raw_path.is_file():
        # Existing file — single-file mode, overwrite
        target_dir = raw_path.parent
        output_path = raw_path
    elif raw_path.parent.is_dir():
        # Non-existent path with valid parent — single-file mode, create
        target_dir = raw_path.parent
        output_path = raw_path
    else:
        print(f"Error: {raw_path.parent} is not a directory", file=sys.stderr)
        return 1

    # Parse target size
    target_size: Optional[int] = None
    if args.size is not None:
        try:
            target_size = parse_size(args.size)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    # Determine max file size (explicit flags → auto-detect)
    max_file_size = 0
    if args.max_file_size is not None:
        try:
            max_file_size = parse_size(args.max_file_size)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
    elif args.fat32:
        max_file_size = FAT32_MAX_FILE_SIZE
    else:
        detected = detect_filesystem_limit(target_dir)
        if detected > 0:
            max_file_size = detected
            print("  Detected FAT32 filesystem — files limited to 4 GiB each")

    # Single-file mode on FAT32 won't work — can't fill the disk with one file
    if output_path is not None and max_file_size > 0:
        print(
            "Error: single-file mode is not compatible with FAT32 filesystems.\n"
            "       FAT32 has a 4 GiB per-file limit, so filling a disk requires\n"
            "       multiple files. Specify a directory path instead.",
            file=sys.stderr,
        )
        return 1

    # Single-file mode forces 1 worker
    if output_path is not None:
        num_workers = 1
    else:
        num_workers = (
            args.workers if args.workers is not None else (os.cpu_count() or 4)
        )
    if num_workers < 1:
        print("Error: --workers must be at least 1", file=sys.stderr)
        return 1

    # Chunk size (argument is in MiB)
    chunk_size = args.chunk_size * 1024 * 1024

    # Run with guaranteed cleanup
    filler = Filler(
        target_dir=target_dir,
        num_workers=num_workers,
        chunk_size=chunk_size,
        target_size=target_size,
        max_file_size=max_file_size,
        verbose=args.verbose,
        output_path=output_path,
        version=VERSION_STR,
    )

    try:
        filler.run()
    finally:
        # Ignore further Ctrl+C during cleanup — files must be deleted
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        if not args.keep:
            filler.cleanup()
        else:
            if output_path is not None:
                print(f"  File kept at {output_path}")
            else:
                print(f"  Files kept in {target_dir}")

    return 0
