"""
Configuration module for YouTube Automation.
Loads settings, API keys, and environment variables.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# API Keys & Secrets
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
YOUTUBE_CLIENT_SECRETS_FILE = BASE_DIR / os.getenv("YOUTUBE_CLIENT_SECRETS_FILE", "client_secrets.json")
YOUTUBE_TOKEN_FILE = BASE_DIR / "youtube_token.json"

# Gemini AI model cascade. Use currently supported model IDs.
_models_env = os.getenv("GEMINI_MODELS", "gemini-3.8-flash")
GEMINI_MODELS = [m.strip() for m in _models_env.split(",") if m.strip()]

# Channel & Production Settings
CHANNEL_NICHE = os.getenv("CHANNEL_NICHE", "preschool nursery rhymes and early learning songs for children ages 2 to 6")
DAILY_SHORTS_COUNT = int(os.getenv("DAILY_SHORTS_COUNT", "1"))
DAILY_LONGFORM_COUNT = int(os.getenv("DAILY_LONGFORM_COUNT", "1"))
# Safe default: nothing becomes public unless explicitly configured.
YOUTUBE_PRIVACY_STATUS = os.getenv("YOUTUBE_PRIVACY_STATUS", "private").strip().lower()
if YOUTUBE_PRIVACY_STATUS not in {"private", "unlisted", "public"}:
    raise ValueError("YOUTUBE_PRIVACY_STATUS must be private, unlisted, or public")

# Directory Paths
OUTPUT_DIR = BASE_DIR / "output"
LOGS_DIR = BASE_DIR / "logs"
ASSETS_DIR = BASE_DIR / "assets"
DATA_DIR = BASE_DIR / "data"
DB_FILE = DATA_DIR / "yt_automator.db"
TOPIC_QUEUE_FILE = BASE_DIR / "topics_queue.txt"
USED_TOPICS_FILE = BASE_DIR / "used_topics.txt"

# Voice & Video Specifications
TTS_VOICE = "en-US-ChristopherNeural"
SHORTS_SIZE = (1080, 1920)
LONGFORM_SIZE = (1920, 1080)

for directory in (OUTPUT_DIR, LOGS_DIR, ASSETS_DIR, DATA_DIR):
    directory.mkdir(parents=True, exist_ok=True)
