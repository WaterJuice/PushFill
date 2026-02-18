# ────────────────────────────────────────────────────────────────────────────────────────
#   display.py
#   ──────────
#
#   Live terminal status display for pushfill. Uses ANSI escape sequences
#   to overwrite previous output, showing speed, progress, and disk usage.
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

import shutil
import sys
import time
from typing import Optional
from pushfill.colour import bold
from pushfill.colour import cyan
from pushfill.colour import dim
from pushfill.colour import green
from pushfill.colour import red
from pushfill.colour import yellow

# ────────────────────────────────────────────────────────────────────────────────────────
#   Helpers
# ────────────────────────────────────────────────────────────────────────────────────────


# ────────────────────────────────────────────────────────────────────────────────────────
def format_size(nbytes: int) -> str:
    """Format a byte count as a human-readable string."""
    if nbytes < 1024:
        return f"{nbytes} B"
    elif nbytes < 1024 * 1024:
        return f"{nbytes / 1024:.1f} KB"
    elif nbytes < 1024 * 1024 * 1024:
        return f"{nbytes / (1024 * 1024):.1f} MB"
    elif nbytes < 1024 * 1024 * 1024 * 1024:
        return f"{nbytes / (1024 * 1024 * 1024):.2f} GB"
    else:
        return f"{nbytes / (1024 * 1024 * 1024 * 1024):.2f} TB"


# ────────────────────────────────────────────────────────────────────────────────────────
def format_time(seconds: float) -> str:
    """Format seconds as h:mm:ss or m:ss."""
    seconds = int(seconds)
    if seconds < 3600:
        return f"{seconds // 60}:{seconds % 60:02d}"
    return f"{seconds // 3600}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"


# ────────────────────────────────────────────────────────────────────────────────────────
#   Display Class
# ────────────────────────────────────────────────────────────────────────────────────────


# ────────────────────────────────────────────────────────────────────────────────────────
class Display:
    """Live terminal display showing write progress and disk stats."""

    def __init__(
        self,
        target_path: str,
        target_size: Optional[int] = None,
        num_workers: int = 1,
    ) -> None:
        self._target_path = target_path
        self._target_size = target_size
        self._num_workers = num_workers
        self._start_time = time.monotonic()
        self._prev_total = 0
        self._prev_time = self._start_time
        self._lines_printed = 0

    def _move_up_and_clear(self) -> None:
        """Move cursor up to overwrite previous output."""
        if self._lines_printed > 0:
            sys.stdout.write(f"\033[{self._lines_printed}A\033[J")

    def _get_bar(self, fraction: float, width: int) -> str:
        """Render a progress bar."""
        filled = int(fraction * width)
        filled = max(0, min(filled, width))
        empty = width - filled
        bar_fill = green("\u2588" * filled)
        bar_empty = dim("\u2591" * empty)
        return f"{bar_fill}{bar_empty}"

    def update(self, total_bytes: int) -> None:
        """Update the display with current progress."""
        now = time.monotonic()
        elapsed = now - self._start_time
        dt = now - self._prev_time

        # Calculate rates
        if dt > 0:
            current_rate = (total_bytes - self._prev_total) / dt
        else:
            current_rate = 0.0

        if elapsed > 0:
            avg_rate = total_bytes / elapsed
        else:
            avg_rate = 0.0

        self._prev_total = total_bytes
        self._prev_time = now

        # Disk usage
        try:
            usage = shutil.disk_usage(self._target_path)
            disk_used = usage.used
            disk_total = usage.total
            disk_pct = (disk_used / disk_total * 100) if disk_total > 0 else 0.0
        except OSError:
            disk_used = 0
            disk_total = 0
            disk_pct = 0.0

        # Terminal width
        term_width = shutil.get_terminal_size((80, 24)).columns

        # Build output lines
        self._move_up_and_clear()
        lines: list[str] = []

        # Speed line
        rate_mbs = current_rate / 1e6
        rate_gbps = current_rate * 8 / 1e9
        avg_mbs = avg_rate / 1e6
        avg_gbps = avg_rate * 8 / 1e9
        lines.append(
            f"  {bold('Speed:')}  {cyan(f'{rate_mbs:,.1f} MB/s')} "
            f"({rate_gbps:.2f} Gbps)  "
            f"{dim('avg')} {avg_mbs:,.1f} MB/s ({avg_gbps:.2f} Gbps)"
        )

        # Written / elapsed line
        lines.append(
            f"  {bold('Written:')} {cyan(format_size(total_bytes))}  "
            f"{dim('elapsed')} {format_time(elapsed)}  "
            f"{dim('workers')} {self._num_workers}"
        )

        # Disk usage line with bar
        bar_width = min(30, term_width - 50)
        if bar_width < 5:
            bar_width = 5
        disk_bar = self._get_bar(disk_pct / 100.0, bar_width)
        disk_colour = green if disk_pct < 80 else (yellow if disk_pct < 95 else red)
        lines.append(
            f"  {bold('Disk:')}   {disk_bar} "
            f"{disk_colour(f'{disk_pct:.1f}%')}  "
            f"{format_size(disk_used)} / {format_size(disk_total)}"
        )

        # Target progress (if --size specified)
        if self._target_size is not None and self._target_size > 0:
            progress = total_bytes / self._target_size
            progress = min(progress, 1.0)
            pct = progress * 100

            # ETA
            if avg_rate > 0 and progress < 1.0:
                remaining = (self._target_size - total_bytes) / avg_rate
                eta_str = f"ETA {format_time(remaining)}"
            else:
                eta_str = ""

            prog_bar = self._get_bar(progress, bar_width)
            lines.append(
                f"  {bold('Target:')} {prog_bar} "
                f"{cyan(f'{pct:.1f}%')}  "
                f"{format_size(total_bytes)} / {format_size(self._target_size)}"
                f"  {dim(eta_str)}"
            )

        output = "\n".join(lines) + "\n"
        sys.stdout.write(output)
        sys.stdout.flush()
        self._lines_printed = len(lines)

    def final_report(self, total_bytes: int) -> None:
        """Print the final summary after completion."""
        elapsed = time.monotonic() - self._start_time
        avg_rate = total_bytes / elapsed if elapsed > 0 else 0.0
        avg_mbs = avg_rate / 1e6
        avg_gbps = avg_rate * 8 / 1e9

        self._move_up_and_clear()
        self._lines_printed = 0

        print()
        print(
            f"  {bold('Done.')} Wrote {cyan(format_size(total_bytes))} "
            f"in {format_time(elapsed)}"
        )
        print(
            f"  Average: {cyan(f'{avg_mbs:,.1f} MB/s')} "
            f"({avg_gbps:.2f} Gbps) across {self._num_workers} workers"
        )
        print()
