"""Reconstructs the pixels behind a removed watermark mask."""

import cv2
import numpy as np

from .config import WatermarkConfig


def patch_reconstruct(
    img_bgr: np.ndarray,
    mask: np.ndarray,
    inpaint_radius: int = 3,
    max_patch_diff: float = 20.0,
) -> np.ndarray:
    """
    Heals the masked area by copying a nearby clean patch of background.
    This is much better for textures like dotted paper or grain.

    Candidate source offsets scale with the size of the healed area (rather
    than a fixed pixel distance), so this works whether the mask comes from
    a tight PDF crop or a large upscaled image corner. Eight directions are
    tried at several distances each -- a watermark sitting right on a real
    content edge (e.g. a photo's own silhouette) often has no clean match
    close by, but a similar edge crossing recurs further along it, which a
    single fixed-distance offset per direction would miss. Among in-bounds,
    mask-free candidates, the one whose border ring most closely matches the
    destination's border ring is used, to avoid visible seams.

    If nothing comes close enough (`max_patch_diff`), pasting the best
    available candidate would do more harm than good: seamless cloning
    trusts the donor patch's own gradients, so stitching in unrelated
    content (a print, a different edge) doesn't just look mismatched, it
    gets confidently redrawn as if it belonged. Plain inpainting is used
    instead in that case -- blurrier, but it can't hallucinate structure
    that isn't there.
    """
    h, w = mask.shape[:2]
    ys, xs = np.where(mask > 0)
    if len(xs) == 0:
        return img_bgr

    # Define the bounding box of the area to heal
    x0, y0, bw, bh = cv2.boundingRect(mask)

    # Expand slightly so the comparison ring below sits mostly on clean pixels
    pad = 4
    x0_p = max(0, x0 - pad)
    y0_p = max(0, y0 - pad)
    x1_p = min(w, x0 + bw + pad)
    y1_p = min(h, y0 + bh + pad)

    bw_p = x1_p - x0_p
    bh_p = y1_p - y0_p

    directions = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1)]
    magnitudes = (1.0, 1.3, 1.6, 2.0, 2.5, 3.0)

    border = min(4, bh_p // 2, bw_p // 2)
    ring = np.zeros((bh_p, bw_p), dtype=bool)
    if border > 0:
        ring[:border, :] = ring[-border:, :] = True
        ring[:, :border] = ring[:, -border:] = True
    dest_ring = img_bgr[y0_p:y1_p, x0_p:x1_p][ring].astype(np.int16)

    best_patch = None
    best_diff = float('inf')
    for dxu, dyu in directions:
        for mag in magnitudes:
            src_x = x0_p + int(dxu * bw_p * mag)
            src_y = y0_p + int(dyu * bh_p * mag)

            # Check if source is within bounds and doesn't overlap the mask
            if src_x < 0 or src_y < 0 or src_x + bw_p > w or src_y + bh_p > h:
                continue
            src_mask = mask[src_y:src_y + bh_p, src_x:src_x + bw_p]
            if cv2.countNonZero(src_mask) != 0:
                continue

            candidate = img_bgr[src_y:src_y + bh_p, src_x:src_x + bw_p]
            diff = float(np.abs(candidate[ring].astype(np.int16) - dest_ring).mean()) if ring.any() else 0.0
            if diff < best_diff:
                best_diff = diff
                best_patch = candidate.copy()

    out = img_bgr.copy()
    if best_patch is not None and best_diff <= max_patch_diff:
        # Plain alpha blending, not Poisson/seamless cloning: a solved
        # Laplace boundary-value problem over a *rectangular* mask that
        # straddles a real, sharp content edge (a photo's own silhouette)
        # produces a radiating artifact from the boundary conditions alone,
        # regardless of which donor patch supplies the interior gradients.
        # A close-matching donor found via the wider/finer search above
        # only needs its seam softened, not full gradient-domain solving.
        target_roi = out[y0_p:y1_p, x0_p:x1_p]
        mask_roi = mask[y0_p:y1_p, x0_p:x1_p]
        feather = max(3, (min(bw_p, bh_p) // 6) | 1)
        mask_float = mask_roi.astype(float) / 255.0
        mask_float = cv2.GaussianBlur(mask_float, (feather, feather), 0)
        for c in range(3):
            target_roi[:, :, c] = (target_roi[:, :, c] * (1 - mask_float) +
                                   best_patch[:, :, c] * mask_float).astype(np.uint8)
    else:
        # No close-enough donor patch: fall back to diffusion inpainting
        # rather than risk stitching in a mismatched one.
        out = cv2.inpaint(out, mask, inpaint_radius, cv2.INPAINT_TELEA)

    return out


def heal(img_bgr: np.ndarray, mask: np.ndarray, config: WatermarkConfig) -> np.ndarray:
    """Reconstructs the masked region using patch healing, or plain inpainting
    if `config.use_patch_heal` is disabled."""
    if config.use_patch_heal:
        return patch_reconstruct(img_bgr, mask, config.inpaint_radius, config.patch_quality_threshold)
    return cv2.inpaint(img_bgr, mask, config.inpaint_radius, cv2.INPAINT_TELEA)
