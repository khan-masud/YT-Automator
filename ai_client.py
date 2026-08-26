"""
Resilient AI Client Module for YT Automator.

Provides a unified, resilient interface to Google Gemini API with:
1. Multi-model cascade fallback (e.g. gemini-2.5-flash -> gemini-2.0-flash -> gemini-1.5-flash -> gemini-2.5-flash-lite).
2. Exponential backoff with jitter on 503 (High Demand / Service Unavailable), 429 (Rate Limit), and connection drops.
3. Robust JSON cleaning and parsing.
"""
import time
import random
import json
import logging
from typing import Optional, List, Dict, Any
from google import genai
import config

logger = logging.getLogger("ai_client")

# Initialize client
_client = None


def get_client() -> genai.Client:
    """Lazy initialization of Google GenAI Client."""
    global _client
    if _client is None:
        _client = genai.Client(api_key=config.GEMINI_API_KEY)
    return _client


def _extract_text_from_response(response: Any) -> str:
    """Extracts raw text content from model response parts safely."""
    if hasattr(response, "candidates") and response.candidates:
        candidate = response.candidates[0]
        if hasattr(candidate, "content") and hasattr(candidate.content, "parts"):
            text_parts = [
                part.text for part in candidate.content.parts
                if hasattr(part, "text") and part.text
            ]
            if text_parts:
                return "".join(text_parts).strip()
    return response.text.strip() if hasattr(response, "text") and response.text else ""


def clean_json_response(raw: str) -> str:
    """Strips markdown code blocks, prefixes, and surrounding whitespace from JSON output."""
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        # Remove opening ``` or ```json
        if lines[0].startswith("```"):
            lines = lines[1:]
        # Remove trailing ```
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        raw = "\n".join(lines).strip()
    return raw


def generate_content_with_retry(
    prompt: str,
    expect_json: bool = False,
    candidate_models: Optional[List[str]] = None,
    max_retries_per_model: int = 3
) -> str:
    """
    Generates content using a resilient multi-model cascade with exponential backoff.
    
    Tries each model in candidate_models in sequence. If a model encounters a 503, 429,
    or network/timeout error, it retries with exponential backoff. If max retries are
    exceeded for a model, it gracefully falls back to the next model in the cascade.
    """
    models = candidate_models or config.GEMINI_MODELS
    client = get_client()

    last_exception = None

    for model in models:
        for attempt in range(1, max_retries_per_model + 1):
            try:
                logger.info(f"Calling Gemini model '{model}' (Attempt {attempt}/{max_retries_per_model})...")
                response = client.models.generate_content(
                    model=model,
                    contents=prompt
                )
                text = _extract_text_from_response(response)
                if not text:
                    raise ValueError(f"Empty response received from model '{model}'")

                if expect_json:
                    cleaned = clean_json_response(text)
                    # Verify it is valid JSON
                    json.loads(cleaned)
                    return cleaned

                return text

            except Exception as e:
                last_exception = e
                err_str = str(e)
                is_transient = any(
                    indicator in err_str.lower()
                    for indicator in [
                        "503", "unavailable", "high demand", "rate limit",
                        "429", "timeout", "disconnected", "remoteprotocolerror",
                        "connection reset", "econnreset", "deadline"
                    ]
                )

                if is_transient and attempt < max_retries_per_model:
                    # Exponential backoff with random jitter
                    delay = min(2 ** attempt + random.uniform(1.0, 2.5), 15.0)
                    logger.warning(
                        f"Transient error with model '{model}' ({type(e).__name__}: {err_str[:120]}...). "
                        f"Retrying in {delay:.1f}s (Attempt {attempt}/{max_retries_per_model})..."
                    )
                    time.sleep(delay)
                else:
                    logger.warning(
                        f"Model '{model}' failed on attempt {attempt}: {err_str[:150]}. "
                        f"Transitioning to next available model in cascade..."
                    )
                    break  # Move to next model in candidate list

    logger.error("All Gemini cascade models failed to respond.")
    if last_exception:
        raise last_exception
    raise RuntimeError("Failed to generate content from any candidate Gemini model.")
