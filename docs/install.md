# Installation

## With uv (recommended)

```bash
uv tool install pushfill
```

This installs pushfill as a standalone CLI tool, isolated from your project
environments.

## With pip

```bash
pip install pushfill
```

## With pipx

```bash
pipx install pushfill
```

## From source

```bash
git clone https://gitlab.com/waterjuice/pushfill.git
cd pushfill
make build
pip install output/*.whl
```

## Requirements

- No runtime dependencies — pushfill is a standalone compiled Go binary
- Platform wheels are available for macOS, Linux, and Windows (amd64 + arm64)
