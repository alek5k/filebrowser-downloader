# Release Instructions

This document describes how to prepare a new release of `filebrowser-downloader` and upload it to PyPI.

## 1. Prerequisites

- You have push access to the GitHub repo.
- You have a PyPI account with permission for `filebrowser-downloader`.
- `python` is installed.

Install release tools:

```bash
python -m pip install --upgrade pip build twine
```

## 2. Update Version

Edit [`pyproject.toml`](./pyproject.toml) and bump:

```toml
[project]
version = "0.1.1"
```

Use semantic versioning:
- Patch: `0.1.1` -> `0.1.2` (bugfixes)
- Minor: `0.1.1` -> `0.2.0` (new backward-compatible features)
- Major: `0.1.1` -> `1.0.0` (breaking changes)

## 3. Commit and Tag

```bash
git add pyproject.toml
git commit -m "Release vX.Y.Z"
git tag vX.Y.Z
git push
git push origin vX.Y.Z
```

## 4. Build Distributions

Clean old artifacts and build:

```bash
rm -rf dist build *.egg-info
python -m build
```

This creates:
- source distribution (`.tar.gz`)
- wheel (`.whl`)

## 5. Validate Package

```bash
python -m twine check dist/*
```

## 6. Upload to PyPI

```bash
python -m twine upload dist/*
```

You will be prompted for PyPI credentials unless you configured an API token.

## 7. Verify Release

- Open PyPI project page and confirm new version appears.
- Test install:

```bash
python -m pip install --upgrade filebrowser-downloader==X.Y.Z
```

## Optional: TestPyPI Dry Run

Upload first to TestPyPI:

```bash
python -m twine upload --repository testpypi dist/*
```

Then test install:

```bash
python -m pip install --index-url https://test.pypi.org/simple/ --no-deps filebrowser-downloader==X.Y.Z
```
