"""High-level watermark removal engine used by all format processors."""

from typing import Optional, Tuple

import cv2
import numpy as np

from .config import WatermarkConfig
from .detection import WatermarkDetector
from .reconstruction import heal


class WatermarkRemover:
    """Detects and removes a bottom-right NotebookLM-style watermark from a ROI."""

    def __init__(self, config: Optional[WatermarkConfig] = None):
        self.config = config or WatermarkConfig()
        self.detector = WatermarkDetector(self.config)

    # ---------- pixel format helpers ---------- #

    def pixmap_to_bgr(self, pix) -> Optional[np.ndarray]:
        """Converts a PyMuPDF Pixmap to a BGR numpy array."""
        data = np.frombuffer(pix.samples, dtype=np.uint8)
        if pix.n == 4:
            return cv2.cvtColor(data.reshape(pix.h, pix.w, 4), cv2.COLOR_RGBA2BGR)
        if pix.n == 3:
            return cv2.cvtColor(data.reshape(pix.h, pix.w, 3), cv2.COLOR_RGB2BGR)
        if pix.n == 1:
            gray = data.reshape(pix.h, pix.w)
            return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        return None

    # ---------- ROI cleaning ---------- #

    def clean_watermark_in_roi(self, roi_bgr: np.ndarray) -> Optional[Tuple[np.ndarray, np.ndarray]]:
        """
        Builds a precise mask and removes the watermark using patch-based
        reconstruction. Returns (cleaned_roi, mask) or None if no watermark
        was detected in this ROI.
        """
        mask = self.detector.build_mask(roi_bgr)
        if mask is None:
            return None
        cleaned = heal(roi_bgr, mask, self.config)
        return cleaned, mask

    def clean_roi_scaled(self, roi_bgr: np.ndarray) -> Optional[np.ndarray]:
        """
        Upscales the ROI for higher-quality detection/reconstruction, then
        composites only the masked (watermark) pixels back onto the
        original-resolution ROI -- content outside the mask is never
        resampled through the upscale/downscale round-trip.
        """
        scale = self.config.pdf_dpi_scale
        h, w = roi_bgr.shape[:2]
        roi_hr = cv2.resize(roi_bgr, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)
        result = self.clean_watermark_in_roi(roi_hr)
        if result is None:
            return None
        cleaned_hr, mask_hr = result

        cleaned = cv2.resize(cleaned_hr, (w, h), interpolation=cv2.INTER_LINEAR)
        mask = cv2.resize(mask_hr, (w, h), interpolation=cv2.INTER_NEAREST)

        out = roi_bgr.copy()
        out[mask > 0] = cleaned[mask > 0]
        return out
