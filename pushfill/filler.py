# ────────────────────────────────────────────────────────────────────────────────────────
#   filler.py
#   ─────────
#
#   Core multiprocess disk fill logic. Each worker process writes pseudo-random
#   data to its own file using the seed-XOR-counter strategy for maximum
#   throughput with stdlib only.
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

import ctypes
import errno
import os
import random
import time
from multiprocessing import Process
from multiprocessing import Value
from pathlib import Path
from typing import Any
from typing import Optional
from pushfill.display import Display

# ────────────────────────────────────────────────────────────────────────────────────────
#   Constants
# ────────────────────────────────────────────────────────────────────────────────────────

DEFAULT_CHUNK_SIZE = 4 * 1024 * 1024  # 4 MiB
UPDATE_INTERVAL = 0.5  # seconds between display updates

# ────────────────────────────────────────────────────────────────────────────────────────
#   Worker Function (module-level for macOS spawn compatibility)
# ────────────────────────────────────────────────────────────────────────────────────────


# ────────────────────────────────────────────────────────────────────────────────────────
def _worker(
    worker_id: int,
    target_dir: str,
    chunk_size: int,
    counter: "ctypes.c_uint64",  # type: ignore[type-arg]
    stop: "ctypes.c_bool",  # type: ignore[type-arg]
    max_bytes: int,
) -> None:
    """
    Worker process that writes pseudo-random data to a file.

    Uses seed-XOR-counter strategy: generate one random seed at startup,
    then XOR with an incrementing counter for each subsequent block.
    """
    filepath = os.path.join(target_dir, f"pushfill_{worker_id:04d}.bin")
    base = int.from_bytes(random.randbytes(chunk_size), "little")
    stride = (1 << (chunk_size * 4)) | 0xDEADBEEF
    n = 0
    local_written = 0

    try:
        with open(filepath, "wb") as f:
            while not stop.value:  # type: ignore[union-attr]
                if max_bytes > 0 and local_written >= max_bytes:
                    break
                data = (base ^ (stride * n)).to_bytes(chunk_size, "little")
                if max_bytes > 0:
                    remaining = max_bytes - local_written
                    if remaining < chunk_size:
                        data = data[:remaining]
                f.write(data)
                n += 1
                local_written += len(data)
                counter.value = local_written  # type: ignore[union-attr]
    except OSError as e:
        if e.errno == errno.ENOSPC:
            # Disk full — expected outcome
            pass
        else:
            raise


# ────────────────────────────────────────────────────────────────────────────────────────
#   Filler Class
# ────────────────────────────────────────────────────────────────────────────────────────


# ────────────────────────────────────────────────────────────────────────────────────────
class Filler:
    """Orchestrates multiprocess disk filling."""

    def __init__(
        self,
        target_dir: Path,
        num_workers: int,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        target_size: Optional[int] = None,
        verbose: bool = False,
    ) -> None:
        self._target_dir = target_dir
        self._num_workers = num_workers
        self._chunk_size = chunk_size
        self._target_size = target_size
        self._verbose = verbose
        self._counters: list[Any] = []
        self._stop: Any = None
        self._processes: list[Process] = []

    def run(self) -> int:
        """
        Run the fill operation. Returns total bytes written.
        """
        # Calculate per-worker byte limit
        if self._target_size is not None:
            per_worker = self._target_size // self._num_workers
            # Give remainder to last worker
            remainder = self._target_size % self._num_workers
        else:
            per_worker = 0  # 0 = unlimited (fill until disk full)
            remainder = 0

        # Create shared state
        self._counters = [
            Value(ctypes.c_uint64, 0, lock=False)  # type: ignore[arg-type]
            for _ in range(self._num_workers)
        ]
        self._stop = Value(ctypes.c_bool, False, lock=False)  # type: ignore[arg-type]

        # Spawn workers
        for i in range(self._num_workers):
            worker_max = per_worker + (remainder if i == self._num_workers - 1 else 0)
            p = Process(
                target=_worker,
                args=(
                    i,
                    str(self._target_dir),
                    self._chunk_size,
                    self._counters[i],
                    self._stop,
                    worker_max,
                ),
                daemon=True,
            )
            p.start()
            self._processes.append(p)

        # Monitor loop
        display = Display(
            target_path=str(self._target_dir),
            target_size=self._target_size,
            num_workers=self._num_workers,
        )

        try:
            while True:
                time.sleep(UPDATE_INTERVAL)
                total = sum(c.value for c in self._counters)  # type: ignore[union-attr]
                display.update(total)

                # Check if all workers have exited
                if all(not p.is_alive() for p in self._processes):
                    break

                # Check if target reached
                if self._target_size is not None and total >= self._target_size:
                    break
        except KeyboardInterrupt:
            pass

        # Stop workers
        self._stop.value = True  # type: ignore[union-attr]
        for p in self._processes:
            p.join(timeout=5)

        total = sum(c.value for c in self._counters)  # type: ignore[union-attr]
        display.final_report(total)
        return total

    def cleanup(self) -> None:
        """Delete all pushfill_*.bin files from the target directory."""
        count = 0
        for f in self._target_dir.glob("pushfill_*.bin"):
            try:
                f.unlink()
                count += 1
            except OSError:
                pass
        if count > 0:
            print(f"  Cleaned up {count} file(s).")
