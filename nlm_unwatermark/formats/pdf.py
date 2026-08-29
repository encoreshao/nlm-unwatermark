"""PDF watermark removal: text-layer redaction with a visual fallback."""

import io
import logging
import os
from typing import Optional

import cv2
import pymupdf as fitz
from PIL import Image
from tqdm import tqdm

from ..detection import WATERMARK_TEXT_VARIANTS
from ..engine import WatermarkRemover

logger = logging.getLogger(__name__)


def _find_watermark_text_rect(remover: WatermarkRemover, page: "fitz.Page") -> Optional["fitz.Rect"]:
    """
    Locates the watermark text via the PDF text layer. Returns a tight,
    lightly padded Rect suitable for redaction, or None if the watermark
    text isn't present in the text layer (e.g. a rasterized/scanned PDF).
    """
    w, h = page.rect.width, page.rect.height
    instances = [rect for text in WATERMARK_TEXT_VARIANTS for rect in page.search_for(text)]
    if not instances:
        return None

    best = None
    best_score = float('inf')
    for rect in instances:
        cy = (rect.y0 + rect.y1) / 2
        cx = (rect.x0 + rect.x1) / 2
        if cy < h * 0.78:
            continue
        if cx < w * 0.70:
            continue
        if rect.width > 320 or rect.height > 50:
            continue
        dist = abs(w - cx) + abs(h - cy)
        if dist < best_score:
            best_score = dist
            best = rect

    if best is None:
        return None

    pad = remover.config.watermark_padding
    return fitz.Rect(
        max(0, best.x0 - pad),
        max(0, best.y0 - pad),
        min(w, best.x1 + pad),
        min(h, best.y1 + pad),
    )


def _find_watermark_icon_zone(text_rect: "fitz.Rect", page_w: float, page_h: float) -> "fitz.Rect":
    """Region to the left of the watermark text where its icon glyph typically sits."""
    return fitz.Rect(
        max(0, text_rect.x0 - 95),
        max(0, text_rect.y0 - 18),
        min(page_w, text_rect.x0 + 8),
        min(page_h, text_rect.y1 + 18),
    )


def _redact_pdf_text(page: "fitz.Page", rect: "fitz.Rect") -> bool:
    """
    Deletes the watermark text from the PDF's text/content layer via
    redaction. Unlike overlaying a raster image on top, this actually
    removes the underlying text objects, so the watermark stops being
    searchable, selectable and copiable, and the original vector
    background is left completely untouched. Returns True if the
    watermark text is confirmed gone afterward.
    """
    try:
        page.add_redact_annot(rect, fill=None)
        try:
            page.apply_redactions(
                images=fitz.PDF_REDACT_IMAGE_NONE,
                graphics=fitz.PDF_REDACT_LINE_ART_NONE,
                text=fitz.PDF_REDACT_TEXT_REMOVE,
            )
        except TypeError:
            # Older PyMuPDF versions don't support these kwargs.
            page.apply_redactions()
    except Exception as e:
        logger.debug(f"Redaction failed on page {page.number}: {e}")
        return False
    return not any(page.search_for(text) for text in WATERMARK_TEXT_VARIANTS)


def _patch_pdf_rect(remover: WatermarkRemover, page: "fitz.Page", rect: "fitz.Rect") -> bool:
    """
    Renders `rect`, detects the watermark inside it, and reinserts only
    the tight sub-region around the detected mask -- real page content
    elsewhere in `rect` is never re-rasterized.
    """
    mat = fitz.Matrix(remover.config.pdf_dpi_scale, remover.config.pdf_dpi_scale)
    pix = page.get_pixmap(clip=rect, matrix=mat, alpha=False)
    roi_bgr = remover.pixmap_to_bgr(pix)
    if roi_bgr is None:
        return False

    # Render a wider surrounding clip too, so reconstruction can find a
    # clean donor patch even when the tight `rect` has nowhere clean nearby
    # (e.g. a watermark sitting right on a real content edge in a scanned page).
    page_w, page_h = page.rect.width, page.rect.height
    ctx_scale = remover.config.context_margin_scale
    extra_w = rect.width * (ctx_scale - 1) / 2
    extra_h = rect.height * (ctx_scale - 1) / 2
    context_rect = fitz.Rect(
        max(0, rect.x0 - extra_w), max(0, rect.y0 - extra_h),
        min(page_w, rect.x1 + extra_w), min(page_h, rect.y1 + extra_h),
    )
    context_pix = page.get_pixmap(clip=context_rect, matrix=mat, alpha=False)
    context_bgr = remover.pixmap_to_bgr(context_pix)
    scale = remover.config.pdf_dpi_scale
    context_offset = (
        int(round((rect.x0 - context_rect.x0) * scale)),
        int(round((rect.y0 - context_rect.y0) * scale)),
    )

    result = remover.clean_watermark_in_roi(roi_bgr, context_bgr, context_offset)
    if result is None:
        return False
    cleaned, mask = result

    x, y, bw, bh = cv2.boundingRect(mask)
    px = max(2, remover.config.watermark_padding)
    x0 = max(0, x - px)
    y0 = max(0, y - px)
    x1 = min(roi_bgr.shape[1], x + bw + px)
    y1 = min(roi_bgr.shape[0], y + bh + px)

    scale = remover.config.pdf_dpi_scale
    sub_rect = fitz.Rect(
        rect.x0 + x0 / scale, rect.y0 + y0 / scale,
        rect.x0 + x1 / scale, rect.y0 + y1 / scale,
    )

    sub_rgb = cv2.cvtColor(cleaned[y0:y1, x0:x1], cv2.COLOR_BGR2RGB)
    buf = io.BytesIO()
    Image.fromarray(sub_rgb).save(buf, format='PNG')
    page.insert_image(sub_rect, stream=buf.getvalue(), overlay=True)
    return True


def process_pdf(remover: WatermarkRemover, input_path: str, output_path: str, preview: bool = False) -> bool:
    """Removes the watermark from every page of a PDF (or just page one in preview mode)."""
    try:
        doc = fitz.open(input_path)
    except Exception as e:
        logger.error(f"Could not open {input_path}: {e}")
        return False

    filename = os.path.basename(input_path)
    pbar = tqdm(enumerate(doc), total=len(doc), desc=f"Processing {filename}", unit="page")
    patched = skipped = 0

    for i, page in pbar:
        if preview and i > 0:
            break

        w, h = page.rect.width, page.rect.height
        patched_now = False

        text_rect = _find_watermark_text_rect(remover, page)
        if text_rect is not None:
            icon_zone = _find_watermark_icon_zone(text_rect, w, h)
            if _redact_pdf_text(page, text_rect):
                # Text is gone from the text/content layer. The icon glyph next
                # to it (if any) isn't part of the text layer, so clean it up
                # rasterizing just that small zone -- this is a no-op if there
                # turns out to be no residue there.
                _patch_pdf_rect(remover, page, icon_zone)
                patched_now = True
            else:
                # Redaction unsupported/failed (e.g. very old PyMuPDF): fall
                # back to rasterizing just the watermark's own rect.
                patched_now = _patch_pdf_rect(remover, page, text_rect | icon_zone)

        if not patched_now:
            # No match in the text layer at all (rasterized/scanned PDF) --
            # fall back to scanning the bottom-right corner visually.
            corner = fitz.Rect(
                max(0, w - remover.config.search_margin_x),
                max(0, h - remover.config.search_margin_y),
                w,
                h,
            )
            patched_now = _patch_pdf_rect(remover, page, corner)

        if patched_now:
            patched += 1
        else:
            skipped += 1
        pbar.set_postfix(patched=patched, skipped=skipped)

    try:
        doc.save(output_path, garbage=3, deflate=True, clean=True)
        doc.close()
        logger.info(f"Saved {output_path} ({patched} patched, {skipped} skipped)")
        return True
    except Exception as e:
        logger.error(f"Error saving {output_path}: {e}")
        return False
