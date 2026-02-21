# ────────────────────────────────────────────────────────────────────────────────────────
#   filler.py
#   ─────────
#
#   Core multiprocess disk fill logic. Each worker process writes pseudo-random
#   data to its own file(s) using the seed-XOR-counter strategy for maximum
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
import shutil
import signal
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
FAT32_MAX_FILE_SIZE = (1 << 32) - 1  # 4 GiB - 1 byte
MIN_SCRUB_SIZE = 512  # smallest write attempt during scrub phase

# Known FAT-family filesystem type names (lowercase) for auto-detection
_FAT_FSTYPES = frozenset({"msdos", "vfat", "fat32", "fat16", "fat"})

# ────────────────────────────────────────────────────────────────────────────────────────
#   Filesystem Detection
# ────────────────────────────────────────────────────────────────────────────────────────


# ────────────────────────────────────────────────────────────────────────────────────────
def detect_filesystem_limit(target_dir: Path) -> int:
    """
    Auto-detect filesystem file size limits for the given path.

    Returns FAT32_MAX_FILE_SIZE if a FAT-family filesystem is detected,
    otherwise returns 0 (no limit).
    """
    import platform

    try:
        system = platform.system()
        if system == "Darwin":
            return _detect_fat_darwin(str(target_dir))
        if system == "Linux":
            return _detect_fat_linux(str(target_dir))
        if system == "Windows":
            return _detect_fat_windows(target_dir)
    except Exception:
        pass
    return 0


# ────────────────────────────────────────────────────────────────────────────────────────
def _detect_fat_darwin(path: str) -> int:
    """Detect FAT filesystem on macOS via ctypes statfs(2)."""
    import ctypes.util

    class _StatFS(ctypes.Structure):
        _fields_ = [  # pyright: ignore[reportIncompatibleVariableOverride]
            ("f_bsize", ctypes.c_uint32),
            ("f_iosize", ctypes.c_int32),
            ("f_blocks", ctypes.c_uint64),
            ("f_bfree", ctypes.c_uint64),
            ("f_bavail", ctypes.c_uint64),
            ("f_files", ctypes.c_uint64),
            ("f_ffree", ctypes.c_uint64),
            ("f_fsid", ctypes.c_int32 * 2),
            ("f_owner", ctypes.c_uint32),
            ("f_type", ctypes.c_uint32),
            ("f_flags", ctypes.c_uint32),
            ("f_fssubtype", ctypes.c_uint32),
            ("f_fstypename", ctypes.c_char * 16),
            ("f_mntonname", ctypes.c_char * 1024),
            ("f_mntfromname", ctypes.c_char * 1024),
            ("f_flags_ext", ctypes.c_uint32),
            ("f_reserved", ctypes.c_uint32 * 7),
        ]

    libc_name = ctypes.util.find_library("c")
    if libc_name is None:
        return 0
    libc = ctypes.CDLL(libc_name)
    buf = _StatFS()
    ret: int = libc.statfs(path.encode("utf-8"), ctypes.byref(buf))
    if ret != 0:
        return 0
    raw: bytes = buf.f_fstypename  # type: ignore[assignment]
    fstype = raw.decode("ascii", errors="ignore").rstrip("\x00").lower()
    if fstype in _FAT_FSTYPES:
        return FAT32_MAX_FILE_SIZE
    return 0


# ────────────────────────────────────────────────────────────────────────────────────────
def _detect_fat_linux(path: str) -> int:
    """Detect FAT filesystem on Linux by reading /proc/mounts."""
    best_mount = ""
    best_fstype = ""
    try:
        with open("/proc/mounts") as f:
            for line in f:
                parts = line.split()
                if len(parts) < 3:
                    continue
                mount_point = parts[1].replace("\\040", " ")
                fstype = parts[2].lower()
                if mount_point == "/":
                    matches = True
                else:
                    matches = path == mount_point or path.startswith(mount_point + "/")
                if matches and len(mount_point) > len(best_mount):
                    best_mount = mount_point
                    best_fstype = fstype
    except OSError:
        return 0
    if best_fstype in _FAT_FSTYPES:
        return FAT32_MAX_FILE_SIZE
    return 0


# ────────────────────────────────────────────────────────────────────────────────────────
def _detect_fat_windows(target_dir: Path) -> int:
    """Detect FAT filesystem on Windows via GetVolumeInformationW."""
    root = str(target_dir.anchor)
    if not root:
        return 0
    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    fs_name_buf = ctypes.create_unicode_buffer(256)
    ret: int = kernel32.GetVolumeInformationW(  # type: ignore[union-attr]
        root, None, 0, None, None, None, fs_name_buf, 256
    )
    if not ret:
        return 0
    fsname: str = fs_name_buf.value.strip().lower()
    if fsname in _FAT_FSTYPES:
        return FAT32_MAX_FILE_SIZE
    return 0


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
    max_file_size: int,
    max_bytes: int,
    output_path: str,
) -> None:
    """
    Worker process that writes pseudo-random data to file(s).

    Uses seed-XOR-counter strategy: generate one random seed at startup,
    then XOR with an incrementing counter for each subsequent block.

    When ENOSPC is hit, enters a scrub phase writing progressively smaller
    chunks until the disk is truly full. If max_file_size > 0, rotates to
    a new file when the current one reaches the limit.

    If output_path is non-empty, writes to that exact file (single-file mode).
    """
    # Ignore SIGINT in workers — main process handles shutdown via stop flag
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    base = int.from_bytes(random.randbytes(chunk_size), "little")
    stride = (1 << (chunk_size * 4)) | 0xDEADBEEF
    n = 0
    local_written = 0
    file_seq = 0
    file_bytes = 0

    def _open_file() -> int:
        """Open the next output file, return the fd."""
        nonlocal file_seq, file_bytes
        if output_path:
            file_bytes = 0
            return os.open(output_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
        path = os.path.join(target_dir, f"pushfill_{worker_id:04d}_{file_seq:04d}.bin")
        file_seq += 1
        file_bytes = 0
        return os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)

    def _write_chunk(data: bytes) -> bool:
        """Write data, rotating files if max_file_size exceeded. Returns False on ENOSPC."""
        nonlocal fd_current, file_bytes, local_written
        remaining = data
        while remaining:
            # Check file size limit
            if max_file_size > 0 and file_bytes >= max_file_size:
                os.close(fd_current)
                fd_current = _open_file()

            # Cap write to file size limit
            write_size = len(remaining)
            if max_file_size > 0:
                write_size = min(write_size, max_file_size - file_bytes)

            to_write = remaining[:write_size]
            try:
                written = os.write(fd_current, to_write)
                file_bytes += written
                local_written += written
                counter.value = local_written  # type: ignore[union-attr]
                remaining = remaining[written:]
            except OSError as e:
                if e.errno == errno.ENOSPC:
                    return False
                if e.errno == errno.EFBIG:
                    if output_path:
                        return False  # Single-file mode — can't rotate
                    os.close(fd_current)
                    fd_current = _open_file()
                    continue
                raise
        return True

    try:
        fd_current = _open_file()

        # Main phase: write full chunks
        while not stop.value:  # type: ignore[union-attr]
            if max_bytes > 0 and local_written >= max_bytes:
                break
            data = (base ^ (stride * n)).to_bytes(chunk_size, "little")
            n += 1
            if max_bytes > 0:
                remaining_budget = max_bytes - local_written
                if remaining_budget < chunk_size:
                    data = data[:remaining_budget]
            if not _write_chunk(data):
                break

        # Scrub phase: fill remaining space with progressively smaller writes
        # Only scrub if we weren't stopped by target size or interrupt
        if not stop.value and not (max_bytes > 0 and local_written >= max_bytes):  # type: ignore[union-attr]
            scrub_size = chunk_size // 2
            while scrub_size >= MIN_SCRUB_SIZE and not stop.value:  # type: ignore[union-attr]
                data = (base ^ (stride * n)).to_bytes(chunk_size, "little")
                n += 1
                scrub_data = data[:scrub_size]
                if not _write_chunk(scrub_data):
                    scrub_size //= 2
                    continue

        os.close(fd_current)
    except (KeyboardInterrupt, BrokenPipeError):
        pass
    except OSError:
        pass


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
        max_file_size: int = 0,
        verbose: bool = False,
        output_path: Optional[Path] = None,
    ) -> None:
        self._target_dir = target_dir
        self._num_workers = num_workers
        self._chunk_size = chunk_size
        self._target_size = target_size
        self._max_file_size = max_file_size
        self._verbose = verbose
        self._output_path = output_path
        self._counters: list[Any] = []
        self._stop: Any = None
        self._processes: list[Process] = []
        self._interrupted = False

    def run(self) -> int:
        """Run the fill operation. Returns total bytes written."""
        # Snapshot initial disk free space for progress estimation
        try:
            usage = shutil.disk_usage(str(self._target_dir))
            initial_free = usage.free
        except OSError:
            initial_free = 0

        # Create shared state
        self._counters = [
            Value(ctypes.c_uint64, 0, lock=False)  # type: ignore[arg-type]
            for _ in range(self._num_workers)
        ]
        self._stop = Value(ctypes.c_bool, False, lock=False)  # type: ignore[arg-type]

        # Install SIGINT handler in main process
        original_sigint = signal.getsignal(signal.SIGINT)

        def _sigint_handler(_signum: int, _frame: Any) -> None:
            self._stop.value = True  # type: ignore[union-attr]
            self._interrupted = True

        signal.signal(signal.SIGINT, _sigint_handler)

        # Calculate per-worker byte budget
        if self._target_size is not None:
            per_worker = self._target_size // self._num_workers
            remainder = self._target_size % self._num_workers
        else:
            per_worker = 0  # 0 = unlimited (fill until disk full)
            remainder = 0

        # Spawn workers
        for i in range(self._num_workers):
            worker_max = per_worker + (remainder if i == self._num_workers - 1 else 0)
            # Only the first worker gets the output_path (single-file mode)
            worker_output = (
                str(self._output_path) if self._output_path and i == 0 else ""
            )
            p = Process(
                target=_worker,
                args=(
                    i,
                    str(self._target_dir),
                    self._chunk_size,
                    self._counters[i],
                    self._stop,
                    self._max_file_size,
                    worker_max,
                    worker_output,
                ),
                daemon=True,
            )
            p.start()
            self._processes.append(p)

        # Determine the goal for progress display
        if self._target_size is not None:
            goal = self._target_size
        else:
            goal = initial_free if initial_free > 0 else None

        # Monitor loop
        display = Display(
            target_path=str(self._target_dir),
            target_size=self._target_size,
            goal_bytes=goal,
            num_workers=self._num_workers,
        )

        try:
            while not self._interrupted:
                time.sleep(UPDATE_INTERVAL)
                total = sum(
                    int(c.value)
                    for c in self._counters  # type: ignore[union-attr]
                )
                display.update(total)

                # Check if all workers have exited (disk full / done)
                if all(not p.is_alive() for p in self._processes):
                    break

                # Check if target size reached
                if self._target_size is not None and total >= self._target_size:
                    self._stop.value = True  # type: ignore[union-attr]
                    break
        except KeyboardInterrupt:
            self._stop.value = True  # type: ignore[union-attr]
            self._interrupted = True

        # Wait for workers to finish
        self._stop.value = True  # type: ignore[union-attr]
        for p in self._processes:
            p.join(timeout=3)

        # Restore original SIGINT handler
        signal.signal(signal.SIGINT, original_sigint)  # type: ignore[arg-type]

        total = sum(int(c.value) for c in self._counters)  # type: ignore[union-attr]
        display.final_report(total, interrupted=self._interrupted)
        return total

    def cleanup(self) -> None:
        """Delete generated files."""
        if self._output_path is not None:
            try:
                self._output_path.unlink()
                print("  Cleaned up 1 file.")
            except OSError:
                pass
            return
        count = 0
        for f in self._target_dir.glob("pushfill_*.bin"):
            try:
                f.unlink()
                count += 1
            except OSError:
                pass
        if count > 0:
            print(f"  Cleaned up {count} file(s).")
