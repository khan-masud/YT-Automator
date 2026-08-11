"""
Visual Fetcher Module.

Generates visual search queries from scripts using Gemini API,
then fetches relevant video clips or photos from Pexels API.
"""
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
import requests
from google import genai
import config

_client = genai.Client(api_key=config.GEMINI_API_KEY)
_MODEL = "gemini-3.5-flash-lite"
PEXELS_HEADERS = {"Authorization": config.PEXELS_API_KEY}


def _extract_text(response) -> str:
    """Extracts text content from model response without non-text part warnings."""
    if hasattr(response, "candidates") and response.candidates:
        candidate = response.candidates[0]
        if hasattr(candidate, "content") and hasattr(candidate.content, "parts"):
            text_parts = [part.text for part in candidate.content.parts if hasattr(part, "text") and part.text]
            if text_parts:
                return "".join(text_parts).strip()
    return response.text.strip() if hasattr(response, "text") and response.text else ""


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
    response = _client.models.generate_content(model=_MODEL, contents=prompt)
    raw = _extract_text(response)
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:]

    queries = json.loads(raw.strip())
    return queries[:num_clips]


def _search_video(query: str, orientation: str) -> Optional[str]:
    """Searches Pexels for a video matching the query and orientation."""
    url = "https://api.pexels.com/videos/search"
    params = {"query": query, "orientation": orientation, "per_page": 3}
    r = requests.get(url, headers=PEXELS_HEADERS, params=params, timeout=20)
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


def _search_photo(query: str) -> Optional[str]:
    """Searches Pexels for a photo matching the query as fallback."""
    url = "https://api.pexels.com/v1/search"
    params = {"query": query, "per_page": 3}
    r = requests.get(url, headers=PEXELS_HEADERS, params=params, timeout=20)
    r.raise_for_status()
    data = r.json()
    photos = data.get("photos", [])
    if not photos:
        return None
    return photos[0]["src"]["large2x"]


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

    results: List[Dict[str, Any]] = []
    for i, query in enumerate(queries):
        try:
            video_url = _search_video(query, orientation)
        except requests.RequestException:
            video_url = None

        if video_url:
            out_path = work_dir / f"clip_{i:02d}.mp4"
            try:
                _download(video_url, out_path)
                results.append({"path": str(out_path), "type": "video"})
                continue
            except requests.RequestException:
                pass

        # Fallback to stock photo
        try:
            photo_url = _search_photo(query)
        except requests.RequestException:
            photo_url = None

        if photo_url:
            out_path = work_dir / f"clip_{i:02d}.jpg"
            try:
                _download(photo_url, out_path)
                results.append({"path": str(out_path), "type": "image"})
                continue
            except requests.RequestException:
                pass

        # Fallback to blank color block if no visual asset was retrieved
        results.append({"path": None, "type": "blank"})

    return results