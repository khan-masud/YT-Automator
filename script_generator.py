"""
Script Generator Module.

Uses Google Gemini API to:
1. Auto-generate video topics when the manual queue is empty.
2. Generate structured scripts, catchy titles, descriptions, and tags.
"""
import json
from typing import Dict, Any
from google import genai
import config

_client = genai.Client(api_key=config.GEMINI_API_KEY)
_MODEL = "gemini-3.5-flash-lite"


def _extract_text(response) -> str:
    """Extracts text content from model response without non-text part warnings."""
    if hasattr(response, "candidates") and response.candidates:
        candidate = response.candidates[0]
        if hasattr(candidate, "content") and hasattr(candidate.content, "parts"):
            text_parts = [part.text for part in candidate.content.parts if hasattr(part, "text") and part.text]
            if text_parts:
                return "".join(text_parts).strip()
    return response.text.strip() if hasattr(response, "text") and response.text else ""


def generate_topic(video_format: str) -> str:
    """Generates a unique catchy video topic idea for the specified format, avoiding duplicates."""
    import db_manager
    length_hint = "a short, punchy fact" if video_format == "short" else "a broader, multi-part topic"
    past_topics = db_manager.get_past_topics_for_format(video_format)
    exclusion_text = ""
    if past_topics:
        past_list_str = "\n".join(f"- {t}" for t in past_topics[:30])
        exclusion_text = f"\nDO NOT suggest any of these previously covered topics for {video_format}:\n{past_list_str}\n"

    for attempt in range(4):
        prompt = f"""
You generate YouTube video topics for an educational facts channel.
Niche: {config.CHANNEL_NICHE}
Provide ONE single unique topic idea suitable for {length_hint}.{exclusion_text}
Reply with ONLY the topic title, nothing else. No quotes, no numbering.
"""
        response = _client.models.generate_content(model=_MODEL, contents=prompt)
        topic = _extract_text(response).strip('"\n ')
        if topic and not db_manager.is_topic_duplicate(topic, video_format):
            return topic

    return topic


def generate_script(topic: str, video_format: str) -> Dict[str, Any]:
    """
    Generates structured script metadata for a topic.
    Returns: {"title": str, "script": str, "description": str, "tags": list}
    """
    if video_format == "short":
        word_count = "120-150 words, fast-paced, strong hook in the first sentence"
    else:
        word_count = "700-900 words, structured with an introduction, 3-4 key points, and a conclusion"

    prompt = f"""
Write a YouTube video script about: "{topic}"

Requirements:
- Length: {word_count}
- Tone: Engaging, conversational spoken tone for voiceover delivery
- Start with a compelling hook sentence
- Exclude stage directions, music tags, or section headers (only spoken content)
- Factually accurate without fabricated statistics

Additional fields:
- Catchy YouTube title (under 80 characters)
- Short YouTube description (2-3 sentences with a subscribe call-to-action)
- 5 relevant video tags

Respond ONLY in valid JSON format:
{{
  "title": "...",
  "script": "...",
  "description": "...",
  "tags": ["...", "...", "...", "...", "..."]
}}
"""
    response = _client.models.generate_content(model=_MODEL, contents=prompt)
    raw = _extract_text(response)
    
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:]

    data = json.loads(raw.strip())
    return data