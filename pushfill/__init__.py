# ────────────────────────────────────────────────────────────────────────────────────────
#   pushfill
#   ────────
#
#   Fill a disk with random data to push out old SSD data.
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

# ────────────────────────────────────────────────────────────────────────────────────────
#   Version
# ────────────────────────────────────────────────────────────────────────────────────────

from .version import VERSION_STR

__version__ = VERSION_STR
__all__ = ["__version__"]
