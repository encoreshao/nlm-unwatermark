# nlm-unwatermark

![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)
![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Windows%20%7C%20Linux-lightgrey.svg)
[![GitHub stars](https://img.shields.io/github/stars/encoreshao/nlm-unwatermark?style=social)](https://github.com/encoreshao/nlm-unwatermark/stargazers)
[![GitHub issues](https://img.shields.io/github/issues/encoreshao/nlm-unwatermark)](https://github.com/encoreshao/nlm-unwatermark/issues)

[English](README.md) | [中文](README_zh.md) | [Français](README_fr.md) | [日本語](README_ja.md)

Removes the "NotebookLM" watermark and the Gemini "spark" badge from PDF, PPTX, and image exports (PNG/JPG/WEBP) using computer-vision inpainting instead of a solid-color box, so gradients, textures, and slide borders stay intact.

## Before / After

| Before | After |
| --- | --- |
| ![Before: page with the NotebookLM watermark](docs/images/before.png) | ![After: watermark removed, background healed](docs/images/after.png) |

## Table of Contents

- [Before / After](#before--after)
- [How It Works](#how-it-works)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
  - [Options](#options)
- [Standalone Executable](#standalone-executable)
- [Project Structure](#project-structure)
- [Development](#development)
- [Contributing](#contributing)
- [Legal & Fair Use](#legal--fair-use)
- [License](#license)

## How It Works

1. **Detect** — contrast analysis + text template matching locate the "NotebookLM" watermark; a standalone shape template catches the Gemini "spark" badge on AI-generated images that carry no text, ignoring nearby slide content.
2. **Reconstruct** — the background behind it is healed from a clean nearby patch, searched for over a wider surrounding area than the detection crop itself (so a badge sitting right on a real content edge can still find a good match), falling back to inpainting when nothing close enough is found.
3. **Patch** — PDFs get the watermark text stripped straight from the text layer (redaction, not overlay) plus a small raster touch-up for the icon; PPTX/images are patched in the rendered pixels.

## Requirements

- Python 3.9 or later
- pip
- Dependencies (installed automatically): [PyMuPDF](https://pypi.org/project/PyMuPDF/), [Pillow](https://pypi.org/project/Pillow/), [opencv-python-headless](https://pypi.org/project/opencv-python-headless/), [NumPy](https://pypi.org/project/numpy/), [tqdm](https://pypi.org/project/tqdm/)

## Installation

```bash
git clone https://github.com/encoreshao/nlm-unwatermark.git
cd nlm-unwatermark
python3 -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install -e .           # optional — gives you the `nlm-unwatermark` command
```

Verify the install:

```bash
nlm-unwatermark --help
```

If that prints the usage text, you're ready to go.

## Usage

```bash
nlm-unwatermark file.pdf                # → file_cleaned.pdf
nlm-unwatermark file.pptx                # → file_cleaned.pptx
nlm-unwatermark slide.png                # → slide_cleaned.png
nlm-unwatermark ./my_folder/             # batch-process every supported file in a folder
nlm-unwatermark file.pdf --preview       # PDF only: process just the first page
nlm-unwatermark file.pdf -o out.pdf      # custom output path
```

Didn't run `pip install -e .`? Use `python -m nlm_unwatermark file.pdf` instead — same behavior.

### Options

| Flag | Default | Description |
|---|---|---|
| `-o`, `--output` | `<name>_cleaned.<ext>` | Output path (single-file runs only) |
| `--preview` | off | PDF only — process just the first page |
| `--margin-x` | `400` | Search width from the right edge, in px |
| `--margin-y` | `120` | Search height from the bottom edge, in px |
| `--threshold` | `22` | Contrast threshold for candidate pixels |
| `--text-threshold` | `0.33` | Template-match confidence required to count as text |
| `--icon-threshold` | `0.65` | Template-match confidence required to count as the Gemini spark icon |
| `--scale` | `3.5` | PDF render / image upscale factor |
| `--radius` | `3` | Inpaint radius (fallback reconstruction only) |
| `--no-patch-heal` | off | Use plain inpainting instead of clean-patch healing |
| `--context-scale` | `3.0` | How much wider than the search margin to look for a clean donor patch |
| `--patch-quality-threshold` | `20.0` | Max acceptable donor-patch mismatch before falling back to inpainting |
| `--debug` | off | Dump detection masks to `debug_watermark/` |

## Standalone Executable

Don't want to set up Python? A prebuilt, single-file executable (no interpreter or dependencies required) can be built for Windows, macOS, and Linux — see [Development](#development) below.

```bash
# Windows
dist\nlm-unwatermark.exe file.pdf

# macOS / Linux
dist/nlm-unwatermark file.pdf
```

## Project Structure

```
nlm_unwatermark/
├── cli.py              CLI entry point (nlm-unwatermark / python -m nlm_unwatermark)
├── config.py            tunable detection/removal parameters
├── detection.py          watermark localization (candidate extraction + template match)
├── reconstruction.py      background healing / inpainting
├── engine.py              wires detection + reconstruction together
└── formats/               per-format processors: pdf.py, image.py, pptx.py
packaging/
├── entry_point.py         PyInstaller-safe absolute-import entry point
└── nlm-unwatermark.spec   PyInstaller build spec
docs/
└── BUILD.md               instructions for building a standalone executable
```

## Development

Set up a local development environment the same way as [Installation](#installation) — **inside that virtual environment**, not a global/shared Python install — then install the build-only dependencies if you plan to package an executable:

```bash
python3 -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt -r requirements-build.txt
python -m PyInstaller packaging/nlm-unwatermark.spec --noconfirm
```

> **Why an isolated venv matters:** PyInstaller statically traces every import it can find, including ones only reached lazily by optional, unused code paths (e.g. PyMuPDF's `Table.to_pandas()`). If you build from a shared/global interpreter that happens to have unrelated heavy packages installed (pandas, torch, etc.), PyInstaller can pull those in too and the build can fail — e.g. a `numpy.dtype size changed` error means an incompatible `pandas`/`numpy` pair got dragged in from outside this project. A clean venv containing only `requirements.txt` + `requirements-build.txt` avoids this entirely.

Full build details — including why the spec targets `packaging/entry_point.py` instead of `nlm_unwatermark/__main__.py` — are in [docs/BUILD.md](docs/BUILD.md).

Tuning detection/removal behavior (margins, thresholds, inpaint radius, etc.) lives in `nlm_unwatermark/config.py`, exposed as CLI flags in `nlm_unwatermark/cli.py` — see the [Options](#options) table above.

## Contributing

PRs welcome — [open an issue](https://github.com/encoreshao/nlm-unwatermark/issues/new) for anything non-trivial before you start.

## Legal & Fair Use

Use this only on documents you own or have the right to modify — you're responsible for how you use it. Watermark removal is legitimate when you own the generated content (Google states it won't claim ownership over NotebookLM output); this tool exists to help you clean up your own exports. It's provided under the MIT License, but using it to evade a paid service's attribution or paywall requirements is not an endorsed use.

## License

MIT © 2026 [Encore Shao](LICENSE)
