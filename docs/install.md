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

- Python 3.9 or later
- No external runtime dependencies — pushfill uses only the Python standard library
