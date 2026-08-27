"""Standalone image (PNG/JPG/WEBP) watermark removal."""

import logging

import cv2

from ..engine import WatermarkRemover

logger = logging.getLogger(__name__)


def process_image(remover: WatermarkRemover, input_path: str, output_path: str) -> bool:
    """Removes the watermark from the bottom-right corner of a single image file."""
    try:
        img = cv2.imread(input_path, cv2.IMREAD_UNCHANGED)
        if img is None:
            logger.error(f"Could not read: {input_path}")
            return False

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
        y0 = max(0, h - my)
        x0 = max(0, w - mx)

        roi = img_bgr[y0:h, x0:w].copy()
        cleaned_roi = remover.clean_roi_scaled(roi)
        if cleaned_roi is None:
            logger.warning(f"No watermark detected in {input_path}")
            return False

        img_bgr[y0:h, x0:w] = cleaned_roi
        img_final = cv2.merge([*cv2.split(img_bgr), alpha]) if has_alpha else img_bgr
        cv2.imwrite(output_path, img_final)
        logger.info(f"Saved cleaned image to {output_path}")
        return True
    except Exception as e:
        logger.error(f"Error processing {input_path}: {e}")
        return False
