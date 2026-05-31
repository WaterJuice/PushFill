# How It Works

## Overview

pushfill uses multiple goroutine workers to write pseudo-random data to disk
files as fast as possible. The goal is to overwrite every available block on
the drive with unique, non-compressible data.

## Random Data Generation

Each worker generates random data using Go's `crypto/rand` package, which
provides cryptographically secure random bytes. Since Go is a compiled
language with efficient concurrency primitives, there is no need for the
complex pool-based XOR multiplication that the Python version used — direct
`crypto/rand` reads are fast enough to saturate disk I/O.

### Why not write zeroes?

SSD controllers are smart. Many can detect all-zero blocks and simply store
a flag rather than physically writing to the NAND cells. The same applies to
any repeating pattern. By writing unique, incompressible data, pushfill
forces actual physical writes to every block.

## Goroutine Workers

pushfill spawns one goroutine worker per CPU core by default. Each worker:

- Generates random data via `crypto/rand.Read()`
- Writes to its own set of files (`pushfill_WWWW_SSSS.bin`)
- Reports progress via a shared atomic counter (`sync/atomic.Int64`)

Workers check a shared atomic stop flag and exit gracefully when signalled.

### File Naming

Files are named `pushfill_{worker_id}_{sequence}.bin`:

- `worker_id` — zero-padded worker number (0000, 0001, ...)
- `sequence` — zero-padded file sequence within that worker (0000, 0001, ...)

For example, with 4 workers, you might see:
```
pushfill_0000_0000.bin
pushfill_0001_0000.bin
pushfill_0002_0000.bin
pushfill_0003_0000.bin
```

## Scrub Phase

When a worker hits `ENOSPC` (disk full), it doesn't stop immediately.
Instead, it enters a **scrub phase**:

1. Halve the chunk size (e.g. 4 MiB to 2 MiB)
2. Try writing again
3. If `ENOSPC` again, halve again
4. Continue until the minimum scrub size (512 bytes) is reached

This ensures the very last bytes of free space are filled, not just the
space available in full-chunk increments.

If space becomes available again (e.g. macOS purging iCloud caches under
disk pressure), workers automatically ramp back up to full chunk size.

## Dynamic Progress

When filling a disk to capacity (no `--size`), pushfill periodically
rechecks available disk space. This keeps the progress bar and ETA accurate
even when the OS reclaims purgeable space (such as iCloud photo caches on
macOS) during the fill.

## Signal Handling

- **Workers** check a shared atomic stop flag on each iteration
- **Main goroutine** catches SIGINT/SIGTERM, sets the stop flag, and waits
  for workers to finish their current write
- During cleanup (file deletion), SIGINT is ignored to ensure files are
  always removed
