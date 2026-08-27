"""Configuration for watermark detection and removal."""

from dataclasses import dataclass


@dataclass
class WatermarkConfig:
    """Configuration for watermark detection and removal."""
    # Search margins from the bottom-right corner
    search_margin_x: int = 400
    search_margin_y: int = 120

    # Extra padding around detected watermark bbox
    watermark_padding: int = 6

    # Threshold for contrast-based candidate extraction
    pixel_threshold: int = 22

    # PDF rendering scale factor (higher = better quality)
    pdf_dpi_scale: float = 3.5

    # Inpainting radius for cv2.inpaint (used only as fallback)
    inpaint_radius: int = 3

    # Component filters
    min_watermark_area: int = 400
    min_component_area: int = 18
    max_component_area_ratio: float = 0.25

    # Text/template detection
    text_match_threshold: float = 0.30
    text_luma_threshold: int = 210  # how far from mid-gray a pixel must be to count as "text", regardless of polarity
    roi_bottom_bias: float = 0.35
    roi_right_bias: float = 0.45

    # Morphology
    dilate_iterations: int = 1
    close_iterations: int = 1

    # Reconstruction
    use_patch_heal: bool = True

    # Debug
    debug: bool = False
