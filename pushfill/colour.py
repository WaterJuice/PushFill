# ────────────────────────────────────────────────────────────────────────────────────────
#   colour.py
#   ─────────
#
#   ANSI colour output for terminal. Only applies colours when stdout is a TTY
#   and colours are not disabled.
#
#   Uses colours that work well on both light and dark backgrounds.
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

import sys
from typing import Optional

# ────────────────────────────────────────────────────────────────────────────────────────
#   ANSI Codes
# ────────────────────────────────────────────────────────────────────────────────────────

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"

# ────────────────────────────────────────────────────────────────────────────────────────
#   State
# ────────────────────────────────────────────────────────────────────────────────────────

_colours_enabled: Optional[bool] = None

# ────────────────────────────────────────────────────────────────────────────────────────
#   Functions
# ────────────────────────────────────────────────────────────────────────────────────────


# ────────────────────────────────────────────────────────────────────────────────────────
def set_colours_enabled(enabled: bool) -> None:
    """Explicitly enable or disable colours."""
    global _colours_enabled
    _colours_enabled = enabled


# ────────────────────────────────────────────────────────────────────────────────────────
def _should_use_colours() -> bool:
    """Determine if colours should be used."""
    global _colours_enabled

    if _colours_enabled is not None:
        return _colours_enabled

    return sys.stdout.isatty()


# ────────────────────────────────────────────────────────────────────────────────────────
def green(text: str) -> str:
    """Return text in green."""
    if _should_use_colours():
        return f"{GREEN}{text}{RESET}"
    return text


# ────────────────────────────────────────────────────────────────────────────────────────
def yellow(text: str) -> str:
    """Return text in yellow."""
    if _should_use_colours():
        return f"{YELLOW}{text}{RESET}"
    return text


# ────────────────────────────────────────────────────────────────────────────────────────
def red(text: str) -> str:
    """Return text in red."""
    if _should_use_colours():
        return f"{RED}{text}{RESET}"
    return text


# ────────────────────────────────────────────────────────────────────────────────────────
def cyan(text: str) -> str:
    """Return text in cyan."""
    if _should_use_colours():
        return f"{CYAN}{text}{RESET}"
    return text


# ────────────────────────────────────────────────────────────────────────────────────────
def magenta(text: str) -> str:
    """Return text in magenta."""
    if _should_use_colours():
        return f"{MAGENTA}{text}{RESET}"
    return text


# ────────────────────────────────────────────────────────────────────────────────────────
def bold(text: str) -> str:
    """Return text in bold."""
    if _should_use_colours():
        return f"{BOLD}{text}{RESET}"
    return text


# ────────────────────────────────────────────────────────────────────────────────────────
def dim(text: str) -> str:
    """Return text in dim."""
    if _should_use_colours():
        return f"{DIM}{text}{RESET}"
    return text
