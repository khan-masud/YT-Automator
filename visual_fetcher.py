"""
Local Visual Asset Loader.

No stock-footage service or API key is used. Add approved images/videos to
assets/visuals/; the pipeline cycles through them for each generated video.
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
    """
    Copies local assets into the working directory.
    Put the channel's consistent character artwork and backgrounds in
    assets/visuals/. If no files exist, blank segments are returned safely.
    """
    del script, orientation  # Local asset selection does not need API queries.
    work_dir.mkdir(parents=True, exist_ok=True)
    assets_dir = config.ASSETS_DIR / "visuals"
    assets_dir.mkdir(parents=True, exist_ok=True)

    candidates = sorted(
        p for p in assets_dir.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS | VIDEO_EXTENSIONS
    )

    if not candidates:
        logger.warning(
            "No local visuals found. Add character images/videos to assets/visuals/; "
            "no external stock API will be called."
        )
        return [{"path": None, "type": "blank"} for _ in range(num_clips)]

    results: List[Dict[str, Any]] = []
    for i in range(num_clips):
        source = candidates[i % len(candidates)]
        target = work_dir / f"clip_{i:02d}{source.suffix.lower()}"
        shutil.copy2(source, target)
        asset_type = "video" if source.suffix.lower() in VIDEO_EXTENSIONS else "image"
        results.append({"path": str(target), "type": asset_type})

    logger.info("Loaded %d local visual assets from %s", len(results), assets_dir)
    return results
