"""
Script Generator Module.

Uses Google Gemini API via resilient multi-model cascade to:
1. Auto-generate video topics when the manual queue is empty.
2. Generate structured scripts, catchy titles, descriptions, and tags.
"""
import json
import logging
from typing import Dict, Any, List
import config
import db_manager
import ai_client

logger = logging.getLogger("script_generator")

# Evergreen fallback topics if AI is completely unavailable
_FALLBACK_TOPICS_SHORT = [
    "Why the human brain uses 20% of total body energy",
    "How honey never spoils even after thousands of years",
    "Why astronauts grow taller in outer space",
    "The secret reason flamingos stand on one leg",
    "How trees communicate underground through fungi networks",
    "Why deep sea creatures glow in total darkness",
    "How lightning strikes can reach five times hotter than the sun",
]

_FALLBACK_TOPICS_LONG = [
    "The engineering marvels of the ancient Roman aqueducts",
    "How deep sea exploration revealed Earth's most extreme ecosystems",
    "The complete science of black holes and event horizons explained",
    "How the human immune system fights off billions of pathogens daily",
    "The mystery of the James Webb Space Telescope's deepest discoveries",
]


def generate_topic(video_format: str) -> str:
    """Generates a unique catchy video topic idea for the specified format, avoiding duplicates."""
    length_hint = "a short, punchy fact" if video_format == "short" else "a broader, multi-part topic"
    past_topics = db_manager.get_past_topics_for_format(video_format)
    exclusion_text = ""
    if past_topics:
        past_list_str = "\n".join(f"- {t}" for t in past_topics[:30])
        exclusion_text = f"\nDO NOT suggest any of these previously covered topics for {video_format}:\n{past_list_str}\n"

    prompt = f"""
You generate YouTube video topics for an educational facts channel.
Niche: {config.CHANNEL_NICHE}
Provide ONE single unique topic idea suitable for {length_hint}.{exclusion_text}
Reply with ONLY the topic title, nothing else. No quotes, no numbering.
"""
    for attempt in range(3):
        try:
            raw_topic = ai_client.generate_content_with_retry(prompt, expect_json=False)
            topic = raw_topic.strip('"\n #*')
            # Extract first line if multiple lines returned
            if "\n" in topic:
                topic = topic.split("\n")[0].strip('"\n #*')

            if topic and not db_manager.is_topic_duplicate(topic, video_format):
                return topic
        except Exception as e:
            logger.warning(f"Topic generation attempt {attempt + 1} failed: {e}")

    # Emergency fallback to curated evergreen topics if AI fails
    logger.warning("AI topic generation exhausted. Using emergency curated fallback topic...")
    pool = _FALLBACK_TOPICS_SHORT if video_format == "short" else _FALLBACK_TOPICS_LONG
    for fb in pool:
        if not db_manager.is_topic_duplicate(fb, video_format):
            return fb

    return pool[0]


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
    try:
        raw_json = ai_client.generate_content_with_retry(prompt, expect_json=True)
        data = json.loads(raw_json)
        # Ensure all required keys exist
        if "title" not in data or not data["title"]:
            data["title"] = topic[:80]
        if "script" not in data or not data["script"]:
            raise ValueError("Generated JSON missing 'script' field.")
        if "description" not in data:
            data["description"] = f"Learn all about {topic}. Subscribe for more daily facts!"
        if "tags" not in data or not isinstance(data["tags"], list):
            data["tags"] = ["facts", "education", "science", "learn", "ytshorts"]
        return data
    except Exception as e:
        logger.error(f"Structured script generation failed ({e}). Generating fallback script...")
        # Fallback to direct text prompt if JSON formatting fails
        direct_prompt = f"Write an educational spoken narration about: {topic}. Length: {word_count}. Spoken words only."
        fallback_text = ai_client.generate_content_with_retry(direct_prompt, expect_json=False)
        return {
            "title": topic[:80],
            "script": fallback_text.strip(),
            "description": f"Exploring {topic}. Subscribe for more fascinating educational content!",
            "tags": ["education", "facts", "curiosity", "learning", "knowledge"]
        }