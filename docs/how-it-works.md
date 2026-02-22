# How It Works

## Overview

pushfill uses multiple worker processes to write pseudo-random data to disk
files as fast as possible. The goal is to overwrite every available block on
the drive with unique, non-compressible data.

## Pool-Based Random Generation

Each worker continuously generates random data using a pool with XOR
multiplication:

1. **Pool fill** — the worker maintains a pool of 8 random blocks, generated
   using Python's Mersenne Twister (`random.getrandbits`)
2. **Fresh block** — each cycle, a new random block is generated and placed
   in the pool (replacing the oldest entry)
3. **XOR multiplication** — the fresh block is XORed with every other entry
   in the pool, producing 7 additional unique output blocks

```
cycle: generate fresh block R
output: R, R^pool[0], R^pool[1], ..., R^pool[6]
```

With a pool of 8, this produces 8 output blocks per random generation call —
an 8x throughput multiplier while ensuring every output block contains fresh
randomness. The pool is continuously refreshed, so no block is ever reused.

### Why not pure random for every block?

Calling `random.getrandbits()` for every chunk is the bottleneck — even the
fast Mersenne Twister can't keep up with NVMe write speeds. The XOR
multiplication stretches each random generation across 8 output blocks while
keeping every block unique and pattern-free.

### Why not write zeroes?

SSD controllers are smart. Many can detect all-zero blocks and simply store
a flag rather than physically writing to the NAND cells. The same applies to
any repeating pattern. By writing unique, incompressible data, pushfill
forces actual physical writes to every block.

## Background Writer Thread

Within each worker, data generation and disk I/O happen concurrently. A
**background writer thread** pulls blocks from a queue and calls `os.write()`,
while the main thread generates the next block. This works because `os.write()`
releases Python's GIL, allowing the main thread to run `getrandbits()` and
`int.to_bytes()` in parallel with the kernel write.

This gives roughly a 36% throughput improvement per worker compared to
sequential generate-then-write.

## Multiprocessing

pushfill spawns one worker process per CPU core by default. Each worker:

- Gets its own random pool (no shared state for data generation)
- Uses a background writer thread to overlap I/O with generation
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
