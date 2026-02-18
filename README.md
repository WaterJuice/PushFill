# pushfill

Fill a disk with pseudo-random data as fast as possible, then clean up.

Designed to push out old data from SSDs by writing pseudo-random bytes
until the target size is reached or the disk is full.

## Usage

```
pushfill /tmp                    # Fill /tmp until disk is full, then delete
pushfill /tmp --size 10G         # Write 10 GB then delete
pushfill /tmp --size 500M --keep # Write 500 MB and keep files
pushfill . --workers 4           # Use 4 worker processes
```

## Install

```
uv tool install pushfill
```

## Licence

This is free and unencumbered software released into the public domain.
See [LICENSE](LICENSE) for details.
