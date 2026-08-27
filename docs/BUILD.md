# Building nlm-unwatermark

This document explains how to build a standalone executable with PyInstaller.

## Requirements for Building

Install the runtime and build dependencies:

```bash
pip install -r requirements.txt -r requirements-build.txt
```

## Build Process

From the repo root, run:

```bash
python -m PyInstaller packaging/nlm-unwatermark.spec --noconfirm
```

The resulting executable will be located in the `dist/` directory:
- Windows: `dist\nlm-unwatermark.exe`
- macOS/Linux: `dist/nlm-unwatermark`

## Technical Details

- **PyInstaller:** Bundles the package and its dependencies into a single file.
- **Spec file:** `packaging/nlm-unwatermark.spec` configures the build, including hidden imports for OpenCV and PyMuPDF.
- **Entry point:** PyInstaller runs its target script outside of any Python package context, which breaks the package's normal relative imports. `packaging/entry_point.py` works around this — it adds the project root to `sys.path` and imports `nlm_unwatermark.cli` absolutely. Don't point the spec at `nlm_unwatermark/__main__.py` directly; use `entry_point.py`.
