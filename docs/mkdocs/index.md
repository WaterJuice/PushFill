# pushfill

**Fill a disk with pseudo-random data as fast as possible, then clean up.**

pushfill writes pseudo-random bytes to a target directory (or file) until the disk is
full or a specified size is reached, then deletes the generated files. It is designed
to push out old data from SSDs before recycling or repurposing a drive.

## Why?

When you delete files on an SSD, the data isn't immediately erased — the blocks are
simply marked as available. Until those blocks are overwritten, the old data remains
on the NAND flash. pushfill forces every available block to be overwritten with
unique, non-compressible data.

Unlike writing zeroes (which the drive controller might optimise away) or using slow
cryptographic wipers, pushfill uses Go's `crypto/rand` to produce unique data at
maximum speed — easily saturating the drive's write bandwidth.

## Features

- **Fast** — compiled Go binary with goroutine workers saturates NVMe drives
- **Unique data** — cryptographic random generation ensures every block is different
- **Zero dependencies** — single static binary, no runtime required
- **Cross-platform** — works on macOS, Linux, and Windows (amd64 + arm64)
- **FAT32 aware** — auto-detects FAT32 filesystems and respects the 4 GiB file limit
- **Live display** — colourful terminal UI showing speed, progress, and ETA
- **Clean shutdown** — Ctrl+C stops gracefully and cleans up generated files

## Quick Start

```bash
# Install
uv tool install pushfill

# Fill current directory until disk is full, then delete
pushfill

# Fill /tmp with 10 GB of data
pushfill /tmp --size 10G

# Fill and keep the files
pushfill /tmp --size 500M --keep
```

See [Installation](install.md) and [Usage](usage.md) for more details.

---

*pushfill is created by WaterJuice and released into the public domain under the
[Unlicense](licence.md).*
