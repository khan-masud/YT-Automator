"""
TTS Generator Module.

Generates voiceover audio files using Edge-TTS with word-level timing.
Includes a gTTS fallback engine to guarantee uninterrupted execution.
"""
import asyncio
import json
import logging
import subprocess
from typing import List, Dict, Any
import edge_tts
from gtts import gTTS
import config

logger = logging.getLogger(__name__)


async def _generate_edge(text: str, out_path: str) -> List[Dict[str, Any]]:
    """Generates audio via Edge-TTS and captures word boundaries."""
    communicate = edge_tts.Communicate(text, config.TTS_VOICE)
    word_boundaries: List[Dict[str, Any]] = []

    with open(out_path, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                word_boundaries.append({
                    "text": chunk["text"],
                    "start": chunk["offset"] / 10_000_000,
                    "duration": chunk["duration"] / 10_000_000,
                })
            elif chunk["type"] == "SentenceBoundary":
                s_text = chunk["text"]
                s_start = chunk["offset"] / 10_000_000
                s_dur = chunk["duration"] / 10_000_000
                words = s_text.split()
                if words:
                    per_w = s_dur / max(len(words), 1)
                    for i, w in enumerate(words):
                        word_boundaries.append({
                            "text": w,
                            "start": s_start + i * per_w,
                            "duration": per_w,
                        })
    return word_boundaries


def _generate_gtts_fallback(text: str, out_path: str) -> List[Dict[str, Any]]:
    """Fallback TTS generator using gTTS."""
    tts = gTTS(text=text, lang="en")
    tts.save(out_path)

    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", out_path],
        capture_output=True,
        text=True,
    )
    duration = float(json.loads(result.stdout)["format"]["duration"])

    words = text.split()
    per_word = duration / max(len(words), 1)
    word_boundaries: List[Dict[str, Any]] = []
    for i, w in enumerate(words):
        word_boundaries.append({
            "text": w,
            "start": i * per_word,
            "duration": per_word,
        })
    return word_boundaries


def generate_voiceover(text: str, out_path: str) -> List[Dict[str, Any]]:
    """
    Generates voiceover audio for script text.
    Returns: List of word boundary dictionaries for subtitle alignment.
    """
    try:
        return asyncio.run(_generate_edge(text, out_path))
    except Exception as e:
        logger.warning(f"Edge-TTS failed ({e}). Falling back to gTTS engine.")
        return _generate_gtts_fallback(text, out_path)