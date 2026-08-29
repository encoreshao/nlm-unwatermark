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

    # ---------- context placement ---------- #

    def _place_mask_in_context(
        self,
        mask: np.ndarray,
        context_bgr: Optional[np.ndarray],
        context_offset: Tuple[int, int],
    ) -> Tuple[np.ndarray, np.ndarray, int, int]:
        """
        Resolves the (possibly missing/misaligned) reconstruction context
        into a same-size full mask, clamping the offset so the ROI always
        fits -- rounding differences between how callers derive the ROI and
        context crops (e.g. PDF page-unit rects vs. pixel crops) shouldn't
        be able to place it out of bounds.
        """
        h, w = mask.shape[:2]
        if context_bgr is None:
            return mask, mask, 0, 0

        ch, cw = context_bgr.shape[:2]
        ox, oy = context_offset
        ox = max(0, min(ox, cw - w))
        oy = max(0, min(oy, ch - h))

        full_mask = np.zeros((ch, cw), dtype=np.uint8)
        full_mask[oy:oy + h, ox:ox + w] = mask
        return full_mask, context_bgr, ox, oy

    # ---------- ROI cleaning ---------- #

    def clean_watermark_in_roi(
        self,
        roi_bgr: np.ndarray,
        context_bgr: Optional[np.ndarray] = None,
        context_offset: Tuple[int, int] = (0, 0),
    ) -> Optional[Tuple[np.ndarray, np.ndarray]]:
        """
        Builds a precise mask from `roi_bgr`, then reconstructs the masked
        pixels by donor-patch healing over `context_bgr` -- a larger crop
        containing `roi_bgr` at `context_offset` -- so a clean donor patch
        can be found even when the tight ROI has nowhere clean nearby (e.g.
        a badge sitting right at a photo's own silhouette edge). Falls back
        to healing within `roi_bgr` alone when no context is given.
        Returns (cleaned_roi, mask) or None if no watermark was detected.
        """
        mask = self.detector.build_mask(roi_bgr)
        if mask is None:
            return None

        h, w = roi_bgr.shape[:2]
        full_mask, context, ox, oy = self._place_mask_in_context(mask, context_bgr, context_offset)
        cleaned_context = heal(context, full_mask, self.config)
        cleaned_roi = cleaned_context[oy:oy + h, ox:ox + w]
        return cleaned_roi, mask

    def clean_roi_scaled(
        self,
        roi_bgr: np.ndarray,
        context_bgr: Optional[np.ndarray] = None,
        context_offset: Tuple[int, int] = (0, 0),
    ) -> Optional[np.ndarray]:
        """
        Upscales the ROI for higher-quality detection, then reconstructs
        (optionally against a wider `context_bgr`, see
        `clean_watermark_in_roi`) and composites only the masked (watermark)
        pixels back onto the original-resolution ROI -- content outside the
        mask is never resampled through the upscale/downscale round-trip.
        """
        scale = self.config.pdf_dpi_scale
        h, w = roi_bgr.shape[:2]
        roi_hr = cv2.resize(roi_bgr, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)
        mask_hr = self.detector.build_mask(roi_hr)
        if mask_hr is None:
            return None
        mask = cv2.resize(mask_hr, (w, h), interpolation=cv2.INTER_NEAREST)

        full_mask, context, ox, oy = self._place_mask_in_context(mask, context_bgr, context_offset)
        cleaned_context = heal(context, full_mask, self.config)
        cleaned_roi = cleaned_context[oy:oy + h, ox:ox + w]

        out = roi_bgr.copy()
        out[mask > 0] = cleaned_roi[mask > 0]
        return out
