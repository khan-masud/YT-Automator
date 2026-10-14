"""Local visual asset loader for Happy Little Stars.

Place approved images and videos in assets/visuals/. The pipeline fails clearly
when that directory is empty instead of silently creating blank videos.
"""
import logging
import shutil
from pathlib import Path
from typing import Any, Dict, List

import config

logger = logging.getLogger("visual_fetcher")

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v"}


def fetch_visuals_for_script(
    script: str,
    num_clips: int,
    orientation: str,
    work_dir: Path,
) -> List[Dict[str, Any]]:
    """Copy approved local assets into a video's temporary working directory."""
    del script, orientation
    work_dir.mkdir(parents=True, exist_ok=True)
    assets_dir = config.ASSETS_DIR / "visuals"
    assets_dir.mkdir(parents=True, exist_ok=True)

    candidates = sorted(
        p for p in assets_dir.iterdir()
        if p.is_file() and p.suffix.lower() in (IMAGE_EXTENSIONS | VIDEO_EXTENSIONS)
    )

    if not candidates:
        raise RuntimeError(
            "No visual assets found in assets/visuals/. Add approved child-friendly "
            "images/videos before running the pipeline; upload has been stopped to "
            "prevent a blank video."
        )

    results: List[Dict[str, Any]] = []
    for i in range(num_clips):
        source = candidates[i % len(candidates)]
        target = work_dir / f"clip_{i:02d}{source.suffix.lower()}"
        shutil.copy2(source, target)
        asset_type = "video" if source.suffix.lower() in VIDEO_EXTENSIONS else "image"
        results.append({"path": str(target), "type": asset_type})

    logger.info("Loaded %d visual clips from %s", len(results), assets_dir)
    return results
