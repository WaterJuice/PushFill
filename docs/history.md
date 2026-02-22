# History

## Version 2 (2026)

pushfill v2 is a complete rewrite in Python, replacing the original C implementation.

Key improvements over v1:

- **Multiprocess architecture** — spawns one worker per CPU core, each with its own
  random pool and background writer thread, saturating modern NVMe drives
- **Pool-based random with XOR multiplication** — replaces RC4 with continuous
  random generation stretched via XOR combinations
- **Background writer thread** — overlaps disk I/O with data generation within each
  worker, since `os.write()` releases Python's GIL
- **Live terminal UI** — colourful box-drawn display with speed, progress bar, and ETA
- **FAT32 auto-detection** — automatically detects FAT32 filesystems and respects
  the 4 GiB file size limit
- **Single-file mode** — write to a specific file path instead of a directory
- **Scrub phase** — fills the last bytes of disk space with progressively smaller writes
- **Graceful shutdown** — Ctrl+C stops cleanly with guaranteed file cleanup
- **Cross-platform** — works on macOS, Linux, and Windows

## Version 1 (2018)

The original pushfill was written by WaterJuice as a C utility, described in the
blog post
[Pushing Old Data Off a Disc](https://waterjuiceweb.wordpress.com/2018/02/16/pushing-old-data-off-a-disc/).

It used a straightforward approach:

1. Generate a 10 MB random block using RC4 encryption
2. Write the block 256 times, incrementing every byte by 1 each iteration
   (producing 2.56 GB of unique data per cycle)
3. Repeat with new RC4-generated blocks until the disk is full

This produced unique data on every block while being significantly faster than
full cryptographic random generation. On modern NVMe drives it reaches around
2.6 GB/s — fast, but limited by being single-threaded.

The original was single-threaded, which was sufficient for SATA drives (~500 MB/s)
but couldn't saturate modern NVMe drives.
