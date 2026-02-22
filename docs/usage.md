# Usage

## Basic Usage

```bash
# Fill current directory until disk is full, then delete files
pushfill

# Fill a specific directory
pushfill /tmp

# Write to a single file
pushfill /tmp/fill.bin

# Write a specific amount then delete
pushfill /tmp --size 10G

# Write and keep the files
pushfill /tmp --size 500M --keep
```

## Options

| Short | Long | Description |
|-------|------|-------------|
| | `path` | Directory or file to fill (default: current directory) |
| `-s` | `--size` | Target size to write (e.g. `10G`, `500M`, `1T`). Default: fill disk |
| `-k` | `--keep` | Keep generated files instead of deleting them |
| `-w` | `--workers` | Number of worker processes (default: CPU count) |
| `-c` | `--chunk-size` | Chunk size in MiB per write (default: 4) |
| `-f` | `--fat32` | Limit each file to 4 GiB (for FAT32 filesystems) |
| `-m` | `--max-file-size` | Maximum size per file (e.g. `2G`). Overrides `--fat32` |
| `-n` | `--no-colour` | Disable coloured output |
| `-v` | `--verbose` | Show verbose output |
| | `--version` | Show version and exit |

## Size Format

Sizes can be specified with the following units:

| Unit | Meaning |
|------|---------|
| `B` | Bytes |
| `K` / `KB` | Kibibytes (1024 bytes) |
| `M` / `MB` | Mebibytes (1024^2 bytes) |
| `G` / `GB` | Gibibytes (1024^3 bytes) |
| `T` / `TB` | Tebibytes (1024^4 bytes) |

Examples: `100M`, `10G`, `1T`, `500MB`, `4096B`

## FAT32 Support

pushfill automatically detects FAT32 filesystems and limits file sizes to
4 GiB - 1 byte. You can also force this behaviour with `--fat32`, or set a
custom per-file limit with `--max-file-size`.

```bash
# Auto-detected
pushfill /mnt/usb

# Explicit
pushfill /mnt/usb --fat32

# Custom limit
pushfill /mnt/usb --max-file-size 2G
```

## Single-File Mode

When the path argument points to a file (rather than a directory), pushfill
writes to that single file using one worker process.

```bash
# Create and fill a single file
pushfill /tmp/fill.bin --size 1G
```

## Keeping Files

By default, pushfill deletes all generated files after completion (or
interruption). Use `--keep` to retain them.

```bash
pushfill /tmp --size 1G --keep
```

If you run pushfill again in the same directory after using `--keep`, it
will create new files alongside the existing ones — it won't overwrite
previously kept files.

## Interrupting

Press **Ctrl+C** to stop pushfill gracefully. It will:

1. Signal all workers to stop
2. Display a summary of what was written
3. Delete generated files (unless `--keep` was used)

Files are always cleaned up, even on interruption.
