# 2.0.0 — 23 Feb 2026

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

# 1.0.0 — February 2018

Original C implementation.

- Single-threaded design using RC4 encryption for seed generation
- 10 MB random block written 256 times with byte increment per iteration
- Cross-platform: Windows, macOS, Linux (x64 and ARM)
- See [blog post](https://waterjuiceweb.wordpress.com/2018/02/16/pushing-old-data-off-a-disc/)
