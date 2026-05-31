# pushfill 3.0.1 — 31 May 2026

Moved to new GitHub location: https://github.com/WaterJuice/pushfill

# pushfill 3.0.0 — 31 Mar 2026

Complete rewrite in Go, replacing the Python implementation.

### Added

- Go binary — single static executable, zero runtime dependencies
- Cross-platform wheels for macOS, Linux, and Windows (amd64 + arm64)
- `crypto/rand` for random data generation — simple, fast, and cryptographically secure
- Goroutine-based workers replace Python multiprocessing

### Changed

- Rewritten from Python to Go
- Distributed as a compiled Go binary via PyPI using `bin2whl`
- No Python runtime required — install with `uv tool install pushfill` or `pip install pushfill`
- Random generation simplified from pool-based XOR multiplication to direct `crypto/rand`
- Workers use goroutines instead of multiprocessing + background writer threads

### Removed

- Python source code and all Python-specific tooling (ruff, pyright, argparse wrapper)
- Pool-based random generation with XOR multiplication (no longer needed for performance)
- Background writer thread per worker (Go handles concurrency natively)

# pushfill 2.0.0 — 23 Feb 2026

Complete rewrite in Python, replacing the original C implementation.

### Added

- Multiprocess architecture — one worker per CPU core for maximum throughput
- Pool-based random generation with XOR multiplication
- Background writer thread — overlaps disk I/O with data generation per worker
- Live terminal UI with colourful box-drawn display, speed, progress bar, and ETA
- FAT32 auto-detection on macOS, Linux, and Windows
- `--fat32` flag and `--max-file-size` option for manual file size limits
- Single-file mode — write to a specific file path instead of a directory
- Scrub phase — fills last bytes with progressively smaller writes
- Dynamic progress tracking — rechecks disk free space as OS purges caches
- Graceful Ctrl+C shutdown with guaranteed file cleanup
- `--keep` flag to retain generated files after completion
- Short flags for all options (`-s`, `-k`, `-w`, `-c`, `-f`, `-m`, `-n`, `-v`)
- `--license` flag (hidden) to display the Unlicense text
- mkdocs-material documentation site

### Changed

- Rewritten from C to Python (stdlib only, zero dependencies)
- Data generation changed from RC4 + byte increment to pool-based random with XOR multiplication

# pushfill 1.0.0 — February 2018

Original C implementation.

- Single-threaded design using RC4 encryption for seed generation
- 10 MB random block written 256 times with byte increment per iteration
- Cross-platform: Windows, macOS, Linux (x64 and ARM)
- See [blog post](https://waterjuiceweb.wordpress.com/2018/02/16/pushing-old-data-off-a-disc/)
