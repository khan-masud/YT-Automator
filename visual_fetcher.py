"""
Visual Fetcher Module.

Generates visual search queries from scripts using Gemini API (with resilient cascade),
then fetches relevant video clips or photos from Pexels API.
"""
import re
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import requests
import config
import ai_client

logger = logging.getLogger("visual_fetcher")
PEXELS_HEADERS = {"Authorization": config.PEXELS_API_KEY}


def _rule_based_visual_queries(script: str, num_clips: int) -> List[str]:
    """Fallback visual query generator using sentence tokenization and keyword heuristics."""
    sentences = [s.strip() for s in re.split(r"[.!?\n]+", script) if len(s.strip()) > 10]
    stop_words = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "with", "about",
        "against", "between", "into", "through", "during", "before", "after", "above", "below",
        "from", "up", "down", "in", "out", "on", "off", "over", "under", "again", "further",
        "then", "once", "here", "there", "when", "where", "why", "how", "all", "any", "both",
        "each", "few", "more", "most", "other", "some", "such", "no", "nor", "not", "only",
        "own", "same", "so", "than", "too", "very", "s", "t", "can", "will", "just", "don",
        "should", "now", "did", "you", "know", "that", "this", "these", "those", "what", "is",
        "are", "was", "were", "be", "been", "being", "have", "has", "had", "having", "do",
        "does", "did", "doing"
    }

    queries: List[str] = []
    if not sentences:
        return ["nature abstract background"] * num_clips

    step = max(1, len(sentences) // max(1, num_clips))
    for i in range(num_clips):
        idx = min(i * step, len(sentences) - 1)
        sentence = sentences[idx]
        words = [w for w in re.findall(r"\b[a-zA-Z]{3,}\b", sentence.lower()) if w not in stop_words]
        if len(words) >= 2:
            query = " ".join(words[:3])
        elif words:
            query = words[0] + " background"
        else:
            query = "cinematic atmospheric"
        queries.append(query)

    return queries[:num_clips]


def generate_visual_queries(script: str, num_clips: int) -> List[str]:
    """Generates a list of simple stock footage search queries from a script."""
    prompt = f"""
Here is a video script:
---
{script}
---
Break this script into {num_clips} short visual scenes in chronological order.
For each scene, provide a simple, concrete stock-footage search query (2-4 words, literal/visual, e.g. "ocean waves sunset", "person typing laptop").
Respond ONLY as a JSON list of strings, exactly {num_clips} items, with no markdown formatting.
"""
    try:
        raw_json = ai_client.generate_content_with_retry(prompt, expect_json=True)
        queries = json.loads(raw_json)
        if isinstance(queries, list) and len(queries) > 0:
            return [str(q).strip() for q in queries[:num_clips]]
    except Exception as e:
        logger.warning(f"AI visual query generation failed ({e}). Falling back to rule-based keyword queries...")

    return _rule_based_visual_queries(script, num_clips)


def _search_video(query: str, orientation: str) -> Optional[str]:
    """Searches Pexels for a video matching the query and orientation."""
    url = "https://api.pexels.com/videos/search"
    params = {"query": query, "orientation": orientation, "per_page": 3}
    try:
        r = requests.get(url, headers=PEXELS_HEADERS, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        videos = data.get("videos", [])
        if not videos:
            return None

        # Sort descending by resolution and select highest quality HD file
        video_files = sorted(videos[0]["video_files"], key=lambda v: v.get("width", 0), reverse=True)
        for vf in video_files:
            if 1080 <= vf.get("width", 0) <= 3840:
                return vf["link"]
        return video_files[0]["link"] if video_files else None
    except Exception as e:
        logger.warning(f"Pexels video search failed for query '{query}': {e}")
        return None


def _search_photo(query: str) -> Optional[str]:
    """Searches Pexels for a photo matching the query as fallback."""
    url = "https://api.pexels.com/v1/search"
    params = {"query": query, "per_page": 3}
    try:
        r = requests.get(url, headers=PEXELS_HEADERS, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        photos = data.get("photos", [])
        if not photos:
            return None
        return photos[0]["src"]["large2x"]
    except Exception as e:
        logger.warning(f"Pexels photo search failed for query '{query}': {e}")
        return None


def _download(url: str, out_path: Path) -> None:
    """Downloads a file from a URL to the specified local path."""
    r = requests.get(url, stream=True, timeout=60)
    r.raise_for_status()
    with open(out_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)


def fetch_visuals_for_script(script: str, num_clips: int, orientation: str, work_dir: Path) -> List[Dict[str, Any]]:
    """
    Fetches visual assets for a script.
    orientation: "portrait" (shorts) or "landscape" (long-form)
    Returns: List of dicts [{"path": str, "type": "video"|"image"|"blank"}]
    """
    work_dir.mkdir(parents=True, exist_ok=True)
    queries = generate_visual_queries(script, num_clips)
    logger.info(f"Visual search queries ({len(queries)}): {queries}")

    results: List[Dict[str, Any]] = []
    for i, query in enumerate(queries):
        video_url = _search_video(query, orientation)
        if video_url:
            out_path = work_dir / f"clip_{i:02d}.mp4"
            try:
                _download(video_url, out_path)
                results.append({"path": str(out_path), "type": "video"})
                continue
            except Exception as e:
                logger.warning(f"Failed to download video clip {i}: {e}")

        # Fallback to stock photo
        photo_url = _search_photo(query)
        if photo_url:
            out_path = work_dir / f"clip_{i:02d}.jpg"
            try:
                _download(photo_url, out_path)
                results.append({"path": str(out_path), "type": "image"})
                continue
            except Exception as e:
                logger.warning(f"Failed to download photo clip {i}: {e}")

        # Fallback to blank color block if no visual asset was retrieved
        results.append({"path": None, "type": "blank"})

    return results