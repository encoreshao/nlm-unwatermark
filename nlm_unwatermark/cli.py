"""Command-line entry point: `nlm-unwatermark` / `python -m nlm_unwatermark`."""

import argparse
import logging
import os

from .config import WatermarkConfig
from .engine import WatermarkRemover
from .formats.image import process_image
from .formats.pdf import process_pdf
from .formats.pptx import process_pptx

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

SUPPORTED_EXTS = ('.pdf', '.pptx', '.png', '.jpg', '.jpeg', '.webp')


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nlm-unwatermark",
        description="Removes the NotebookLM watermark from PDF, PPTX, and image files.",
    )
    parser.add_argument("path", help="File (PDF/PPTX/PNG/JPG) or directory")
    parser.add_argument("-o", "--output", help="Output path")
    parser.add_argument("--preview", action="store_true", help="Process only first page (PDF only)")
    parser.add_argument("--margin-x", type=int, default=None, help="Search margin width from right edge")
    parser.add_argument("--margin-y", type=int, default=None, help="Search margin height from bottom edge")
    parser.add_argument("--threshold", type=int, default=None, help="Dark contrast threshold")
    parser.add_argument("--text-threshold", type=float, default=None, help="Template match threshold, e.g. 0.48")
    parser.add_argument("--scale", type=float, default=None, help="Render/upscale factor")
    parser.add_argument("--radius", type=int, default=None, help="Inpaint radius")
    parser.add_argument("--no-patch-heal", action="store_true", help="Disable clean-patch healing, use plain inpainting instead")
    parser.add_argument("--debug", action="store_true", help="Save debug masks/images")
    return parser


def _config_from_args(args: argparse.Namespace) -> WatermarkConfig:
    config = WatermarkConfig()
    if args.margin_x is not None:
        config.search_margin_x = args.margin_x
    if args.margin_y is not None:
        config.search_margin_y = args.margin_y
    if args.threshold is not None:
        config.pixel_threshold = args.threshold
    if args.text_threshold is not None:
        config.text_match_threshold = args.text_threshold
    if args.scale is not None:
        config.pdf_dpi_scale = args.scale
    if args.radius is not None:
        config.inpaint_radius = args.radius
    if args.no_patch_heal:
        config.use_patch_heal = False
    if args.debug:
        config.debug = True
    return config


def _collect_tasks(path: str) -> list:
    if os.path.isdir(path):
        tasks = sorted([
            os.path.join(path, f)
            for f in os.listdir(path)
            if f.lower().endswith(SUPPORTED_EXTS)
        ])
        logger.info(f"Found {len(tasks)} supported files.")
        return tasks
    if os.path.isfile(path) and path.lower().endswith(SUPPORTED_EXTS):
        return [path]
    logger.error("Invalid path or unsupported format.")
    return []


def main() -> None:
    args = build_arg_parser().parse_args()
    config = _config_from_args(args)
    remover = WatermarkRemover(config)

    tasks = _collect_tasks(args.path)

    for input_path in tasks:
        ext = os.path.splitext(input_path)[1].lower()
        if args.output and len(tasks) == 1:
            out_path = args.output
        else:
            base, _ = os.path.splitext(input_path)
            out_path = f"{base}_cleaned{ext}"

        if ext == '.pdf':
            process_pdf(remover, input_path, out_path, preview=args.preview)
        elif ext == '.pptx':
            process_pptx(remover, input_path, out_path)
        else:
            process_image(remover, input_path, out_path)


if __name__ == "__main__":
    main()
