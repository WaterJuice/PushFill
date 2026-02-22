# PushFill 2.0 — Rewritten in Python, Faster Than C

Back in 2018 I wrote a small C tool called [PushFill](https://waterjuiceweb.wordpress.com/2018/02/16/pushing-old-data-off-a-disc/) for pushing old data off SSDs. The idea was simple: fill the drive with unique, non-compressible data so the SSD controller has no choice but to physically overwrite every NAND cell. Delete the files, and the old data is gone.

That version used RC4 to generate a 10 MB random block, then wrote it 256 times with each byte incremented by one on each pass. This produced 2.56 GB of unique data per cycle, and on the SATA SSDs of the day it ran at about 1 GB/s. Fast enough.

Eight years later, drives have changed. NVMe SSDs on Apple Silicon can sustain several GB/s of writes. A single-threaded program — even in C — can't saturate a modern drive. I wanted something that could.

## The Rewrite

PushFill 2.0 is a complete rewrite in Python. Yes, Python. Before you raise an eyebrow — the bottleneck was never CPU speed. It's disk I/O. Python's standard library gives us `multiprocessing`, `os.write`, and that's really all we need. No pip packages, no dependencies, just stdlib.

The key change is **multiprocessing**. PushFill now spawns one worker process per CPU core. Each worker generates its own data and writes to its own files independently. On a MacBook Pro with Apple Silicon, this saturates the NVMe drive — around **3x faster** than the original C version running on the same hardware.

## Pool-Based Random with XOR Multiplication

The data generation strategy changed too. Instead of RC4, each worker uses what I'm calling a **pool-based random generation** approach with XOR multiplication:

1. Each worker maintains a pool of 8 random blocks, generated using Python's Mersenne Twister
2. Each cycle, a fresh random block is generated and placed in the pool
3. That fresh block is XORed with every other pool entry, producing 7 additional unique output blocks

```
cycle: generate fresh random block R
output: R, R^pool[0], R^pool[1], ..., R^pool[6]
```

This gives 8 output blocks per random generation call — an 8x throughput multiplier. Every output block contains fresh randomness (it's XORed with a just-generated block), the pool is continuously refreshed, and no two output blocks are ever identical. Unlike the v1 approach where the random generation happened once at startup, here it runs continuously — the XOR multiplication just stretches each generation further.

## Scrub Phase

One thing that always bothered me about the original was that it would write full-size chunks until it got a disk-full error and then stop. But the drive isn't really full — there are still gaps smaller than the chunk size.

PushFill 2.0 has a **scrub phase**. When a worker hits disk-full, it halves the chunk size and tries again. Keeps halving down to 512 bytes. This squeezes out every last byte of free space.

On macOS there's an interesting wrinkle: the OS has "purgeable" space — iCloud photo caches, Time Machine snapshots, that sort of thing. When disk pressure builds, macOS starts freeing this space in the background. So PushFill might hit disk-full, scrub down to nothing, and then a few seconds later there's another 20 GB free. The workers detect this and ramp back up to full-speed writes automatically.

## Live Display

The original just printed periodic status lines. The new version has a proper terminal UI with box-drawing characters, a progress bar, rolling speed average, and ETA. It dynamically tracks how much space is actually available (accounting for the OS reclaiming purgeable space) and adjusts the progress bar accordingly.

```
╭──────────────────────────────────────────────────────────╮
│  pushfill 2.0.0b1                        Elapsed 2:34   │
├──────────────────────────────────────────────────────────┤
│  Speed     6,842.3 MB/s   (54.74 Gbps)                  │
│  Average   7,012.1 MB/s   (56.10 Gbps)                  │
│  Written   924.18 GB / 926.35 GB              ETA 0:01   │
│  ██████████████████████████████████████████░░░  99.8%    │
╰──────────────────────────────────────────────────────────╯
```

## Other Improvements

A few more things that are new in v2:

- **FAT32 auto-detection** — if you're filling a USB stick formatted as FAT32, PushFill detects this and automatically limits files to under 4 GiB. Works on macOS, Linux, and Windows.
- **Single-file mode** — point it at a file path instead of a directory and it writes to that one file.
- **`--keep` flag** — by default PushFill deletes everything when it's done. Use `--keep` to retain the files (handy for benchmarking or creating test data).
- **Graceful Ctrl+C** — press Ctrl+C and it stops cleanly, always cleaning up its files. No orphaned data left behind.

## Installation

```bash
# With uv (recommended)
uv tool install pushfill

# Or pip
pip install pushfill
```

Then just:

```bash
# Fill current directory until disk is full, then delete
pushfill

# Fill a specific directory with a specific amount
pushfill /tmp --size 10G

# Fill a USB drive
pushfill /mnt/usb
```

## The Numbers

On the same Apple Silicon MacBook Pro with a 1 TB NVMe SSD:

| Version | Speed | Language | Workers |
|---------|-------|----------|---------|
| v1 (2018) | ~2.6 GB/s | C | 1 |
| v2 (2026) | ~7.8 GB/s | Python | 10 (one per core) |

Python beating C by 3x. Not something you see every day — but when the bottleneck is I/O parallelism rather than raw computation, the language barely matters. What matters is keeping all the drive's channels busy.

## Source and Documentation

PushFill is released into the public domain under the [Unlicense](https://unlicense.org).

- **PyPI:** [pypi.org/project/pushfill](https://pypi.org/project/pushfill/)
- **Source:** [gitlab.com/waterjuice/pushfill](https://gitlab.com/waterjuice/pushfill)
- **Documentation:** [pushfill-4a17ec.gitlab.io](https://pushfill-4a17ec.gitlab.io/)
