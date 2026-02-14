"""
UPES visualization: heatmap from final_score raster; optional high-risk overlay.
"""
from pathlib import Path
from typing import Optional, Tuple

import numpy as np


def render_upes_heatmap(
    raster_path: Path,
    output_path: Optional[Path] = None,
    threshold: Optional[float] = None,
    title: str = "UPES Final Score",
) -> Tuple[Optional[Path], Optional[bytes]]:
    """
    Read final_score GeoTIFF, render Matplotlib heatmap; optionally highlight cells > threshold.
    If output_path is set, save PNG there and return (output_path, None).
    Else return (None, png_bytes) for in-memory response.
    """
    import rasterio
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if threshold is None:
        from config import settings
        threshold = getattr(settings, "upes_alert_threshold", 0.5)
    with rasterio.open(raster_path) as src:
        data = src.read()
    arr = np.squeeze(data)
    if arr.ndim != 2:
        return None, None
    fig, ax = plt.subplots(figsize=(10, 8))
    im = ax.imshow(arr, cmap="YlOrRd", vmin=0, vmax=1, origin="upper")
    if threshold is not None:
        ax.contour(arr, levels=[threshold], colors=["darkred"], linewidths=2)
    ax.set_title(title)
    plt.colorbar(im, ax=ax, label="UPES")
    plt.tight_layout()
    if output_path is not None:
        plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
        plt.close()
        return output_path, None
    import io
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="white")
    plt.close()
    buf.seek(0)
    return None, buf.read()
