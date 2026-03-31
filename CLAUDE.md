# CLAUDE.md

This file provides guidance for AI agents working on this project.

## Project Overview

pushfill is a single-purpose CLI tool that fills a disk with pseudo-random data as fast
as possible, then deletes the files. Used to push out old data from SSDs.

Written in Go with zero external dependencies (stdlib only). Uses goroutine-based
workers with `crypto/rand` for random data generation. Distributed as a Go binary
via PyPI using `bin2whl` for cross-platform wheel packaging.

## Language and Spelling

Use **Australian English** throughout:
- colour (not color)
- initialise (not initialize)
- organisation (not organization)

## Code Style

### Go Files

- **Go 1.25+** — uses standard library only, zero external dependencies
- `CGO_ENABLED=0` for static cross-compilation
- Format with `gofmt`
- Lint with `go vet`
- Manual CLI argument parsing (no flag package)
- TTY-aware ANSI colour output (Python 3.14 argparse style)

Every Go file should have:
1. A file header block with description, authors, and version history
2. Section headers separating major sections (Imports, Constants, Functions, etc.)
3. Horizontal separators (87 chars) above each function definition

Example structure:
```go
// ---------------------------------------------------------------------------------------
//
//	filename.go
//	-----------
//
//	Brief description of what this module does.
//
//	(c) 2026 WaterJuice — Released under the Unlicense; see LICENSE.
//
//	Authors
//	-------
//	bena (via Claude)
//
//	Version History
//	---------------
//	Mar 2026 - Created
//
// ---------------------------------------------------------------------------------------
package internal

// ---------------------------------------------------------------------------------------
//
//	Imports
//
// ---------------------------------------------------------------------------------------

import (
	"fmt"
)

// ---------------------------------------------------------------------------------------
//
//	Functions
//
// ---------------------------------------------------------------------------------------

// ---------------------------------------------------------------------------------------
// MyFunction does something useful.
func MyFunction() {
}
```

## Common Commands

```bash
make help       # Show all available targets
make check      # Run gofmt check + go vet
make format     # Format Go source with gofmt
make go-build   # Cross-compile for all platforms
make build      # Build wheels and documentation
make clean      # Remove build artefacts
make dev        # Build + symlink into .venv/bin/
make run ARGS="" # Build + run with arguments
```

## Project Structure

```
pushfill/
├── main.go               # Entry point, version injection via ldflags
├── go.mod                # Go module (zero external dependencies)
├── internal/             # Internal package
│   ├── cli.go            # CLI argument parsing, help text, colour helpers
│   ├── display.go        # Live terminal status display with box drawing
│   ├── filler.go         # Core fill logic with goroutine workers
│   ├── platform_unix.go  # Unix disk usage, filesystem detection, terminal width
│   ├── platform_windows.go # Windows implementations
│   ├── statfs_darwin.go  # macOS filesystem type name extraction
│   └── statfs_linux.go   # Linux filesystem type detection via /proc/mounts
├── Makefile              # Build automation
├── pyproject.toml        # Minimal uv config for dev dependencies
├── wheel.json            # bin2whl configuration for wheel building
├── mkdocs.yml            # Documentation config
└── docs/                 # Documentation source
```

## Architecture

- **No subcommands** — single-purpose tool with flat argument list
- **Goroutine workers** — each worker generates random data and writes to its own file
- **crypto/rand** — uses Go's cryptographic random number generator for data
- **Atomic counters** — `sync/atomic.Int64` for lock-free progress tracking
- **Platform files** — build-tagged files for Unix vs Windows specifics
- **FAT32 auto-detection** — via statfs on macOS, /proc/mounts on Linux,
  GetVolumeInformationW on Windows
- **Scrub phase** — workers fill remaining space with progressively smaller writes
- **Signal handling** — catches SIGINT/SIGTERM, sets stop flag, cleanup ignores SIGINT

## Build & Distribution

- Go binary cross-compiled for 6 platforms (macOS/Linux/Windows × amd64/arm64)
- Version injected at build time via `-ldflags -X main.Version=...`
- `bin2whl` wraps each binary in a platform-specific Python wheel
- Wheels distributed via PyPI — install with `uv tool install pushfill` or `pip install pushfill`
- No Python runtime needed — the wheel contains a standalone Go binary

## Testing Changes

After making changes:
1. Run `make check` to verify formatting and vet pass
2. Run `make go-build` to verify cross-compilation works
3. Test CLI with `make run ARGS="--help"`
4. Test a small fill: `make run ARGS="--size 100M /tmp"`

## Versioning

- Version is derived from git tags via Makefile
- Create a tag like `3.0.0` before running `make build` for a release (no `v` prefix)
- The Makefile injects the version via Go ldflags at build time

## Commits

When committing:
- Use clear, descriptive commit messages
- Include `Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>` in commits made with AI assistance
- **Never rewrite git history** unless explicitly asked to

## Licence

Unlicense — public domain; see LICENSE in the project root.
