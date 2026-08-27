"""Watermark detection: locates the NotebookLM text/icon inside a ROI and
builds a tight removal mask via a hybrid of contrast-based candidate
extraction and template matching.
"""

import os
from typing import List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .config import WatermarkConfig

# NotebookLM's export watermark has shipped under more than one label over
# time ("NotebookLM", then "Gemini Notebook"). Match the current label first,
# but keep matching the legacy one so older exports still get redacted.
WATERMARK_TEXT_VARIANTS = ("Gemini Notebook", "NotebookLM")


class WatermarkDetector:
    """Builds a removal mask for the NotebookLM watermark inside a ROI."""

    def __init__(self, config: Optional[WatermarkConfig] = None):
        self.config = config or WatermarkConfig()
        self._template_cache = {}

    # ---------- debug ---------- #

    def debug_save(self, name: str, img: np.ndarray) -> None:
        if not self.config.debug:
            return
        try:
            os.makedirs("debug_watermark", exist_ok=True)
            cv2.imwrite(os.path.join("debug_watermark", name), img)
        except Exception:
            pass

    # ---------- text template matching ---------- #

    def _render_text_template(self, text: str, height: int) -> np.ndarray:
        """Creates a binary template for the given watermark label at a target height."""
        key = (text, max(10, int(height)))
        if key in self._template_cache:
            return self._template_cache[key]

        font_size = max(12, int(key[1] * 1.15))
        canvas_w = max(180, font_size * len(text) * 2)
        canvas_h = max(40, font_size * 3)

        img = Image.new('L', (canvas_w, canvas_h), 255)
        draw = ImageDraw.Draw(img)

        font = None
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf",  # Fedora/RHEL
            "/usr/share/fonts/TTF/DejaVuSans.ttf",  # Arch
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
            "/usr/share/fonts/msttcore/arial.ttf",
            "/Library/Fonts/Arial.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",  # modern macOS
            "C:/Windows/Fonts/arial.ttf",
        ]
        for path in candidates:
            try:
                font = ImageFont.truetype(path, font_size)
                break
            except Exception:
                continue
        if font is None:
            font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        x = 8
        y = max(4, (canvas_h - th) // 2 - bbox[1])
        draw.text((x, y), text, fill=0, font=font)

        arr = np.array(img)
        _, binary = cv2.threshold(arr, 200, 255, cv2.THRESH_BINARY_INV)
        ys, xs = np.where(binary > 0)
        if len(xs) == 0 or len(ys) == 0:
            tpl = np.zeros((10, 80), dtype=np.uint8)
        else:
            tpl = binary[ys.min():ys.max() + 1, xs.min():xs.max() + 1]

        self._template_cache[key] = tpl
        return tpl

    def _is_light_background(self, gray: np.ndarray) -> bool:
        """
        Rough polarity check for the ROI: light page background with dark text
        (the common case), or a dark slide background with light text.
        Sampled from the ROI border ring, which is very unlikely to contain
        the watermark itself (it sits away from the crop edges).
        """
        h, w = gray.shape[:2]
        border = max(2, min(h, w) // 20)
        edge_pixels = np.concatenate([
            gray[:border, :].ravel(),
            gray[-border:, :].ravel(),
            gray[:, :border].ravel(),
            gray[:, -border:].ravel(),
        ])
        return float(np.median(edge_pixels)) >= 128

    def _template_match_text(self, roi_bgr: np.ndarray) -> Tuple[Optional[Tuple[int, int, int, int]], float]:
        """Template-match the watermark text in the bottom-right ROI."""
        h, w = roi_bgr.shape[:2]
        if h < 20 or w < 80:
            return None, 0.0

        gray = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2GRAY)
        light_bg = self._is_light_background(gray)
        gray_eq = cv2.equalizeHist(gray)

        # Only search the bottom-right-biased sub-region the watermark actually
        # lives in (same bias used by `_extract_candidates`). Without this, a
        # low but passing score can win on a coincidental match anywhere in the
        # ROI -- e.g. unrelated page content near the top -- since
        # matchTemplate has no notion of where the watermark is expected.
        search_x0 = int(w * self.config.roi_right_bias)
        search_y0 = int(h * self.config.roi_bottom_bias)
        search_area = gray_eq[search_y0:h, search_x0:w]

        best_score = 0.0
        best_box = None

        # The watermark's rendered text is a small caption, not proportional to
        # the (much larger) search-margin ROI -- searching template heights
        # scaled off `h` used to try sizes 4-10x too big for the real text and
        # would essentially never match it. Scale the search range off the
        # render/upscale factor instead, which is what actually determines how
        # large the watermark glyphs are in `roi_bgr`.
        scale = self.config.pdf_dpi_scale
        min_h = max(12, int(round(6 * scale)))
        max_h = max(min_h + 4, int(round(42 * scale)))

        for text in WATERMARK_TEXT_VARIANTS:
            for text_h in range(min_h, max_h, 3):
                tpl = self._render_text_template(text, text_h)
                th, tw = tpl.shape[:2]
                if th >= search_area.shape[0] or tw >= search_area.shape[1]:
                    continue

                result = cv2.matchTemplate(search_area, tpl, cv2.TM_CCOEFF_NORMED)
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

                # The template is light text on a dark canvas. On a light-background
                # ROI, real dark-on-light text correlates negatively against it; on a
                # dark-background ROI, real light-on-dark text correlates positively.
                # Pick the sign that matches this ROI's polarity instead of taking
                # whichever is larger, which would just as happily "detect" the
                # watermark's own inverse pattern anywhere in the page.
                if light_bg:
                    match_val, match_loc = -min_val, min_loc
                else:
                    match_val, match_loc = max_val, max_loc

                if match_val > best_score:
                    x, y = match_loc
                    best_score = float(match_val)
                    best_box = (x + search_x0, y + search_y0, tw, th)

        if best_score < self.config.text_match_threshold:
            return None, best_score
        return best_box, best_score

    # ---------- candidate extraction ---------- #

    def _extract_candidates(self, roi_bgr: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2GRAY)
        light_bg = self._is_light_background(gray)

        # Robust background estimate
        ksize = max(15, min(41, ((min(gray.shape[:2]) // 5) | 1)))
        bg = cv2.medianBlur(gray, ksize)

        if light_bg:
            # Dark text/icon on a light background
            diff = cv2.subtract(bg, gray)
            luma_mask = np.where(gray < self.config.text_luma_threshold, 255, 0).astype(np.uint8)
        else:
            # Light text/icon on a dark background
            diff = cv2.subtract(gray, bg)
            luma_mask = np.where(gray > (255 - self.config.text_luma_threshold), 255, 0).astype(np.uint8)

        _, diff_mask = cv2.threshold(diff, self.config.pixel_threshold, 255, cv2.THRESH_BINARY)
        mask = cv2.bitwise_and(luma_mask, diff_mask)

        # Restrict to bottom-right biased region to reduce false positives
        h, w = gray.shape[:2]
        geom = np.zeros_like(mask)
        x0 = int(w * self.config.roi_right_bias)
        y0 = int(h * self.config.roi_bottom_bias)
        geom[y0:h, x0:w] = 255
        mask = cv2.bitwise_and(mask, geom)

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=self.config.close_iterations)
        mask = cv2.dilate(mask, kernel, iterations=self.config.dilate_iterations)
        return mask

    def _component_boxes_from_mask(self, mask: np.ndarray) -> List[Tuple[int, int, int, int, int]]:
        n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        h, w = mask.shape[:2]
        out = []
        for i in range(1, n):
            x, y, cw, ch, area = stats[i]
            if area < self.config.min_component_area:
                continue
            if area > int(h * w * self.config.max_component_area_ratio):
                continue
            out.append((int(x), int(y), int(cw), int(ch), int(area)))
        return out

    # ---------- mask assembly ---------- #

    def build_mask(self, roi_bgr: np.ndarray) -> Optional[np.ndarray]:
        """
        Hybrid watermark detection:
        1) detect dark components in the bottom-right region,
        2) locate text using template matching,
        3) build a mask covering the matched text plus room for its icon,
        4) return a tight but safe mask for removal.
        """
        h, w = roi_bgr.shape[:2]
        if h < 10 or w < 20:
            return None

        candidate_mask = self._extract_candidates(roi_bgr)
        comps = self._component_boxes_from_mask(candidate_mask)
        if not comps:
            return None

        text_box, score = self._template_match_text(roi_bgr)
        if text_box is None:
            # Fallback: no confident text match, so approximate the watermark as
            # the union of small, roughly text/icon-shaped dark components in the
            # bottom-right area. This is intentionally conservative: a decorative
            # element sharing that corner (a ruled grid, a border) is made of
            # thin, elongated line segments rather than the compact, moderately
            # proportioned blobs that letters and icons form, so long/thin
            # components are excluded to avoid patching over real page content.
            selected = []
            for x, y, cw, ch, area in comps:
                cx = x + cw / 2
                cy = y + ch / 2
                if cx < w * 0.60 or cy < h * 0.55:
                    continue
                if ch > h * 0.7 or cw > w * 0.8:
                    continue
                if max(cw, ch) / max(1, min(cw, ch)) > 6:
                    continue
                selected.append((x, y, cw, ch, area))
            if not selected:
                return None

            mask = np.zeros((h, w), dtype=np.uint8)
            n, labels, stats, _ = cv2.connectedComponentsWithStats(candidate_mask, connectivity=8)
            for i in range(1, n):
                x, y, cw, ch, area = stats[i]
                for sx, sy, sw, sh, sa in selected:
                    if x == sx and y == sy and cw == sw and ch == sh and area == sa:
                        mask[labels == i] = 255
                        break

            total_area = cv2.countNonZero(mask)
            if total_area < self.config.min_watermark_area:
                return None

            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
            mask = cv2.dilate(mask, kernel, iterations=2)
            self.debug_save("fallback_mask.png", mask)
            return mask

        tx, ty, tw, th = text_box
        pad = self.config.watermark_padding

        # Crop the candidate mask to a bounded region around the matched text,
        # with extra room to its left for the watermark's icon glyph. Picking
        # by connected component here is unreliable: a decoration that merely
        # touches the watermark (a grid line, a ruler, a border) merges into
        # the same 8-connected blob as the text, so "keep the component near
        # the text" can pull in something far larger than the watermark
        # itself. A hard geometric crop can't be fooled that way -- content
        # outside the region is excluded no matter what it's connected to.
        icon_pad = max(60, int(th * 3.5))
        region_x0 = max(0, tx - icon_pad)
        region_y0 = max(0, ty - int(th * 1.5))
        region_x1 = min(w, tx + tw + pad)
        region_y1 = min(h, ty + th + pad)

        # Fill the region solid rather than keeping only its high-contrast
        # pixels: watermark badges commonly sit on a faint semi-transparent
        # chip/pill background that never clears the contrast threshold used
        # by `candidate_mask`, so intersecting with it left that soft
        # background visible as a ghost after the glyph strokes were removed.
        selected_mask = np.zeros((h, w), dtype=np.uint8)
        selected_mask[region_y0:region_y1, region_x0:region_x1] = 255

        if cv2.countNonZero(selected_mask) < self.config.min_watermark_area:
            return None

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        selected_mask = cv2.morphologyEx(selected_mask, cv2.MORPH_CLOSE, kernel, iterations=1)
        selected_mask = cv2.dilate(selected_mask, kernel, iterations=2)

        self.debug_save("candidate_mask.png", candidate_mask)
        self.debug_save("selected_mask.png", selected_mask)
        return selected_mask
