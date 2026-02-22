# ────────────────────────────────────────────────────────────────────────────────────────
#   display.py
#   ──────────
#
#   Live terminal status display for pushfill. Uses Unicode box-drawing
#   characters and ANSI escape sequences for a polished, framed display
#   showing speed, progress, disk usage, and ETA.
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

import re
import shutil
import sys
import time
from typing import Callable
from typing import Optional
from pushfill.colour import bold
from pushfill.colour import cyan
from pushfill.colour import dim
from pushfill.colour import green
from pushfill.colour import magenta
from pushfill.colour import yellow

# ────────────────────────────────────────────────────────────────────────────────────────
#   Helpers
# ────────────────────────────────────────────────────────────────────────────────────────

EMA_ALPHA = 0.1  # smoothing factor — lower = slower, smoother rolling average


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
    seconds = max(0, int(seconds))
    if seconds < 3600:
        return f"{seconds // 60}:{seconds % 60:02d}"
    return f"{seconds // 3600}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"


# ────────────────────────────────────────────────────────────────────────────────────────
#   Display Class
# ────────────────────────────────────────────────────────────────────────────────────────


# ────────────────────────────────────────────────────────────────────────────────────────
class Display:
    """Live terminal display with box-drawn framing."""

    def __init__(
        self,
        target_path: str,
        target_size: Optional[int] = None,
        goal_bytes: Optional[int] = None,
        num_workers: int = 1,
        version: str = "dev",
    ) -> None:
        self._target_path = target_path
        self._target_size = target_size
        self._goal_bytes = goal_bytes
        self._num_workers = num_workers
        self._version = version
        self._start_time = time.monotonic()
        self._prev_total = 0
        self._prev_time = self._start_time
        self._ema_rate: Optional[float] = None
        self._lines_printed = 0

    # ──────────────────────────────────────────────────────────────────────────────────
    def set_goal(self, goal_bytes: Optional[int]) -> None:
        """Update the goal bytes (e.g. when purgeable space is reclaimed)."""
        self._goal_bytes = goal_bytes

    # ──────────────────────────────────────────────────────────────────────────────────
    def _move_up_and_clear(self) -> None:
        """Move cursor up to overwrite previous output."""
        if self._lines_printed > 0:
            sys.stdout.write(f"\033[{self._lines_printed}A\033[J")

    # ──────────────────────────────────────────────────────────────────────────────────
    def _get_bar(
        self,
        fraction: float,
        width: int,
        colour_fn: Optional[Callable[[str], str]] = None,
    ) -> str:
        """Render a progress bar with the given colour."""
        fraction = max(0.0, min(1.0, fraction))
        filled = int(fraction * width)
        empty = width - filled
        if colour_fn is None:
            colour_fn = green
        bar_fill = colour_fn("\u2588" * filled)
        bar_empty = dim("\u2591" * empty)
        return f"{bar_fill}{bar_empty}"

    # ──────────────────────────────────────────────────────────────────────────────────
    def _box_line(self, content: str, inner_w: int) -> str:
        """Wrap content in box borders, padding to inner_w visible characters."""
        visible = _strip_ansi(content)
        pad = inner_w - len(visible)
        if pad < 0:
            pad = 0
        border = dim("\u2502")
        return f"{border}  {content}{' ' * pad}  {border}"

    # ──────────────────────────────────────────────────────────────────────────────────
    def _box_top(self, inner_w: int) -> str:
        return dim("\u256d" + "\u2500" * (inner_w + 4) + "\u256e")

    def _box_sep(self, inner_w: int) -> str:
        return dim("\u251c" + "\u2500" * (inner_w + 4) + "\u2524")

    def _box_bottom(self, inner_w: int) -> str:
        return dim("\u2570" + "\u2500" * (inner_w + 4) + "\u256f")

    # ──────────────────────────────────────────────────────────────────────────────────
    def update(self, total_bytes: int) -> None:
        """Update the display with current progress (8 lines max)."""
        now = time.monotonic()
        elapsed = now - self._start_time
        dt = now - self._prev_time

        # Calculate rates
        if dt > 0:
            instant_rate = (total_bytes - self._prev_total) / dt
        else:
            instant_rate = 0.0

        # EMA smoothing (slow rolling average)
        if self._ema_rate is None:
            self._ema_rate = instant_rate
        else:
            self._ema_rate = EMA_ALPHA * instant_rate + (1 - EMA_ALPHA) * self._ema_rate

        if elapsed > 0:
            avg_rate = total_bytes / elapsed
        else:
            avg_rate = 0.0

        self._prev_total = total_bytes
        self._prev_time = now

        # Terminal width → inner box width
        term_width = shutil.get_terminal_size((80, 24)).columns
        inner_w = max(46, min(term_width - 6, 72))
        bar_width = max(10, inner_w - 10)

        # Build lines
        self._move_up_and_clear()
        lines: list[str] = []

        # Line 1: top border
        lines.append(self._box_top(inner_w))

        # Line 2: title + elapsed
        elapsed_str = format_time(elapsed)
        title_left = bold(cyan(f"pushfill {self._version}"))
        title_right = dim(f"Elapsed {elapsed_str}")
        title_pad = inner_w - _visible_len(title_left) - _visible_len(title_right)
        border = dim("\u2502")
        lines.append(
            f"{border}  {title_left}{' ' * max(1, title_pad)}{title_right}  {border}"
        )

        # Line 3: separator
        lines.append(self._box_sep(inner_w))

        # Line 4: speed (rolling average)
        ema = self._ema_rate or 0.0
        speed_mbs = ema / 1e6
        speed_gbps = ema * 8 / 1e9
        lines.append(
            self._box_line(
                f"{magenta(bold('Speed'))}     {cyan(f'{speed_mbs:,.1f} MB/s')}   "
                f"{dim(f'({speed_gbps:.2f} Gbps)')}",
                inner_w,
            )
        )

        # Line 5: average (total / elapsed)
        avg_mbs = avg_rate / 1e6
        avg_gbps = avg_rate * 8 / 1e9
        lines.append(
            self._box_line(
                f"{magenta(bold('Average'))}   {cyan(f'{avg_mbs:,.1f} MB/s')}   "
                f"{dim(f'({avg_gbps:.2f} Gbps)')}",
                inner_w,
            )
        )

        # Line 6: written + ETA (or disk %)
        if self._goal_bytes is not None and self._goal_bytes > 0:
            progress = min(total_bytes / self._goal_bytes, 1.0)
            size_str = f"{format_size(total_bytes)} / {format_size(self._goal_bytes)}"
            if avg_rate > 0 and progress < 1.0:
                eta_str = (
                    f"ETA {format_time((self._goal_bytes - total_bytes) / avg_rate)}"
                )
            else:
                eta_str = ""
            left = f"{magenta(bold('Written'))}   {cyan(size_str)}"
            right = yellow(eta_str) if eta_str else ""
        else:
            progress = 0.0
            left = f"{magenta(bold('Written'))}   {cyan(format_size(total_bytes))}"
            try:
                usage = shutil.disk_usage(self._target_path)
                disk_pct = usage.used / usage.total * 100 if usage.total > 0 else 0.0
                progress = disk_pct / 100.0
                right = dim(f"Disk {disk_pct:.1f}%")
            except OSError:
                right = ""

        pad = inner_w - _visible_len(left) - _visible_len(right)
        border = dim("\u2502")
        lines.append(f"{border}  {left}{' ' * max(1, pad)}{right}  {border}")

        # Line 7: progress bar
        pct_str = f"{progress * 100:.1f}%"
        prog_bar = self._get_bar(progress, bar_width, green)
        lines.append(self._box_line(f"{prog_bar}  {green(pct_str)}", inner_w))

        # Line 8: bottom border
        lines.append(self._box_bottom(inner_w))

        output = "\n".join(lines) + "\n"
        sys.stdout.write(output)
        sys.stdout.flush()
        self._lines_printed = len(lines)

    # ──────────────────────────────────────────────────────────────────────────────────
    def final_report(self, total_bytes: int, interrupted: bool = False) -> None:
        """Print the final summary."""
        elapsed = time.monotonic() - self._start_time
        avg_rate = total_bytes / elapsed if elapsed > 0 else 0.0
        avg_mbs = avg_rate / 1e6
        avg_gbps = avg_rate * 8 / 1e9

        if interrupted:
            # Don't clear the live display — append summary below it
            sys.stdout.write(
                f"\n  {yellow('Interrupted')} — wrote {cyan(format_size(total_bytes))} "
                f"in {bold(format_time(elapsed))} "
                f"({avg_mbs:,.1f} MB/s, {avg_gbps:.2f} Gbps) "
                f"across {self._num_workers} workers\n"
            )
            sys.stdout.flush()
            return

        # Normal completion — replace live display with summary box
        self._move_up_and_clear()
        self._lines_printed = 0

        term_width = shutil.get_terminal_size((80, 24)).columns
        inner_w = max(46, min(term_width - 6, 72))

        lines: list[str] = []
        lines.append(self._box_top(inner_w))
        lines.append(
            self._box_line(
                f"{bold(cyan(f'pushfill {self._version}'))}  {green('Done')} — "
                f"wrote {cyan(format_size(total_bytes))} "
                f"in {bold(format_time(elapsed))}",
                inner_w,
            )
        )
        lines.append(
            self._box_line(
                f"{magenta('Average:')} {cyan(f'{avg_mbs:,.1f} MB/s')} "
                f"{dim(f'({avg_gbps:.2f} Gbps)')} "
                f"across {self._num_workers} workers",
                inner_w,
            )
        )
        lines.append(self._box_bottom(inner_w))

        output = "\n".join(lines) + "\n"
        sys.stdout.write(output)
        sys.stdout.flush()


# ────────────────────────────────────────────────────────────────────────────────────────
#   ANSI Helpers
# ────────────────────────────────────────────────────────────────────────────────────────

_ANSI_RE = re.compile(r"\033\[[0-9;]*m")


def _strip_ansi(s: str) -> str:
    """Remove ANSI escape codes from a string."""
    return _ANSI_RE.sub("", s)


def _visible_len(s: str) -> int:
    """Return the visible length of a string (excluding ANSI codes)."""
    return len(_strip_ansi(s))
