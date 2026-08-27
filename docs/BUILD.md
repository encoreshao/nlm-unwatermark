# Building nlm-unwatermark

This document explains how to build a standalone executable with PyInstaller.

## Requirements for Building

Always build from a clean, isolated virtual environment — **do not** build from a global/shared Python interpreter that has other projects' packages installed. PyInstaller statically traces every import it can find, including ones only reached lazily by optional, unused code paths (e.g. PyMuPDF's `Table.to_pandas()`). If unrelated heavy packages (pandas, torch, etc.) happen to be installed alongside this project, PyInstaller can pull those in too, and the build can fail with errors like `numpy.dtype size changed, may indicate binary incompatibility` — a sign an incompatible `pandas`/`numpy` pair got dragged in from outside this project, not a bug in nlm-unwatermark itself.

```bash
python3 -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt -r requirements-build.txt
```

## Build Process

From the repo root, with the virtual environment above still active, run:

```bash
python -m PyInstaller packaging/nlm-unwatermark.spec --noconfirm
```

The resulting executable will be located in the `dist/` directory:
- Windows: `dist\nlm-unwatermark.exe`
- macOS/Linux: `dist/nlm-unwatermark`

## Technical Details

- **PyInstaller:** Bundles the package and its dependencies into a single file.
- **Spec file:** `packaging/nlm-unwatermark.spec` configures the build, including hidden imports for OpenCV and PyMuPDF, and excludes (`pandas`, `IPython`, `ipywidgets`, `matplotlib`, `pytest`) for optional libraries that PyMuPDF/tqdm only import lazily and this project never uses — belt-and-suspenders against the environment-contamination issue described above.
- **Entry point:** PyInstaller runs its target script outside of any Python package context, which breaks the package's normal relative imports. `packaging/entry_point.py` works around this — it adds the project root to `sys.path` and imports `nlm_unwatermark.cli` absolutely. Don't point the spec at `nlm_unwatermark/__main__.py` directly; use `entry_point.py`.
