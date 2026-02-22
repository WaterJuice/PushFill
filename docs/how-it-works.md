# How It Works

## Overview

pushfill uses multiple worker processes to write pseudo-random data to disk
files as fast as possible. The goal is to overwrite every available block on
the drive with unique, non-compressible data.

## Seed-XOR-Counter Strategy

Each worker generates random data using a two-step approach:

1. **Seed generation** — at startup, each worker calls `random.randbytes(chunk_size)`
   to produce a cryptographically-seeded random block (the "seed")
2. **Counter XOR** — for each subsequent write, the seed is XORed with an
   incrementing counter multiplied by a large stride constant

```
block[n] = seed XOR (stride * n)
```

This produces unique data for every block written, across all workers, without
the overhead of repeated cryptographic random generation. The stride constant
includes a magic number (`0xDEADBEEF`) to ensure good bit distribution.

### Why not just use random data?

Calling `random.randbytes()` for every chunk is slow — it involves the OS
entropy pool and cryptographic mixing. The XOR-counter approach generates
the seed once, then produces subsequent blocks with a single integer XOR
operation, which is orders of magnitude faster.

### Why not write zeroes?

SSD controllers are smart. Many can detect all-zero blocks and simply store
a flag rather than physically writing to the NAND cells. The same applies to
any repeating pattern. By writing unique, incompressible data, pushfill
forces actual physical writes to every block.

## Multiprocessing

pushfill spawns one worker process per CPU core by default. Each worker:

- Gets its own random seed (no shared state for data generation)
- Writes to its own set of files (`pushfill_WWWW_SSSS.bin`)
- Reports progress via a shared counter (`multiprocessing.Value`)

Workers are daemon processes and ignore `SIGINT` — the main process handles
shutdown via a shared stop flag.

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
rechecks available disk space via `shutil.disk_usage()`. This keeps the
progress bar and ETA accurate even when the OS reclaims purgeable space
(such as iCloud photo caches on macOS) during the fill.

## Signal Handling

- **Workers** ignore `SIGINT` — they only stop when the shared stop flag is set
- **Main process** catches `SIGINT`, sets the stop flag, and waits for workers
  to finish their current write
- During cleanup (file deletion), `SIGINT` is ignored to ensure files are
  always removed
