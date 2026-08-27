"""PPTX watermark removal: patches every embedded slide image in place."""

import logging
import os
import shutil
import tempfile
import zipfile
from typing import Optional

import cv2
import numpy as np
from tqdm import tqdm

from ..engine import WatermarkRemover

logger = logging.getLogger(__name__)

IMAGE_EXTS = ('.png', '.jpg', '.jpeg', '.webp')


def _clean_pptx_image_bytes(remover: WatermarkRemover, img_bytes: bytes, original_ext: str = ".png") -> Optional[bytes]:
    arr = np.frombuffer(img_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)
    if img is None:
        return None

    h, w = img.shape[:2]
    has_alpha = len(img.shape) == 3 and img.shape[2] == 4

    if has_alpha:
        channels = cv2.split(img)
        img_bgr = cv2.merge(channels[:3])
        alpha = channels[3]
    else:
        img_bgr = img.copy()
        alpha = None

    mx, my = remover.config.search_margin_x, remover.config.search_margin_y
    y0, x0 = max(0, h - my), max(0, w - mx)

    roi = img_bgr[y0:h, x0:w].copy()
    cleaned_roi = remover.clean_roi_scaled(roi)
    if cleaned_roi is None:
        return None

    img_bgr[y0:h, x0:w] = cleaned_roi
    img_final = cv2.merge([*cv2.split(img_bgr), alpha]) if has_alpha else img_bgr

    ext = original_ext.lower()
    if ext in ('.jpg', '.jpeg') and not has_alpha:
        ok, encoded = cv2.imencode('.jpg', img_final, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
    elif ext == '.webp':
        ok, encoded = cv2.imencode('.webp', img_final, [int(cv2.IMWRITE_WEBP_QUALITY), 95])
    else:
        ok, encoded = cv2.imencode('.png', img_final)
    return encoded.tobytes() if ok else None


def process_pptx(remover: WatermarkRemover, input_path: str, output_path: str) -> bool:
    """Removes the watermark from every embedded image inside a PPTX file."""
    tmpdir = None
    try:
        tmpdir = tempfile.mkdtemp()
        with zipfile.ZipFile(input_path, 'r') as zin:
            zin.extractall(tmpdir)

        media_dir = os.path.join(tmpdir, 'ppt', 'media')
        if not os.path.isdir(media_dir):
            logger.error(f"No media directory in {input_path}")
            shutil.rmtree(tmpdir)
            return False

        images = sorted([f for f in os.listdir(media_dir) if f.lower().endswith(IMAGE_EXTS)])
        if not images:
            logger.error(f"No images found in {input_path}")
            shutil.rmtree(tmpdir)
            return False

        patched = 0
        pbar = tqdm(images, desc=f"Processing {os.path.basename(input_path)}", unit="img")
        for img_name in pbar:
            img_path = os.path.join(media_dir, img_name)
            with open(img_path, 'rb') as f:
                original = f.read()

            ext = os.path.splitext(img_name)[1]
            cleaned = _clean_pptx_image_bytes(remover, original, ext)
            if cleaned is not None:
                with open(img_path, 'wb') as f:
                    f.write(cleaned)
                patched += 1
            pbar.set_postfix(patched=patched)

        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zout:
            for root, _, files in os.walk(tmpdir):
                for fname in files:
                    full_path = os.path.join(root, fname)
                    arcname = os.path.relpath(full_path, tmpdir)
                    zout.write(full_path, arcname)

        shutil.rmtree(tmpdir)
        logger.info(f"Saved {output_path} ({patched}/{len(images)} images patched)")
        return True

    except Exception as e:
        logger.error(f"Error processing PPTX {input_path}: {e}")
        if tmpdir and os.path.isdir(tmpdir):
            shutil.rmtree(tmpdir)
        return False
